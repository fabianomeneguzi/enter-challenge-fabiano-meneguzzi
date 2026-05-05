import sys
import io

# Force UTF-8 encoding for console output on Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import json

from rivet_runner import run_rivet_workflows
from document_generator import generate_document
from returns_calculator import generate_returns_csv
from chart_generator import generate_performance_chart
from macro_researcher import fetch_macro_news
from recommender import generate_recommendations


def _first_client_id() -> str:
    with open("clients.json", encoding="utf-8") as f:
        clients = json.load(f)
    if not clients:
        return ""
    return clients[0]["id"]


if __name__ == "__main__":
    client_id = _first_client_id()
    if not client_id:
        print("Error: clients.json must contain at least one client.")
        sys.exit(1)

    # 1. Run Rivet to extract positions and risk profile
    success_pos = run_rivet_workflows("extract_positions", client_id)
    success_risk = run_rivet_workflows("extract_riskprofile", client_id)
    
    if success_pos:
        # 2. Python fetches APIs, calculates returns and generates performance_summary.json
        chart_data = generate_returns_csv()
        
        # 3. Generate performance chart image
        generate_performance_chart(chart_data)
        
        # 4. Fetch dynamic macro news
        fetch_macro_news()
        
        # 5. Generate dynamic recommendations based on profile and performance
        generate_recommendations()
        
        # 6. Run Rivet to generate the letter, injecting all JSONs
        success_challenge = run_rivet_workflows("main_challenge", client_id)
        
        if success_challenge:
            # 7. Generate Word Document
            generate_document()
