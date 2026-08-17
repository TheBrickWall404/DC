import sqlite3
import re
import unicodedata
import requests

DB_NAME = "debate_cv.db"

# Valid Chen algorithm speaking classes (Class C and above)
ELIGIBLE_CLASSES = {"S-WUDC", "S-AAA+", "S-AAA", "S-AA+", "S-AA", "S-A+", "S-A", "S-B", "S-C"}

# -------------------------------------------------------------
# 1. Chen Name Normalizer Spec
# -------------------------------------------------------------
def normalize_name(name: str) -> str:
    """
    Implements the Chen Name Matcher:
    - Removes quotes and brackets (nicknames)
    - Replaces diacritics and special Latin characters (Đ, Ł, Ø, etc.)
    - Removes emojis and non-alphabetic characters
    - Trims and lowercases
    - Strips whitespace
    """
    if not name:
        return ""
    
    # Remove text in brackets or quotes
    cleaned = re.sub(r'\(.*?\)|\[.*?\]|".*?"|\'.*?\'', '', name)
    
    # Custom character handling before decomposition
    custom_map = {
        'đ': 'd', 'Đ': 'd', 'ð': 'd', 'Ð': 'd',
        'ł': 'l', 'Ł': 'l', 'ø': 'o', 'Ø': 'o'
    }
    for char, replacement in custom_map.items():
        cleaned = cleaned.replace(char, replacement)
    
    # Normalize unicode accents/diacritics
    cleaned = unicodedata.normalize('NFKD', cleaned).encode('ASCII', 'ignore').decode('utf-8')
    
    # Remove non-letter characters
    cleaned = re.sub(r'[^a-zA-Z\s]', '', cleaned)
    
    # Decapitalize and remove intra-word spaces
    return re.sub(r'\s+', '', cleaned).lower()


# -------------------------------------------------------------
# 2. Database Initialization
# -------------------------------------------------------------
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
    cur.execute("""
    CREATE TABLE IF NOT EXISTS tournaments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slug TEXT UNIQUE,
        name TEXT,
        date TEXT,
        speaking_class TEXT,
        format TEXT DEFAULT 'BP',
        is_prm INTEGER DEFAULT 0
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS participants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        raw_name TEXT,
        normalized_name TEXT UNIQUE
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS speaker_tab (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tournament_id INTEGER,
        participant_id INTEGER,
        speaker_rank INTEGER,
        total_speakers INTEGER,
        average_speaks REAL,
        is_eligible INTEGER,
        FOREIGN KEY(tournament_id) REFERENCES tournaments(id),
        FOREIGN KEY(participant_id) REFERENCES participants(id)
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS team_tab (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tournament_id INTEGER,
        team_name TEXT,
        team_rank INTEGER,
        total_teams INTEGER,
        is_eligible INTEGER,
        FOREIGN KEY(tournament_id) REFERENCES tournaments(id)
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS team_members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tournament_id INTEGER,
        team_name TEXT,
        participant_id INTEGER,
        FOREIGN KEY(tournament_id) REFERENCES tournaments(id),
        FOREIGN KEY(participant_id) REFERENCES participants(id)
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS outrounds (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tournament_id INTEGER,
        team_name TEXT,
        category TEXT,
        is_open INTEGER,
        furthest_stage TEXT,
        FOREIGN KEY(tournament_id) REFERENCES tournaments(id)
    );
    """)
    
    conn.commit()
    conn.close()


