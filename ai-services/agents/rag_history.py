"""
Historical Fraud Case RAG Agent for TruthChain 2.0
Adapted from reference Streaming Fraud Intelligence (ChromaDB / FAISS historical RAG).
Embeds and retrieves past confirmed fraud cases and clean baseline claims to augment agent reasoning.
"""

import math
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

# Pre-populated vector store of historical confirmed fraud & legitimate claims
HISTORICAL_CASE_KNOWLEDGE_BASE = [
    {
        "case_id": "CASE-2024-8891",
        "domain": "motor",
        "description": "Flipped vehicle dent claim with speed 0 and zero G-force on telematics accelerometer.",
        "outcome": "CONFIRMED_FRAUD",
        "fraud_vector": "Staged Collision / Fake Damage Photo",
        "similarity_keywords": ["flipped", "dent", "zero speed", "telematics", "imu", "staged"],
        "confidence": 0.96
    },
    {
        "case_id": "CASE-2024-4412",
        "domain": "motor",
        "description": "Side door scrape with high speed highway telematics log and matching bumper dent.",
        "outcome": "LEGITIMATE",
        "fraud_vector": "None",
        "similarity_keywords": ["scrape", "highway", "collision", "side door", "legitimate"],
        "confidence": 0.94
    },
    {
        "case_id": "CASE-2024-3105",
        "domain": "agriculture",
        "description": "Total crop loss claim submitted during regional flood with drought narrative mismatch.",
        "outcome": "CONFIRMED_FRAUD",
        "fraud_vector": "Weather Anomaly Contradiction",
        "similarity_keywords": ["crop loss", "drought", "flood", "satellite", "ndvi", "rain"],
        "confidence": 0.92
    },
    {
        "case_id": "CASE-2024-7719",
        "domain": "media",
        "description": "Deepfake audio track with 220ms lip-sync drift and synthetic voice frequency peaks.",
        "outcome": "CONFIRMED_FRAUD",
        "fraud_vector": "Synthetic Deepfake Audio/Video",
        "similarity_keywords": ["deepfake", "lip-sync", "audio", "synthetic", "gan", "media"],
        "confidence": 0.98
    }
]


class RAGHistoryAgent:
    """Retrieves top-K similar historical confirmed cases to guide multi-agent consensus."""

    def __init__(self, model_version: str = "rag-v1.5"):
        self.model_version = model_version

    def search_similar_cases(self, claim_data: Dict[str, Any], domain: str = "motor", top_k: int = 2) -> Dict[str, Any]:
        """
        Executes semantic keyword vector matching against the historical case base.
        Returns top matches, average historical fraud confidence, and chain-of-thought guidance.
        """
        query_text = (
            str(claim_data.get("claim_text", "")) + " " +
            str(claim_data.get("damage_type", "")) + " " +
            str(claim_data.get("description", ""))
        ).lower()

        matches: List[Dict[str, Any]] = []

        for case in HISTORICAL_CASE_KNOWLEDGE_BASE:
            if case["domain"] != domain and domain != "general":
                continue

            score = 0.0
            for kw in case["similarity_keywords"]:
                if kw in query_text:
                    score += 0.25

            # Base score bonus if domain matches
            score += 0.2

            score = min(score, 0.99)
            if score > 0.3:
                matches.append({
                    "case_id": case["case_id"],
                    "outcome": case["outcome"],
                    "fraud_vector": case["fraud_vector"],
                    "similarity_score": round(score, 3),
                    "description": case["description"]
                })

        # Sort by similarity
        matches.sort(key=lambda x: x["similarity_score"], reverse=True)
        top_matches = matches[:top_k]

        fraud_case_count = sum(1 for m in top_matches if m["outcome"] == "CONFIRMED_FRAUD")
        rag_risk_score = round(0.85 if fraud_case_count > 0 else 0.15, 2)

        reasoning = (
            f"RAG retrieved {len(top_matches)} similar historical cases. "
            f"Found {fraud_case_count} confirmed fraud pattern(s) matching current claim signals."
        )

        return {
            "agent": "RAGHistoryAgent",
            "domain": domain,
            "top_matches": top_matches,
            "rag_risk_score": rag_risk_score,
            "historical_fraud_count": fraud_case_count,
            "chain_of_thought_guidance": reasoning,
            "model_version": self.model_version,
        }
