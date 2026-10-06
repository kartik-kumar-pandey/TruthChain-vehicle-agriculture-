export interface VisionPrediction {
  probability: number;
  threshold: number;
  detected: boolean;
}

export interface BaseAgentReport {
  agent: string;
  domain: string;
  decision: string;
  confidence?: number;
  risk_score?: number;
  evidence?: string[];
  contradictions?: string[];
  model_version?: string;
  processing_time_ms?: number;
}

export interface ImageAgentReport extends BaseAgentReport {
  agent: "ImageAgent";
  damage_detected?: boolean;
  detected_damage?: string[];
  num_detected?: number;
  predictions?: Record<string, VisionPrediction>;
}

export interface SensorFeatures {
  speed?: number;
  accel_x?: number;
  accel_y?: number;
  accel_z?: number;
  acceleration_magnitude?: number;
  speed_change?: number;
  acceleration_change?: number;
  gps_distance?: number;
  gps_speed?: number;
  speed_gps_difference?: number;
  speed_gps_ratio?: number;
}

export interface SensorAgentReport extends BaseAgentReport {
  agent: "SensorAgent";
  anomaly?: boolean;
  model_score?: number;
  features?: SensorFeatures;
}

export interface ExtractedTextInfo {
  incident_type?: string;
  damage_types?: string[];
  time_mentions?: string[];
  location_mentions?: string[];
  vehicle_mentions?: string[];
  action_mentions?: string[];
}

export interface TextAgentReport extends BaseAgentReport {
  agent: "TextAgent";
  extracted_information?: ExtractedTextInfo;
  summary?: string;
  signals?: string[];
  text_length?: number;
}

export interface CrossModalAgentReport extends BaseAgentReport {
  agent: "CrossModalAgent";
  agreement_state?: string;
  modal_results?: {
    image_decision?: string;
    sensor_decision?: string;
    text_decision?: string;
  };
}

export interface RiskComponents {
  image_fraud_signal?: number;
  sensor_fraud_signal?: number;
  text_fraud_signal?: number;
  cross_modal_fraud_signal?: number;
}

export interface RiskEngineReport extends BaseAgentReport {
  agent: "RiskEngine";
  fraud_score: number;
  weighted_risk?: number;
  final_verdict?: string;
  formula_components?: RiskComponents;
  raw_agent_scores?: Record<string, number>;
  weights?: Record<string, number>;
  active_weight_total?: number;
  risk_stage?: string;
  pipeline_status?: string;
  pipeline_failures?: string[];
  evidence_status?: string;
}

export interface AdversarialVerifierReport extends BaseAgentReport {
  agent: "AdversarialVerifier";
  final_verdict?: string;
  fraud_score?: number;
  preliminary_risk?: number;
  adversarial_flagged?: boolean;
  audited_evidence?: string[];
  audited_agents?: string[];
  failed_agents?: string[];
  pipeline_status?: string;
  pipeline_failures?: string[];
}

export interface ExplanationAgentReport extends BaseAgentReport {
  agent: "ExplanationAgent";
  final_verdict?: string;
  executive_summary?: string;
  key_highlights?: string[];
  recommended_actions?: string[];
  contradiction_count?: number;
  verifier_decision?: string;
  verifier_final_verdict?: string;
  pipeline_status?: string;
  pipeline_failures?: string[];
}

export interface CommunicationAgentReport extends BaseAgentReport {
  agent: "CommunicationAgent";
  claim_id?: string;
  final_verdict?: string;
  subject?: string;
  message_body?: string;
  recipient?: string;
  fraud_score?: number;
  contradiction_count?: number;
  explanation_summary?: string;
  evidence_highlight_count?: number;
  pipeline_status?: string;
  pipeline_warnings?: string[];
}

export type AgentReport =
  | ImageAgentReport
  | SensorAgentReport
  | TextAgentReport
  | CrossModalAgentReport
  | RiskEngineReport
  | AdversarialVerifierReport
  | ExplanationAgentReport
  | CommunicationAgentReport;

export type AgentReports = {
  ImageAgent?: ImageAgentReport;
  SensorAgent?: SensorAgentReport;
  TextAgent?: TextAgentReport;
  CrossModalAgent?: CrossModalAgentReport;
  RiskEngine?: RiskEngineReport;
  AdversarialVerifier?: AdversarialVerifierReport;
  ExplanationAgent?: ExplanationAgentReport;
  CommunicationAgent?: CommunicationAgentReport;
};
