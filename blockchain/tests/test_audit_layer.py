"""
Unit & Integration Tests for TruthChain Blockchain Audit Layer
==============================================================
Tests:
1. Deterministic canonical JSON serialization & hashing.
2. SHA-256 image hashing.
3. Decoupled assessment registration.
4. Tamper detection verification.
"""

import unittest
from blockchain.canonical import (
    canonical_json_bytes,
    format_canonical_prediction,
    hash_image_bytes,
    hash_prediction_dict,
    to_bytes32,
)
from blockchain.audit_service import get_audit_service


class TestBlockchainAuditLayer(unittest.TestCase):

    def test_canonical_json_determinism(self):
        # Different dictionary insertion order
        dict_a = {"scratch": 0.71, "dent": 0.82, "crack": 0.12}
        dict_b = {"crack": 0.12, "dent": 0.82, "scratch": 0.71}

        json_a = canonical_json_bytes(dict_a)
        json_b = canonical_json_bytes(dict_b)

        self.assertEqual(json_a, json_b)
        self.assertEqual(json_a, b'{"crack":0.12,"dent":0.82,"scratch":0.71}')

    def test_prediction_hashing(self):
        pred_a = {
            "probabilities": {"dent": 0.82, "scratch": 0.71, "glass_shatter": 0.05},
            "thresholds": {"dent": 0.35, "scratch": 0.42, "glass_shatter": 0.30},
            "detected_damages": [
                {"type": "dent", "probability": 0.82, "threshold": 0.35},
                {"type": "scratch", "probability": 0.71, "threshold": 0.42},
            ],
            "model_version": "truthchain-vision-v1",
        }

        # Shuffle keys in pred_b
        pred_b = {
            "model_version": "truthchain-vision-v1",
            "thresholds": {"glass_shatter": 0.30, "scratch": 0.42, "dent": 0.35},
            "detected_damages": [
                {"threshold": 0.42, "probability": 0.71, "type": "scratch"},
                {"type": "dent", "threshold": 0.35, "probability": 0.82},
            ],
            "probabilities": {"glass_shatter": 0.05, "dent": 0.82, "scratch": 0.71},
        }

        hash_a = hash_prediction_dict(pred_a)
        hash_b = hash_prediction_dict(pred_b)

        self.assertEqual(hash_a, hash_b)
        self.assertEqual(len(hash_a), 64)

    def test_image_hashing(self):
        fake_image = b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
        img_hash = hash_image_bytes(fake_image)
        self.assertEqual(len(img_hash), 64)

    def test_to_bytes32(self):
        hex_str = "a83f91c271bf2a9d1234567890abcdef1234567890abcdef1234567890abcdef"
        b32 = to_bytes32(hex_str)
        self.assertEqual(len(b32), 32)
        self.assertEqual(b32.hex(), hex_str)

    def test_audit_registration_and_tamper_detection(self):
        audit_service = get_audit_service()
        fake_image = b"TEST_VEHICLE_IMAGE_BYTES_12345"
        prediction = {
            "probabilities": {"dent": 0.82, "scratch": 0.71},
            "thresholds": {"dent": 0.35, "scratch": 0.42},
            "detected_damages": [{"type": "dent", "probability": 0.82, "threshold": 0.35}],
            "model_version": "truthchain-vision-v1",
        }

        # 1. Register assessment
        record = audit_service.register_assessment(
            image_bytes=fake_image,
            prediction_raw=prediction,
            record_id="TC-TEST-0001",
            vehicle_id="V-1001",
        )

        self.assertEqual(record["record_id"], "TC-TEST-0001")
        self.assertIn("transaction", record["blockchain"])
        self.assertTrue(record["blockchain"]["verified"])

        # 2. Verify authentic data (should pass)
        verify_ok = audit_service.verify_integrity(
            record_id="TC-TEST-0001",
            image_bytes=fake_image,
            prediction_dict=prediction,
        )
        self.assertTrue(verify_ok["verified"])
        self.assertEqual(verify_ok["status"], "VERIFIED_AUTHENTIC")

        # 3. Simulate tamper test on prediction (altered probability)
        tampered_prediction = {
            "probabilities": {"dent": 0.10, "scratch": 0.71},  # Altered dent prob
            "thresholds": {"dent": 0.35, "scratch": 0.42},
            "detected_damages": [{"type": "dent", "probability": 0.10, "threshold": 0.35}],
            "model_version": "truthchain-vision-v1",
        }
        verify_tampered = audit_service.verify_integrity(
            record_id="TC-TEST-0001",
            image_bytes=fake_image,
            prediction_dict=tampered_prediction,
        )
        self.assertFalse(verify_tampered["verified"])
        self.assertEqual(verify_tampered["status"], "TAMPER_DETECTED")
        self.assertFalse(verify_tampered["prediction_integrity"]["matched"])


if __name__ == "__main__":
    unittest.main()
