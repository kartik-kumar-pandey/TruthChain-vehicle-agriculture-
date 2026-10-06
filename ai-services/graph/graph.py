"""
TruthChain 2.0 - Multi-Domain LangGraph Unified Router
------------------------------------------------------

Dispatches incoming claim state to domain-specific LangGraphs:
    1. domain == "motor" -> Motor Insurance Pipeline
    2. domain == "agriculture" -> Agriculture Insurance Pipeline
"""

from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

from graph.motor_graph import app_graph as motor_graph
from graph.agri_graph import app_graph as agri_graph


class UnifiedGraph:
    """
    Multi-domain router wrapping motor and agriculture graphs.
    Provides standard `.invoke(state)` interface compatible with LangGraph.
    """

    def invoke(self, state: Dict[str, Any], config: Any = None) -> Dict[str, Any]:
        domain = str(state.get("domain", "")).strip().lower()
        data = state.get("data", {})
        if not isinstance(data, dict):
            data = {}

        # Infer domain from fields if not explicitly specified
        if not domain:
            if (
                data.get("crop")
                or data.get("claimed_crop")
                or data.get("crop_type")
                or data.get("field_geojson")
                or data.get("sown_area")
                or data.get("field_area_hectares")
            ):
                domain = "agriculture"
            else:
                domain = "motor"

        logger.info(f"UnifiedGraph routing claim {state.get('claim_id')} to domain: {domain}")

        if domain == "agriculture" or "agri" in domain:
            return agri_graph.invoke(state, config=config)
        else:
            return motor_graph.invoke(state, config=config)


app_graph = UnifiedGraph()
graph = app_graph

__all__ = ["app_graph", "graph", "UnifiedGraph"]