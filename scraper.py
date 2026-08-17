"""
Scrapes Tabbycat instances and stores speaker tabs, team tabs, and Open outrounds.
"""
import re
import requests
from urllib.parse import urlparse
from typing import Optional
from config import ELIGIBLE_CLASSES, PRM_KEYWORDS, STAGE_HIERARCHY
from database import get_connection
from name_matcher import normalize_name

class TabbycatScraper:
    def __init__(self, full_url: str, api_token: Optional[str] = None):
        parsed = urlparse(full_url.strip())
        self.domain = f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
        
        path_parts = [p for p in parsed.path.strip("/").split("/") if p]
        self.slug = path_parts[0] if path_parts else ""
        
        self.headers = {
            "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/119.0"
        }
        if api_token:
            self.headers["Authorization"] = f"Token {api_token}"

    def fetch_json(self, endpoint: str):
        url = f"{self.domain}/api/v1/{endpoint.lstrip('/')}"
        res = requests.get(url, headers=self.headers, timeout=12)
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

    def scrape_tournament(self, speaking_class: str, format_type: str = "BP", override_slug: Optional[str] = None):
        slug = override_slug or self.slug
        if not slug:
            print(f"[SKIP] Invalid slug for URL {self.domain}")
            return

        if speaking_class not in ELIGIBLE_CLASSES:
            return

        conn = get_connection()
        cur = conn.cursor()

        try:
            # 1. Fetch metadata
            tourn_name = slug
            date = ""
            try:
                meta = self.fetch_json(f"tournaments/{slug}")
                tourn_name = meta.get("name", slug)
                date = meta.get("starts_at", "")
            except Exception:
                pass

            is_prm = 1 if any(k in slug.lower() or k in tourn_name.lower() for k in PRM_KEYWORDS) else 0

            cur.execute("""
                INSERT OR REPLACE INTO tournaments (slug, name, date, speaking_class, format, is_prm)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (slug, tourn_name, date, speaking_class, format_type, is_prm))
            tourn_id = cur.execute("SELECT id FROM tournaments WHERE slug = ?", (slug,)).fetchone()[0]

            # 2. Ingest Speaker Tab
            speaker_scores = {}
            spk_data = self.fetch_json(f"tournaments/{slug}/speakers/standings")
            total_spks = len(spk_data)

            for entry in spk_data:
                spk_obj = entry.get("speaker", {})
                raw_name = spk_obj.get("name", "")
                p_id = self.get_or_create_participant(cur, raw_name)
                
                rank = entry.get("ranking", entry.get("rank", 999))
                avg_speaks = entry.get("metrics", {}).get("average_score", 0.0)
                speaker_scores[p_id] = avg_speaks

                is_eligible = 1 if rank <= (total_spks / 2) else 0
                cur.execute("""
                    INSERT INTO speaker_tab (tournament_id, participant_id, speaker_rank, total_speakers, avg_speaks, is_eligible)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (tourn_id, p_id, rank, total_spks, avg_speaks, is_eligible))

            # 3. Ingest Team Tab & Rosters
            team_data = self.fetch_json(f"tournaments/{slug}/teams/standings")
            total_teams = len(team_data)

            for entry in team_data:
                team_obj = entry.get("team", {})
                team_name = team_obj.get("short_name", team_obj.get("name", "Unknown"))
                rank = entry.get("ranking", entry.get("rank", 999))
                is_eligible = 1 if rank <= (total_teams / 2) else 0

                cur.execute("""
                    INSERT INTO team_tab (tournament_id, team_name, team_rank, total_teams, is_eligible)
                    VALUES (?, ?, ?, ?, ?)
                """, (tourn_id, team_name, rank, total_teams, is_eligible))

                for spk in team_obj.get("speakers", []):
                    p_id = self.get_or_create_participant(cur, spk.get("name", ""))
                    p_avg = speaker_scores.get(p_id, 0.0)
                    cur.execute("""
                        INSERT INTO team_members (tournament_id, team_name, participant_id, avg_speaks)
                        VALUES (?, ?, ?, ?)
                    """, (tourn_id, team_name, p_id, p_avg))

            # 4. Ingest Outrounds (Open Outrounds prioritised)
            rounds = self.fetch_json(f"tournaments/{slug}/rounds")
            elim_rounds = [r for r in rounds if r.get("stage") == "elimination" or r.get("draw_type") == "elimination"]
            team_furthest = {}

            for rnd in elim_rounds:
                seq = rnd.get("seq")
                r_name = rnd.get("abbreviation", rnd.get("name", "")).upper()
                stage = "OF"
                if "GF" in r_name or "FINAL" in r_name: stage = "GF"
                elif "SF" in r_name or "SEMI" in r_name: stage = "SF"
                elif "QF" in r_name or "QUARTER" in r_name: stage = "QF"
                elif "OCTO" in r_name: stage = "OF"
                elif "DOUBLE" in r_name: stage = "DOF"

                pairings = self.fetch_json(f"tournaments/{slug}/rounds/{seq}/pairings")
                for debate in pairings:
                    for team in debate.get("teams", []):
                        t_name = team.get("short_name", team.get("name"))
                        _, curr_val = team_furthest.get(t_name, ("QOF", 0))
                        if STAGE_HIERARCHY.get(stage, 0) > curr_val:
                            team_furthest[t_name] = (stage, STAGE_HIERARCHY.get(stage, 0))

            for t_name, (stage, _) in team_furthest.items():
                cur.execute("""
                    INSERT INTO outrounds (tournament_id, team_name, category, is_open, stage)
                    VALUES (?, ?, 'Open', 1, ?)
                """, (tourn_id, t_name, stage))

            conn.commit()
            print(f"[STORED] {slug} (Class: {speaking_class})")

        except Exception as e:
            print(f"[SKIP/ERROR] {slug}: {e}")
        finally:
            conn.close()