import { API_BASE_URL } from "./constants";
import type {
  ConsensusRequest,
  ConsensusResponse,
  ClaimsListResponse,
  ClaimResult,
} from "@/types/claim";
import type {
  BlockchainStatus,
  BlockchainRecord,
  BlockchainVerifyRequest,
  BlockchainVerifyResponse,
} from "@/types/blockchain";
import type {
  HealthResponse,
  ReadyResponse,
  SystemInfoResponse,
  RootResponse,
  VisionPredictResponse,
} from "@/types/api";

async function request<T>(
  path: string,
  options: RequestInit = {},
  useProxy = false,
): Promise<T> {
  const base = useProxy ? "" : API_BASE_URL;
  const url = `${base}${path}`;

  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };

  if (
    options.body &&
    !(options.body instanceof FormData) &&
    !headers["Content-Type"]
  ) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(url, {
    ...options,
    headers,
  });

  const contentType = res.headers.get("content-type") || "";
  const isJson = contentType.includes("application/json");

  if (!res.ok) {
    let detail: unknown = `${res.status} ${res.statusText}`;
    if (isJson) {
      try {
        const body = await res.json();
        detail = body.detail || body.message || body;
      } catch {
        // ignore
      }
    }
    if (typeof detail === "object" && detail !== null && "detail" in detail) {
      detail = (detail as { detail: unknown }).detail;
    }
    const message =
      typeof detail === "string" ? detail : JSON.stringify(detail);
    throw new Error(message);
  }

  if (res.status === 204) {
    return undefined as T;
  }

  if (!isJson) {
    return (await res.text()) as unknown as T;
  }

  return (await res.json()) as T;
}

export const api = {
  root(): Promise<RootResponse> {
    return request<RootResponse>("/");
  },

  health(): Promise<HealthResponse> {
    return request<HealthResponse>("/health");
  },

  ready(): Promise<ReadyResponse> {
    return request<ReadyResponse>("/ready");
  },

  systemInfo(): Promise<SystemInfoResponse> {
    return request<SystemInfoResponse>("/api/v1/system/info");
  },

  async visionPredict(file: File): Promise<VisionPredictResponse> {
    const form = new FormData();
    form.append("file", file);
    return request<VisionPredictResponse>("/api/v1/vision/predict", {
      method: "POST",
      body: form,
    });
  },

  evaluateClaim(payload: ConsensusRequest): Promise<ConsensusResponse> {
    return request<ConsensusResponse>("/api/v1/consensus/evaluate", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  evaluateAgricultureClaim(payload: Record<string, unknown>): Promise<ConsensusResponse> {
    return request<ConsensusResponse>("/api/v1/agriculture/claim", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  getClaim(claimId: string): Promise<ClaimResult> {
    return request<ClaimResult>(`/api/v1/claims/${encodeURIComponent(claimId)}`);
  },

  listClaims(): Promise<ClaimsListResponse> {
    return request<ClaimsListResponse>("/api/v1/claims");
  },

  getBlockchainStatus(): Promise<BlockchainStatus> {
    return request<BlockchainStatus>("/api/v1/blockchain/status");
  },

  listBlockchainRecords(limit = 50): Promise<BlockchainRecord[]> {
    const safeLimit = Math.max(1, Math.min(limit, 500));
    return request<BlockchainRecord[]>(
      `/api/v1/blockchain/records?limit=${safeLimit}`,
    );
  },

  getBlockchainRecord(recordId: string): Promise<BlockchainRecord> {
    return request<BlockchainRecord>(
      `/api/v1/blockchain/record/${encodeURIComponent(recordId)}`,
    );
  },

  verifyBlockchainRecord(
    payload: BlockchainVerifyRequest,
  ): Promise<BlockchainVerifyResponse> {
    return request<BlockchainVerifyResponse>("/api/v1/blockchain/verify", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  satellitePreview(payload: {
    field_geojson: Record<string, unknown>;
    start_date: string;
    end_date: string;
    max_cloud?: number;
  }): Promise<{
    status: string;
    scenes_found: number;
    best_scene?: {
      scene_id: string;
      datetime: string | null;
      cloud_cover: number | null;
      collection: string;
    };
    tile_url?: string;
    cdse_wms_url?: string;
    bbox?: number[];
    message?: string;
    meta: { processing_time_ms: number; request_id: string };
  }> {
    return request("/api/v1/satellite/preview", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
};
