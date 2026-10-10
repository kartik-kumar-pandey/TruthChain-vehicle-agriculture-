// AI service (Python/FastAPI) - port 8000
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

// Node/Fastify backend with Neon DB - port 4000
export const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:4000";

export const MAX_IMAGE_BYTES = 10 * 1024 * 1024; // 10 MiB
export const MAX_DESCRIPTION_LENGTH = 10000;
export const MAX_CLAIM_ID_LENGTH = 128;

export const ACCEPTED_IMAGE_TYPES = [
  "image/jpeg",
  "image/jpg",
  "image/png",
  "image/webp",
  "image/bmp",
  "image/tiff",
];

export const ETHERSCAN_BASE_URL = "https://sepolia.etherscan.io";

export const AGENT_ORDER = [
  "ImageAgent",
  "SensorAgent",
  "TextAgent",
  "CrossModalAgent",
  "RiskEngine",
  "AdversarialVerifier",
  "ExplanationAgent",
  "CommunicationAgent",
] as const;

export type AgentName = (typeof AGENT_ORDER)[number];

export const PIPELINE_STATES = {
  START: "START",
  IMAGE_AGENT: "IMAGE_AGENT",
  SENSOR_AGENT: "SENSOR_AGENT",
  TEXT_AGENT: "TEXT_AGENT",
  CROSS_MODAL: "CROSS_MODAL",
  RISK_ENGINE: "RISK_ENGINE",
  ADVERSARIAL: "ADVERSARIAL",
  EXPLANATION: "EXPLANATION",
  COMMUNICATION: "COMMUNICATION",
  COMPLETE: "COMPLETE",
  BLOCKCHAIN_REGISTERED: "BLOCKCHAIN_REGISTERED",
  FAILED: "FAILED",
} as const;

export const FINAL_VERDICTS = {
  VERIFIED: "VERIFIED",
  REVIEW: "REVIEW",
  FRAUD: "FRAUD",
  PENDING: "PENDING",
  FAILED: "FAILED",
} as const;

export type FinalVerdict = (typeof FINAL_VERDICTS)[keyof typeof FINAL_VERDICTS];
