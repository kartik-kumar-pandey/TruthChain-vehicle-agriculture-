import type {
  ConsensusRequest,
  ConsensusResponse,
  ClaimsListResponse,
  ClaimResult,
} from "./claim";
import type {
  BlockchainStatus,
  BlockchainRecord,
  BlockchainVerifyRequest,
  BlockchainVerifyResponse,
} from "./blockchain";

export interface HealthResponse {
  status: "healthy" | "degraded" | string;
  service: string;
  version: string;
  modules: {
    vision: boolean;
    graph_orchestrator: boolean;
    risk_engine: boolean;
    blockchain: boolean;
  };
  errors?: Record<string, string | null>;
}

export interface ReadyResponse {
  status: "ready" | string;
  service: string;
  version: string;
  modules: Record<string, boolean>;
}

export interface SystemInfoResponse {
  service: string;
  version: string;
  python: string;
  modules: Record<string, boolean>;
  dependencies?: {
    scikit_learn?: string;
  };
  limits: {
    max_image_bytes: number;
    max_description_length: number;
    max_claim_id_length: number;
    max_metadata_items: number;
  };
}

export interface RootResponse {
  service: string;
  version: string;
  status: string;
  docs: string;
  health: string;
}

export interface VisionPredictResponse {
  status: string;
  result: Record<string, unknown>;
  meta: {
    filename: string;
    content_type?: string;
    processing_time_ms: number;
    request_id: string;
  };
}

export {
  ConsensusRequest,
  ConsensusResponse,
  ClaimsListResponse,
  ClaimResult,
  BlockchainStatus,
  BlockchainRecord,
  BlockchainVerifyRequest,
  BlockchainVerifyResponse,
};
