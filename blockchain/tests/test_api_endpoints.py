"""
API Integration Test for TruthChain Blockchain Audit & Verification Endpoints
"""

import sys
import unittest
from pathlib import Path

# Bootstrap Python path for ai-services and workspace root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_AI_SERVICES_DIR = _PROJECT_ROOT / "ai-services"

if str(_AI_SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(_AI_SERVICES_DIR))
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from fastapi.testclient import TestClient
from server import app


class TestTruthChainAPI(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_blockchain_status(self):
        resp = self.client.get("/api/blockchain/status")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("ledger_type", data)
        self.assertIn("database", data)

    def test_blockchain_records_list(self):
        resp = self.client.get("/api/blockchain/records?limit=5")
        self.assertEqual(resp.status_code, 200)
        records = resp.json()
        self.assertIsInstance(records, list)

    def test_verification_endpoint(self):
        # 1. First run a simulated audit
        from blockchain.audit_service import get_audit_service
        audit_service = get_audit_service()
        fake_image = b"TEST_SAMPLE_PIXELS_FOR_API_TEST"
        prediction = {
            "probabilities": {"dent": 0.88, "scratch": 0.65},
            "thresholds": {"dent": 0.35, "scratch": 0.42},
            "detected_damages": [{"type": "dent", "probability": 0.88, "threshold": 0.35}],
            "model_version": "TruthChain Vision ResNet-50",
        }
        record = audit_service.register_assessment(
            image_bytes=fake_image,
            prediction_raw=prediction,
            record_id="TC-API-TEST-001",
            vehicle_id="VIN-TEST-999",
        )

        # 2. Test GET record
        get_resp = self.client.get("/api/blockchain/record/TC-API-TEST-001")
        self.assertEqual(get_resp.status_code, 200)
        self.assertEqual(get_resp.json()["record_id"], "TC-API-TEST-001")

        # 3. Test POST verify (authentic)
        verify_resp = self.client.post("/api/blockchain/verify", json={
            "record_id": "TC-API-TEST-001",
            "prediction": prediction
        })
        self.assertEqual(verify_resp.status_code, 200)
        self.assertTrue(verify_resp.json()["verified"])
        self.assertEqual(verify_resp.json()["status"], "VERIFIED_AUTHENTIC")

        # 4. Test POST verify (tampered prediction)
        tampered = dict(prediction)
        tampered["probabilities"] = {"dent": 0.05, "scratch": 0.02}
        tampered_resp = self.client.post("/api/blockchain/verify", json={
            "record_id": "TC-API-TEST-001",
            "prediction": tampered
        })
        self.assertEqual(tampered_resp.status_code, 200)
        self.assertFalse(tampered_resp.json()["verified"])
        self.assertEqual(tampered_resp.json()["status"], "TAMPER_DETECTED")


if __name__ == "__main__":
    unittest.main()
