"""
TruthChain 2.0 — Progress Webhook Reporter Utility
==================================================
Sends real-time pipeline status updates to the Express backend SSE state map.
Mirrors AURIX's real_scanner.py report_progress pattern.
"""

import os
import requests
import json
import logging

logger = logging.getLogger(__name__)

def report_progress(claim_id: str, step: str, progress: int, message: str = "", agent_output: dict = None):
    """
    Sends a progress update webhook to the Node.js backend.
    """
    webhook_url = os.environ.get("TRUTHCHAIN_WEBHOOK_URL", "http://localhost:4000/api/internal/webhook/claim-progress")
    webhook_token = os.environ.get("TRUTHCHAIN_WEBHOOK_TOKEN", "truthchain-dev-internal-token")

    payload = {
        "claimId": claim_id,
        "step": step,
        "progress": progress,
        "message": message,
        "agentOutput": agent_output or {}
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {webhook_token}"
    }

    try:
        res = requests.post(webhook_url, json=payload, headers=headers, timeout=3)
        if res.status_code != 200:
            logger.warning(f"[Webhook] Non-200 response from backend: {res.status_code}")
    except Exception as e:
        logger.debug(f"[Webhook] Could not deliver progress event for claim {claim_id}: {e}")

if __name__ == "__main__":
    import sys
    claim_id = sys.argv[1] if len(sys.argv) > 1 else "TEST-CLAIM-001"
    print(f"Testing webhook for claim {claim_id}...")
    report_progress(claim_id, "INGESTION", 20, "Canonical hashing initiated")
    report_progress(claim_id, "VISION_ANALYSIS", 60, "ResNet-50 detection completed")
    report_progress(claim_id, "COMPLETE", 100, "Certificate issued")
    print("Done!")
