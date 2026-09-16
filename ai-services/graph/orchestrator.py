import time
import hashlib
from graph.graph import app_graph
from engine.webhook import report_progress

class TruthChainOrchestrator:
    def __init__(self, domain, claim_data, claim_id=None):
        self.domain = domain
        self.data = claim_data
        self.claim_id = claim_id or ("0x" + hashlib.sha256(str(claim_data).encode() + str(time.time()).encode()).hexdigest()[:32])
        self.state = "Idle"
        self.steps = []
        self.agent_reports = {}
        self.final_verdict = None
        self.fraud_score = 0
        self.evidence_hash = hashlib.sha256(str(claim_data).encode()).hexdigest()
        self.certificate = {}

    def run_pipeline(self):
        report_progress(self.claim_id, "INGESTION", 15, "Ingesting claim payload and calculating canonical hashes")

        # Build initial state for the LangGraph workflow
        initial_state = {
            "claim_id": self.claim_id,
            "domain": self.domain,
            "data": self.data,
            "state": "Idle",
            "final_verdict": "PENDING",
            "fraud_score": 0,
            "agent_reports": {},
            "certificate": {},
            "steps": [{
                "step": "Initialize",
                "status": "COMPLETE",
                "duration_sec": 0.05,
                "details": "Initialized claim workspace and generated ClaimID"
            }]
        }
        
        report_progress(self.claim_id, "TEXT_ANALYSIS", 35, "Cross-checking policy rules and claim description text")
        
        # Invoke the compiled LangGraph
        result_state = app_graph.invoke(initial_state)

        report_progress(self.claim_id, "VISION_ANALYSIS", 65, "Evaluating ResNet-50 visual damage probabilities")
        report_progress(self.claim_id, "CROSS_MODAL", 85, "Evaluating multi-agent consensus and contradiction matrices")
        
        # Populate class attributes with graph outputs
        self.state = result_state["state"]
        self.final_verdict = result_state["final_verdict"]
        self.fraud_score = result_state["fraud_score"]
        self.agent_reports = result_state["agent_reports"]
        self.certificate = result_state["certificate"]
        self.steps = result_state["steps"]
        
        output = {
            "claim_id": self.claim_id,
            "domain": self.domain,
            "state": self.state,
            "final_verdict": self.final_verdict,
            "fraud_score": self.fraud_score,
            "agent_reports": self.agent_reports,
            "certificate": self.certificate,
            "steps": self.steps
        }

        report_progress(self.claim_id, "COMPLETE", 100, "Issued blockchain certificate and saved claim results", agent_output=output)
        return output

