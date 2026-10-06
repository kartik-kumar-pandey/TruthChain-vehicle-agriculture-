"""
Test FastAPI server Agriculture claim endpoint
"""

import sys
from pathlib import Path
from fastapi.testclient import TestClient

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from server import app

client = TestClient(app)

print("=== TESTING FASTAPI AGRICULTURE CLAIM ENDPOINT ===")

request_payload = {
    "claim_id": "AGRI-001",
    "domain": "agriculture",
    "claim_text": "Wheat crop in Village Rampur, District Lucknow, field area 2 hectares. Heavy rain occurred on 2026-09-17 causing 65% crop loss.",
    "claimed_crop": "Wheat",
    "field_area_hectares": 2.0,
    "event": "Heavy rain",
    "event_date": "2026-09-17",
    "location": "Village Rampur, District Lucknow",
    "claimed_loss_percent": 65,
    "image": "data/uploaded_crop_image.jpg",
    "field_geojson": {
        "type": "Polygon",
        "coordinates": [
            [
                [80.1922, 26.4522],
                [80.1922, 26.4513],
                [80.1912, 26.4513],
                [80.1912, 26.4522],
                [80.1922, 26.4522]
            ]
        ]
    }
}

response = client.post("/api/v1/agriculture/claim", json=request_payload)

print("HTTP Status Code:", response.status_code)
if response.status_code == 200:
    res_data = response.json()
    print("Response Status:", res_data.get("status"))
    graph_res = res_data.get("data", {})
    print("Claim ID:", graph_res.get("claim_id"))
    print("Final Verdict:", graph_res.get("final_verdict"))
    print("Risk Score:", graph_res.get("risk_score"))
    print("Pipeline Status:", graph_res.get("pipeline_status"))
    print("\nSUCCESS! Server API endpoint works perfectly.")
else:
    print("Error Detail:", response.text)
