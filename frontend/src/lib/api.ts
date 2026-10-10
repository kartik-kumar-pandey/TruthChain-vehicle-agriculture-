import { API_BASE_URL, BACKEND_URL } from "./constants";
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

// ─── helpers ────────────────────────────────────────────────────────────────

function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("truthchain_auth_token");
}

/** Request to the Python AI service (port 8000) — no auth header needed */
async function aiRequest<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const url = `${API_BASE_URL}${path}`;

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

  const res = await fetch(url, { ...options, headers });
  return handleResponse<T>(res);
}

/** Request to the Node/Fastify backend (port 4000) — attaches Bearer token */
async function backendRequest<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = getStoredToken();
  const url = `${BACKEND_URL}${path}`;

  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  if (
    options.body &&
    !(options.body instanceof FormData) &&
    !headers["Content-Type"]
  ) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(url, { ...options, headers });
  return handleResponse<T>(res);
}

async function handleResponse<T>(res: Response): Promise<T> {
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

// ─── API surface ─────────────────────────────────────────────────────────────

export const api = {
  // ── AI Service (port 8000) ──────────────────────────────────────────────

  root(): Promise<RootResponse> {
    return aiRequest<RootResponse>("/");
  },

  health(): Promise<HealthResponse> {
    return aiRequest<HealthResponse>("/health");
  },

  ready(): Promise<ReadyResponse> {
    return aiRequest<ReadyResponse>("/ready");
  },

  systemInfo(): Promise<SystemInfoResponse> {
    return aiRequest<SystemInfoResponse>("/api/v1/system/info");
  },

  async visionPredict(file: File): Promise<VisionPredictResponse> {
    const form = new FormData();
    form.append("file", file);
    return aiRequest<VisionPredictResponse>("/api/v1/vision/predict", {
      method: "POST",
      body: form,
    });
  },

  evaluateClaim(payload: ConsensusRequest): Promise<ConsensusResponse> {
    return aiRequest<ConsensusResponse>("/api/v1/consensus/evaluate", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  evaluateAgricultureClaim(
    payload: Record<string, unknown>,
  ): Promise<ConsensusResponse> {
    return aiRequest<ConsensusResponse>("/api/v1/agriculture/claim", {
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
    return aiRequest("/api/v1/satellite/preview", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  // ── Node/Fastify Backend (port 4000) — require auth ────────────────────

  listClaims(): Promise<ClaimsListResponse> {
    return backendRequest<ClaimsListResponse>("/api/v1/claims");
  },

  getClaim(claimId: string): Promise<ClaimResult> {
    return backendRequest<ClaimResult>(
      `/api/v1/claims/${encodeURIComponent(claimId)}`,
    );
  },

  getBlockchainStatus(): Promise<BlockchainStatus> {
    return backendRequest<BlockchainStatus>("/api/v1/blockchain/status");
  },

  listBlockchainRecords(limit = 50): Promise<BlockchainRecord[]> {
    const safeLimit = Math.max(1, Math.min(limit, 500));
    return backendRequest<BlockchainRecord[]>(
      `/api/v1/blockchain/records?limit=${safeLimit}`,
    );
  },

  getBlockchainRecord(recordId: string): Promise<BlockchainRecord> {
    return backendRequest<BlockchainRecord>(
      `/api/v1/blockchain/record/${encodeURIComponent(recordId)}`,
    );
  },

  verifyBlockchainRecord(
    payload: BlockchainVerifyRequest,
  ): Promise<BlockchainVerifyResponse> {
    return backendRequest<BlockchainVerifyResponse>("/api/v1/blockchain/verify", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
};
