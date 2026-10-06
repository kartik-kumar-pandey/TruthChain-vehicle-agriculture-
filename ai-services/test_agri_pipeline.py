"""
Test script for TruthChain 2.0 Agriculture Domain Pipeline
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from graph.graph import app_graph

sample_claim = {
    "claim_id": "AGRI-001",
    "domain": "agriculture",
    "data": {
        "claim_id": "AGRI-001",
        "claim_text": "Wheat crop in Village Rampur, District Lucknow, field area 2 hectares. Heavy rain occurred on 2026-09-17 causing 65% crop loss.",
        "claimed_crop": "Wheat",
        "crop": "Wheat",
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
        },
        "sensor_observations": {
            "rainfall_24h_mm": 82.4,
            "rainfall_7d_mm": 146.7,
            "temperature_c": 27.3,
            "wind_speed_kmh": 18.5,
            "soil_moisture": 0.91,
            "humidity_pct": 94
        }
    }
}

print("=== STARTING AGRICULTURE PIPELINE TEST ===")
result = app_graph.invoke(sample_claim)

print("\n=== PIPELINE COMPLETED ===")
print("Claim ID:", result.get("claim_id"))
print("Domain:", result.get("domain"))
print("Final Verdict:", result.get("final_verdict"))
print("Risk Score:", result.get("risk_score"))
print("Pipeline Status:", result.get("pipeline_status"))
print("Blockchain Allowed:", result.get("blockchain_allowed"))

print("\nAgent Reports:")
for agent_name, report in result.get("agent_reports", {}).items():
    print(f"  - {agent_name}: decision={report.get('decision')}, risk={report.get('risk_score')}, evidence={report.get('evidence')}")

print("\nPipeline Steps:")
for step in result.get("steps", []):
    print(f"  - {step.get('agent') or step.get('step')}: decision={step.get('decision')}")

print("\n=== SUCCESS ===")
