"""
Statistical & Rule-Based Detection Engine for TruthChain 2.0
Adapted from reference Multi-Agent Fraud Detection System.
Implements 6 core rule algorithms:
1. Duplicate claim detection
2. Amount anomaly (Z-score calculation)
3. Code / domain taxonomy mismatch
4. Velocity fraud (high claim frequency in short windows)
5. Provider / repair workshop outlier scoring
6. Impossible scenario & sensor/telematics physical contradiction
"""

import math
import logging
from typing import Dict, Any, List, Tuple

logger = logging.getLogger(__name__)

# Domain baseline statistics for Z-score calculation
DOMAIN_BASELINE_STATS = {
    "motor": {"mean_amount": 3500.0, "std_amount": 1200.0, "high_threshold": 15000.0},
    "agriculture": {"mean_amount": 8000.0, "std_amount": 2500.0, "high_threshold": 30000.0},
    "media": {"mean_amount": 5000.0, "std_amount": 1800.0, "high_threshold": 20000.0},
    "general": {"mean_amount": 4000.0, "std_amount": 1500.0, "high_threshold": 25000.0},
}


class RuleEngineAgent:
    """Statistical and Rule-Based Detection Agent for TruthChain 2.0"""

    def __init__(self, model_version: str = "rules-v2.0"):
        self.model_version = model_version

    def evaluate(self, claim_data: Dict[str, Any], domain: str = "motor") -> Dict[str, Any]:
        """
        Executes all 6 rules against the incoming claim data and generates
        a quantitative rule risk score, list of triggered flags, and feature contributions.
        """
        domain_key = domain.lower() if domain.lower() in DOMAIN_BASELINE_STATS else "general"
        stats = DOMAIN_BASELINE_STATS[domain_key]

        flags: List[str] = []
        explanations: List[str] = []
        contributions: Dict[str, float] = {}
        total_weight = 0.0

        # --- Rule 1: Duplicate Claims ---
        is_dup, dup_expl, dup_score = self._check_duplicate(claim_data)
        if is_dup:
            flags.append("DUPLICATE_CLAIM")
            explanations.append(dup_expl)
            contributions["duplicate_claim"] = dup_score
            total_weight += dup_score

        # --- Rule 2: Amount Anomaly (Z-score) ---
        is_anomaly, anomaly_expl, z_score, anomaly_weight = self._check_amount_anomaly(claim_data, stats)
        if is_anomaly:
            flags.append("AMOUNT_ANOMALY")
            explanations.append(anomaly_expl)
            contributions["amount_anomaly"] = anomaly_weight
            total_weight += anomaly_weight

        # --- Rule 3: Taxonomy / Code Mismatch ---
        is_mismatch, mismatch_expl, mismatch_weight = self._check_code_mismatch(claim_data, domain_key)
        if is_mismatch:
            flags.append("TAXONOMY_MISMATCH")
            explanations.append(mismatch_expl)
            contributions["taxonomy_mismatch"] = mismatch_weight
            total_weight += mismatch_weight

        # --- Rule 4: Velocity Fraud ---
        is_velocity, velocity_expl, velocity_weight = self._check_velocity_fraud(claim_data)
        if is_velocity:
            flags.append("VELOCITY_FRAUD")
            explanations.append(velocity_expl)
            contributions["velocity_fraud"] = velocity_weight
            total_weight += velocity_weight

        # --- Rule 5: Provider / Entity Outlier ---
        is_provider_outlier, provider_expl, provider_weight = self._check_provider_outlier(claim_data)
        if is_provider_outlier:
            flags.append("PROVIDER_OUTLIER")
            explanations.append(provider_expl)
            contributions["provider_outlier"] = provider_weight
            total_weight += provider_weight

        # --- Rule 6: Impossible Physical Scenario ---
        is_impossible, imp_expl, imp_weight = self._check_impossible_scenario(claim_data)
        if is_impossible:
            flags.append("IMPOSSIBLE_SCENARIO")
            explanations.append(imp_expl)
            contributions["impossible_scenario"] = imp_weight
            total_weight += imp_weight

        # Normalized risk score in [0.0, 1.0]
        norm_risk_score = round(min(total_weight / 100.0, 1.0), 4)

        return {
            "agent": "RuleEngineAgent",
            "domain": domain,
            "risk_score": norm_risk_score,
            "rules_triggered_count": len(flags),
            "flags": flags,
            "explanations": explanations,
            "feature_contributions": contributions,
            "model_version": self.model_version,
            "baseline_stats_used": stats,
        }

    def _check_duplicate(self, data: Dict[str, Any]) -> Tuple[bool, str, float]:
        dup_count = data.get("duplicate_count", 1)
        prev_claim_id = data.get("previous_matching_claim_id", "")
        if dup_count > 1 or prev_claim_id or data.get("is_duplicate", False):
            expl = f"Duplicate claim match detected (Count: {dup_count}, Previous ID: '{prev_claim_id or 'MATCH'}')"
            return True, expl, 25.0
        return False, "", 0.0

    def _check_amount_anomaly(self, data: Dict[str, Any], stats: Dict[str, float]) -> Tuple[bool, str, float, float]:
        amount = float(data.get("claim_amount", data.get("estimated_cost", 0.0)))
        if amount <= 0:
            return False, "", 0.0, 0.0

        mean = stats["mean_amount"]
        std = stats["std_amount"]
        z_score = (amount - mean) / std if std > 0 else 0.0

        if abs(z_score) >= 2.5 or amount >= stats["high_threshold"]:
            weight = 30.0 if abs(z_score) >= 3.0 else 20.0
            expl = f"Claim amount ${amount:,.2f} is anomalous (Z-score: {z_score:.2f}σ from baseline ${mean:,.2f})"
            return True, expl, z_score, weight
        return False, "", z_score, 0.0

    def _check_code_mismatch(self, data: Dict[str, Any], domain: str) -> Tuple[bool, str, float]:
        proc_code = str(data.get("procedure_code", data.get("damage_type", "")))
        diag_code = str(data.get("diagnosis_code", data.get("description", "")))
        is_mismatch = data.get("is_code_mismatch", False)

        if is_mismatch or ("scratch" in proc_code.lower() and "total_loss" in diag_code.lower()):
            expl = f"Taxonomy mismatch between claimed damage ({proc_code}) and reported event ({diag_code})"
            return True, expl, 15.0
        return False, "", 0.0

    def _check_velocity_fraud(self, data: Dict[str, Any]) -> Tuple[bool, str, float]:
        claims_7d = data.get("claimant_claims_7d", data.get("claims_in_7_days", 1))
        claims_30d = data.get("claimant_claims_30d", data.get("claims_in_30_days", 1))

        if claims_7d >= 3 or claims_30d >= 6:
            expl = f"Velocity threshold exceeded: {claims_7d} claims in past 7 days, {claims_30d} claims in 30 days"
            return True, expl, 20.0
        return False, "", 0.0

    def _check_provider_outlier(self, data: Dict[str, Any]) -> Tuple[bool, str, float]:
        provider_risk = data.get("provider_risk_ratio", 1.0)
        is_outlier = data.get("is_provider_outlier", False)

        if is_outlier or provider_risk > 2.2:
            expl = f"Repair facility/provider billing risk ratio ({provider_risk:.2f}x) significantly exceeds peer group"
            return True, expl, 15.0
        return False, "", 0.0

    def _check_impossible_scenario(self, data: Dict[str, Any]) -> Tuple[bool, str, float]:
        speed = data.get("telematics_speed", data.get("speed_mph", 0))
        imu = data.get("imu_g_force", 0.0)
        impact_claimed = "collision" in str(data.get("claim_text", "")).lower() or "dent" in str(data.get("claim_text", "")).lower()

        if impact_claimed and speed == 0 and imu < 0.1 and data.get("has_telematics", False):
            expl = "Impossible physical scenario: Claim reports collision damage but telematics records 0 mph and zero G-force"
            return True, expl, 30.0
        elif data.get("is_impossible_scenario", False):
            expl = f"Impossible scenario flag: {data.get('impossible_reason', 'Physical condition mismatch')}"
            return True, expl, 30.0
        return False, "", 0.0
