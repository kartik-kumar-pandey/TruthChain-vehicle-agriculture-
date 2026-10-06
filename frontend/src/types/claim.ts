import type { AgentReports } from "./agents";

export interface BlockchainCertificate {
  claim_id: string;
  record_id?: string;
  image_hash?: string;
  prediction_hash?: string;
  model_version?: string;
  transaction_hash?: string | null;
  block_number?: number | null;
  contract_address?: string;
  network?: string;
  status?: string;
  reused?: boolean;
  registered_at?: number | null;
  recorder?: string;
}

export interface PipelineStep {
  agent: string;
  decision?: string;
  risk_score?: number;
  confidence?: number;
  status?: string;
  transaction_hash?: string;
  block_number?: number;
  claim_id?: string;
}

export interface ClaimInputData {
  image?: string;
  image_path?: string;
  image_url?: string;
  sensor?: Record<string, number>;
  sensor_data?: Record<string, number>;
  telemetry?: Record<string, number>;
  text?: string;
  claim_text?: string;
  [key: string]: unknown;
}

export interface ClaimResult {
  claim_id: string;
  domain?: string;
  data?: ClaimInputData;
  state?: string;
  final_verdict?: string;
  fraud_score?: number;
  risk_score?: number;
  confidence?: number;
  preliminary_verdict?: string;
  preliminary_fraud_score?: number;
  agent_reports?: AgentReports;
  pipeline_status?: string;
  pipeline_failures?: string[];
  failed_agents?: string[];
  required_agents_complete?: boolean;
  blockchain_allowed?: boolean;
  blockchain_reason?: string;
  certificate?: BlockchainCertificate;
  explanation?: import("./agents").ExplanationAgentReport;
  communication?: import("./agents").CommunicationAgentReport;
  steps?: PipelineStep[];
  meta?: Record<string, unknown>;
  claim_metadata?: Record<string, unknown>;
}

export interface ConsensusRequest {
  claim_id: string;
  description: string;
  metadata?: Record<string, unknown>;
}

export interface ConsensusResponse {
  status: string;
  data: ClaimResult;
  meta: {
    claim_id: string;
    processing_time_ms: number;
    request_id: string;
  };
}

export interface ClaimsListResponse {
  count: number;
  claims: ClaimResult[];
}

export type ClaimFilter =
  | "ALL"
  | "VERIFIED"
  | "REVIEW"
  | "FRAUD"
  | "BLOCKCHAIN_REGISTERED"
  | "FAILED";

export function verdictToFilter(verdict?: string): ClaimFilter {
  if (!verdict) return "ALL";
  switch (verdict.toUpperCase()) {
    case "VERIFIED":
      return "VERIFIED";
    case "REVIEW":
      return "REVIEW";
    case "FRAUD":
      return "FRAUD";
    case "FAILED":
      return "FAILED";
    default:
      return "ALL";
  }
}
