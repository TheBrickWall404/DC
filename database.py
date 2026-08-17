"""
Database schema creation and connection managers for SQLite.
"""
import sqlite3
from config import DB_FILE

def get_connection():
    return sqlite3.connect(DB_FILE)

def init_db():
    conn = get_connection()
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
        avg_speaks REAL,
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
        avg_speaks REAL,
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
        stage TEXT,
        FOREIGN KEY(tournament_id) REFERENCES tournaments(id)
    );
    """)

    conn.commit()
    conn.close()