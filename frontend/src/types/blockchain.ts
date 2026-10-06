export interface BlockchainStatus {
  blockchain_connected?: boolean;
  rpc_url?: string;
  contract_address?: string;
  ledger_type?: string;
  database?: {
    status?: string;
    total_assessments?: number;
    [key: string]: unknown;
  };
  total_simulated_assessments?: number;
  connected?: boolean;
  chain_id?: number;
  network?: string;
  recorder_address?: string;
  balance_wei?: number;
  balance_eth?: number;
  [key: string]: unknown;
}

export interface BlockchainRecord {
  record_id?: string;
  claim_id?: string;
  vehicle_id?: string;
  image?: {
    storage_uri?: string;
    sha256?: string;
  };
  vision?: {
    model?: string;
    detections?: string[];
    probabilities?: Record<string, number>;
    thresholds?: Record<string, number>;
  };
  blockchain?: {
    network?: string;
    contract?: string;
    transaction?: string;
    block_number?: number;
    prediction_hash?: string;
    image_hash?: string;
    timestamp?: number;
    verified?: boolean;
  };
  canonical_prediction?: Record<string, unknown>;
  created_at?: string;
  image_hash?: string;
  prediction_hash?: string;
  model_version?: string;
  timestamp?: number;
  recorder?: string;
  contract_address?: string;
  transaction_hash?: string;
  block_number?: number;
  network?: string;
  status?: string;
  [key: string]: unknown;
}

export interface IntegrityCheck {
  matched: boolean;
  expected_hash: string;
  computed_hash: string;
}

export interface BlockchainVerifyResponse {
  record_id: string;
  verified: boolean;
  status: string;
  message?: string;
  image_integrity?: IntegrityCheck;
  prediction_integrity?: IntegrityCheck;
  model_version?: string;
  blockchain?: {
    network?: string;
    transaction?: string;
    block_number?: number;
    timestamp?: number;
  };
  is_match?: boolean;
  image_hash_match?: boolean;
  prediction_hash_match?: boolean;
  supplied_image_hash?: string;
  supplied_prediction_hash?: string;
  on_chain_image_hash?: string;
  on_chain_prediction_hash?: string;
  registered_at?: number;
  on_chain_timestamp?: number;
  recorder?: string;
}

export interface BlockchainVerifyRequest {
  record_id: string;
  image_url?: string;
  prediction?: Record<string, unknown>;
}
