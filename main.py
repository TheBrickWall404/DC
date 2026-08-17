"""
Application execution pipeline: batch ingest and debater evaluation.
"""
import os
import pandas as pd
from typing import Optional, List
from database import init_db
from scraper import TabbycatScraper
from cv_calculator import ChenCVCalculator
from config import ELIGIBLE_CLASSES

def ingest_from_excel(excel_path: str = "list of tournaments 2026.xlsx", limit: Optional[int] = None):
    if not os.path.exists(excel_path):
        print(f"Error: '{excel_path}' not found.")
        return
    
    init_db()
    df = pd.read_excel(excel_path, sheet_name="List")
    
    eligible_df = df[
        (df["speaking_class"].isin(ELIGIBLE_CLASSES)) & 
        (df["is_ineligible"].isna()) & 
        (df["to_skip"].isna())
    ]
    
    if limit:
        eligible_df = eligible_df.head(limit)
        
    print(f"Ingesting {len(eligible_df)} qualifying tournaments (>= Class S-C)...")
    for _, row in eligible_df.iterrows():
        url = str(row.get("home_url", "")).strip()
        s_class = str(row.get("speaking_class", "")).strip()
        fmt = str(row.get("format", "BP")).strip()
        
        if url.startswith("http"):
            scraper = TabbycatScraper(full_url=url)
            scraper.scrape_tournament(speaking_class=s_class, format_type=fmt)

def query_debater(names_and_aliases: List[str]):
    result = ChenCVCalculator.calculate_speaking_cv(names_and_aliases)
    if "error" in result:
        print(f"\n[QUERY RESULT] {result['error']}")
        return

    print("\n" + "="*60)
    print(f"Matched Debater     : {', '.join(result['matched_names'])}")
    print(f"Speaking CV Score   : {result['speaking_cv_score']}")
    print(f"Top 10 Achievements : {result['top_10_achievements']}")
    print("="*60)
    print("\nTournaments Evaluated:")
    for t in result["tournaments"]:
        print(f"\n* {t['tournament']} ({t['class']}) {'[PRM]' if t['is_prm'] else ''}")
        print(f"  - Furthest Open Outround: {t['open_outround']}")
        print(f"  - Team Tab Position:     {t['team_tab']}")
        print(f"  - Speaker Tab Position:  {t['speaker_tab']}")

if __name__ == "__main__":
    init_db()
    # Batch ingest the first 20 tournaments
    ingest_from_excel("list of tournaments 2026.xlsx", limit=20)