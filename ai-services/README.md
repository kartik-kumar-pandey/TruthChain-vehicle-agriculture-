# 🤖 `ai-services` — Centralized AI Ecosystem

The `ai-services` directory consolidates all artificial intelligence, computer vision, multi-agent consensus, and risk assessment components into a single, self-contained module.

---

## 🏛️ Module Architecture

```
ai-services/
├── server.py                   # FastAPI server entrypoint for AI microservice
├── config.py                   # Model weights, environment & server configuration
├── requirements.txt            # Python dependencies for AI components
├── vision/                     # Computer Vision (ResNet-50) damage assessment
│   ├── inference.py
│   └── test_inference.py
├── agents/                     # Specialized AI Agents & Risk Engines
│   ├── cross_modal_agent.py    # Cross-modal fusion agent
│   ├── image_agent.py          # Vision damage evaluation agent
│   ├── sensor_agent.py         # Telematics & sensor anomaly agent
│   ├── text_agent.py           # Natural language claim explanation agent
│   ├── risk_engine.py          # Multi-factor risk calculation engine
│   ├── rule_engine.py          # Policy & rule checking engine
│   ├── explanation_agent.py    # Automated narrative generator
│   ├── policy_checker.py       # Insurance policy validation
│   ├── rag_history.py          # RAG historical claims retrieval agent
│   ├── communication_agent.py   # User & stakeholder notification agent
│   └── adversarial_verifier.py # Anti-fraud cross-validation agent
├── graph/                      # LangGraph Multi-Agent Orchestration
│   ├── state.py                # Graph state definitions
│   ├── graph.py                # State graph definition
│   ├── orchestrator.py         # Workflow runner
│   └── blockchain_node.py      # Immutable hash generation node
├── domains/                    # Domain-Specific Claim Handlers
│   └── scenarios.py            # Motor, Agriculture, Media scenarios
├── ml/                         # Machine Learning Models & Training
│   ├── models/                 # Model artifacts (.pth, .pkl, JSON configs)
│   │   ├── vision/
│   │   └── sensor/
│   └── training/               # Model training & ablation study scripts
└── webhook.py                  # Integration webhook handler
```

---

## 🚀 How to Run

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run Standalone Microservice
```bash
python server.py
# Server starts at http://0.0.0.0:8000 (configurable via config.py or env)
```

### 3. Import in Python Code
```python
from vision.inference import VehicleDamageClassifier
from graph.orchestrator import run_claim_consensus

# Initialize damage classifier
classifier = VehicleDamageClassifier()

# Run full multi-agent consensus workflow
consensus_res = run_claim_consensus(
    claim_id="CLM-9912",
    description="Side collision during thunderstorm",
    metadata={"vehicle_speed": 45}
)
```
