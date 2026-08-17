"""
Main driver interface.
"""
from database import init_db
from scraper import TabbycatScraper
from cv_calculator import ChenCVCalculator

def main():
    # 1. Initialize local DB
    init_db()

    # 2. Example scraper execution
    scraper = TabbycatScraper(base_url="https://tab.example.com", api_token=None)
    
    # Ingest tournament (Class S-AAA)
    # scraper.scrape_tournament("sample-iv-2025", speaking_class="S-AAA", format_type="BP")

    # 3. Query participant CV by name & nicknames
    query_names = ["Jane Doe", "JD", "Jane D."]
    result = ChenCVCalculator.calculate_speaking_cv(query_names)

    print("\n--- CHEN CV RESULT ---")
    if "error" in result:
        print(result["error"])
    else:
        print(f"Matched Debater: {', '.join(result['matched_names'])}")
        print(f"Final Speaking CV Score: {result['speaking_cv_score']}")
        print(f"Top 10 Counted Achievements: {result['top_10_speaking_achievements']}")
        print("\nTournament Breakdown:")
        for t in result["tournaments"]:
            print(f" - {t['tournament']} ({t['class']}) | Outround: {t['open_outround']} | Team Tab: {t['team_tab']} | Speaker Tab: {t['speaker_tab']}")

if __name__ == "__main__":
    main()