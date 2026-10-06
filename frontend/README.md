# TruthChain 2.0 — Decoupled Multimodal AI & Blockchain Audit Engine

TruthChain 2.0 is a multimodal fraud detection and audit ecosystem that pairs computer vision damage assessment with an independent, decoupled **Blockchain Verification Layer** and **Neon PostgreSQL** off-chain storage.

---

## ⚡ Service Startup Commands

To launch all components of TruthChain, start each of the 4 dedicated services in a separate terminal:

| # | Service | Command | Port | Description |
|---|---|---|---|---|
| **1** | **Blockchain Node** | `cd blockchain && npx hardhat node` | `:8545` | Hardhat local Ethereum test node & contract deployment |
| **2** | **Backend API** | `cd backend && npm run dev` | `:4000` | Express REST API, auth middleware & Prisma ORM database service |
| **3** | **AI Services Engine** | `cd ai-services && uvicorn server:app --reload --port 8000` | `:8000` | Multi-agent consensus engine (Motor 8 agents, Agri 10 agents) |
| **4** | **Frontend Web Dashboard** | `cd frontend && npm run dev` | `:3000` | Next.js 16 / React 19 claim verification & audit portal |

---

## 🏛️ System Architecture & Dual-Domain Consensus Flow

```
                           USER / FARMER / INSPECTOR
                                       │
                    ┌──────────────────┴──────────────────┐
                    ▼                                     ▼
           🚗 MOTOR INSURANCE                     🌾 AGRICULTURE INSURANCE
         (Vehicle Damage & Sensor)               (Crop Photo + GPS + Sentinel-2)
                    │                                     │
                    ▼                                     ▼
           FastAPI AI Engine                     FastAPI AI Engine
        /api/motor/verify (:8000)             /api/agri/verify (:8000)
                    │                                     │
                    ▼                                     ▼
     ┌────────────────────────────┐        ┌────────────────────────────┐
     │ Motor LangGraph Pipeline   │        │ Agri LangGraph Pipeline    │
     │  1. Text Agent (LLM)       │        │  1. Text Agent (Crop NLP)  │
     │  2. Vision Agent           │        │  2. Crop RGB Agent         │
     │  3. Sensor Agent           │        │  3. Sentinel-2 Agent       │
     │  4. CrossModal Fusion      │        │  4. Weather Sensor Agent   │
     │  5. Fraud Investigation    │        │  5. CrossModal Fusion      │
     │  6. Risk Scoring Engine    │        │  6. Weather Verification   │
     │  7. Adversarial Detector   │        │  7. Loss Risk Engine       │
     │  8. Decision Consensus     │        │  8. EXIF Manipulation      │
     └──────────────┬─────────────┘        │  9. Settlement Consensus   │
                    │                      │ 10. Ledger Serialization   │
                    │                      └──────────────┬─────────────┘
                    └──────────────────┬──────────────────┘
                                       │
                                       ▼
                       ┌───────────────────────────────┐
                       │  Blockchain Audit Commitment  │
                       │   (AssessmentRegistry.sol)    │
                       └───────────────┬───────────────┘
                                       │
                                       ▼
                         Next.js 16 Dashboard UI (:3000)
```

---

## 🤖 Pre-Trained Machine Learning Models

The repository contains all pre-trained machine learning models:
- **Motor Damage Vision Model**: `ai-services/ml/models/vision/`
- **Vehicle Telemetry Anomaly Isolation Forest**: `ai-services/ml/models/sensor/sensor_isolationforest_v2.pkl`
- **Crop Disease & Health Classifier (DINOv2 / CNN)**: `ai-services/ml/models/agriculture/crop/cropagent_rgb_dinov2_v0.2_best.pt`
- **Satellite Evidence Classifier (Random Forest 77 Features)**: `ai-services/ml/models/agriculture/satellite/satellite_evidence_agent_v1_FULL.joblib` & `satellite_cropagent_v0.2.json`

---

## 📁 Repository Structure

```
TruthChain-2.0/
├── ai-services/               # FastAPI backend & LangGraph AI agent workflows
│   ├── graph/                 # LangGraph state machines (motor_graph.py & agri_graph.py)
│   ├── ml/models/             # Machine learning models (Vision, Sensor, Crop, Satellite)
│   └── server.py              # FastAPI server entry point
├── backend/                   # Express REST API, Auth, & Prisma ORM database schemas
├── blockchain/                # Solidity smart contracts (AssessmentRegistry.sol & EvidenceRegistry.sol)
├── frontend/                  # Next.js 16 (App Router) + React 19 claim & audit web interface
└── README.md                  # System overview and quick start guide
```