# -------------------------------------------------------------
# 3. Tabbycat REST API Ingest Pipeline
# -------------------------------------------------------------
class TabbycatScraper:
    def __init__(self, base_url: str, api_token: str = None):
        self.base_url = base_url.rstrip("/")
        self.headers = {"Authorization": f"Token {api_token}"} if api_token else {}

    def get(self, endpoint: str):
        url = f"{self.base_url}/api/v1/{endpoint.lstrip('/')}"
        res = requests.get(url, headers=self.headers)
        res.raise_for_status()
        return res.json()

    def get_or_create_participant(self, cur, raw_name: str) -> int:
        norm = normalize_name(raw_name)
        cur.execute("SELECT id FROM participants WHERE normalized_name = ?", (norm,))
        row = cur.fetchone()
        if row:
            return row[0]
        cur.execute("INSERT INTO participants (raw_name, normalized_name) VALUES (?, ?)", (raw_name, norm))
        return cur.lastrowid

    def ingest_tournament(self, tournament_slug: str, speaking_class: str, is_prm: bool = False, format_type: str = "BP"):
        # Check eligibility threshold: Ignore anything below Class S-C
        if speaking_class not in ELIGIBLE_CLASSES:
            print(f"Skipping {tournament_slug}: Speaking class '{speaking_class}' is below S-C.")
            return

        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()

        # 1. Store Tournament
        tourn_data = self.get(f"tournaments/{tournament_slug}")
        cur.execute("""
            INSERT OR REPLACE INTO tournaments (slug, name, date, speaking_class, format, is_prm)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (tournament_slug, tourn_data.get("name"), tourn_data.get("starts_at", ""), speaking_class, format_type, int(is_prm)))
        tournament_id = cur.execute("SELECT id FROM tournaments WHERE slug = ?", (tournament_slug,)).fetchone()[0]

        # 2. Ingest Speaker Tab (Standings)
        speaker_standings = self.get(f"tournaments/{tournament_slug}/speakers/standings")
        total_speakers = len(speaker_standings)
        for entry in speaker_standings:
            speaker_info = entry.get("speaker", {})
            raw_name = speaker_info.get("name")
            p_id = self.get_or_create_participant(cur, raw_name)
            
            rank = entry.get("ranking", entry.get("rank"))
            # Top 50% eligibility condition
            is_eligible = 1 if rank and rank <= (total_speakers / 2) else 0
            
            # Fetch average speaker score if present in metrics
            speaks = entry.get("metrics", {}).get("average_score", 0.0)

            cur.execute("""
                INSERT INTO speaker_tab (tournament_id, participant_id, speaker_rank, total_speakers, average_speaks, is_eligible)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (tournament_id, p_id, rank, total_speakers, speaks, is_eligible))

        # 3. Ingest Team Tab & Roster
        team_standings = self.get(f"tournaments/{tournament_slug}/teams/standings")
        total_teams = len(team_standings)
        for entry in team_standings:
            team_info = entry.get("team", {})
            team_name = team_info.get("short_name", team_info.get("name", "Unknown"))
            rank = entry.get("ranking", entry.get("rank"))
            is_eligible = 1 if rank and rank <= (total_teams / 2) else 0

            cur.execute("""
                INSERT INTO team_tab (tournament_id, team_name, team_rank, total_teams, is_eligible)
                VALUES (?, ?, ?, ?, ?)
            """, (tournament_id, team_name, rank, total_teams, is_eligible))

            # Store members linked to this team
            for spk in team_info.get("speakers", []):
                p_id = self.get_or_create_participant(cur, spk.get("name"))
                cur.execute("""
                    INSERT INTO team_members (tournament_id, team_name, participant_id)
                    VALUES (?, ?, ?)
                """, (tournament_id, team_name, p_id))

        # 4. Ingest Outround Progression
        rounds = self.get(f"tournaments/{tournament_slug}/rounds")
        elim_rounds = [r for r in rounds if r.get("stage") == "elimination" or r.get("draw_type") == "elimination"]
        
        # Track furthest round reached per team
        stage_order = {"Win": 7, "GF": 6, "SF": 5, "QF": 4, "OF": 3, "DOF": 2, "QOF": 1}
        team_furthest = {}

        for rnd in elim_rounds:
            r_seq = rnd.get("seq")
            r_name = rnd.get("abbreviation", rnd.get("name", ""))
            
            # Map round name to standardized stage
            stage = "OF"
            if "GF" in r_name or "Final" in r_name: stage = "GF"
            elif "SF" in r_name or "Semi" in r_name: stage = "SF"
            elif "QF" in r_name or "Quarter" in r_name: stage = "QF"
            elif "Octo" in r_name: stage = "OF"
            elif "Double" in r_name: stage = "DOF"

            pairings = self.get(f"tournaments/{tournament_slug}/rounds/{r_seq}/pairings")
            for debate in pairings:
                for team in debate.get("teams", []):
                    t_name = team.get("short_name", team.get("name"))
                    current_best = team_furthest.get(t_name, ("Open", "QOF", 0))
                    
                    if stage_order.get(stage, 0) > current_best[2]:
                        team_furthest[t_name] = ("Open", stage, stage_order.get(stage, 0))

        for t_name, (cat, stage, _) in team_furthest.items():
            cur.execute("""
                INSERT INTO outrounds (tournament_id, team_name, category, is_open, furthest_stage)
                VALUES (?, ?, ?, 1, ?)
            """, (tournament_id, t_name, cat, stage))

        conn.commit()
        conn.close()
        print(f"Successfully scraped & stored data for {tournament_slug}.")