"use client";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { SectionHeader, Alert, Skeleton, Separator } from "@/components/ui/primitives";
import {
  Cpu,
  Activity,
  Eye,
  ShieldAlert,
  Gauge,
  Database,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  RefreshCw,
  BrainCircuit,
  Blocks,
  Link2,
} from "lucide-react";
import {
  useHealth,
  useReady,
  useSystemInfo,
  useBlockchainStatus,
} from "@/hooks/useTruthChain";
import { Button } from "@/components/ui/button";
import { API_BASE_URL } from "@/lib/constants";
import { cn } from "@/lib/utils";
import { Copyable } from "@/components/ui/copyable";

type ModuleKey =
  | "vision"
  | "graph_orchestrator"
  | "risk_engine"
  | "blockchain";

const MODULE_META: Record<
  ModuleKey,
  { label: string; icon: React.ComponentType<{ className?: string }>; accent: string }
> = {
  vision: { label: "Vision Inference", icon: Eye, accent: "cyan" },
  graph_orchestrator: {
    label: "Graph Orchestrator",
    icon: BrainCircuit,
    accent: "indigo",
  },
  risk_engine: {
    label: "Risk Engine",
    icon: Gauge,
    accent: "amber",
  },
  blockchain: {
    label: "Blockchain Service",
    icon: Blocks,
    accent: "purple",
  },
};

function healthStatusColor(status?: string): string {
  if (!status) return "bg-slate-500";
  if (status === "healthy" || status === "ready") return "bg-emerald-400";
  if (status === "degraded") return "bg-amber-400";
  return "bg-rose-400";
}

export default function SystemPage() {
  const health = useHealth();
  const ready = useReady();
  const system = useSystemInfo();
  const bc = useBlockchainStatus();

  const modules = health.data?.modules as Record<ModuleKey, boolean> | undefined;

  return (
    <div className="space-y-6">
      <SectionHeader
        eyebrow="Runtime Diagnostics"
        title="System"
        description="AI service health, module readiness, API limits, and blockchain connectivity. Refreshes automatically every 15 seconds."
        actions={
          <div className="flex items-center gap-2 flex-wrap">
            <Badge variant="info" className="font-mono text-[10px]">
              /health · /ready · /api/v1/system/info
            </Badge>
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                health.refetch();
                ready.refetch();
                system.refetch();
                bc.refetch();
              }}
              disabled={health.isFetching || system.isFetching}
            >
              <RefreshCw
                className={cn(
                  "h-3.5 w-3.5",
                  health.isFetching && "animate-spin",
                )}
              />
              Refresh
            </Button>
          </div>
        }
      />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card
          className={cn(
            "overflow-hidden",
            health.data?.status === "healthy"
              ? "border-emerald-800/50"
              : health.data?.status === "degraded"
                ? "border-amber-800/50"
                : "border-slate-800",
          )}
        >
          <CardContent className="p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                  Service Health
                </div>
                <div className="mt-2 flex items-center gap-2">
                  <span className="relative flex h-3 w-3">
                    <span
                      className={cn(
                        "absolute inline-flex h-full w-full rounded-full opacity-75",
                        health.data?.status === "healthy"
                          ? "bg-emerald-400 animate-ping"
                          : "",
                      )}
                    />
                    <span
                      className={cn(
                        "relative inline-flex rounded-full h-3 w-3",
                        healthStatusColor(health.data?.status),
                      )}
                    />
                  </span>
                  <span className="text-2xl font-bold text-slate-100 tabular-nums capitalize">
                    {health.isLoading ? "…" : health.data?.status || "N/A"}
                  </span>
                </div>
              </div>
              <div className="h-11 w-11 rounded-xl border border-slate-700 bg-slate-800/40 flex items-center justify-center">
                <Activity className="h-5 w-5 text-cyan-400" />
              </div>
            </div>
            <div className="mt-3 text-xs font-mono text-slate-400">
              {health.data?.service || "ai-services"} ·{" "}
              {health.data?.version || "—"}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                  Readiness
                </div>
                <div className="mt-2 flex items-center gap-2">
                  {ready.isLoading ? (
                    <Skeleton className="h-6 w-24" />
                  ) : ready.error ? (
                    <>
                      <XCircle className="h-5 w-5 text-rose-400" />
                      <span className="text-2xl font-bold text-rose-300">
                        NOT READY
                      </span>
                    </>
                  ) : (
                    <>
                      <CheckCircle2 className="h-5 w-5 text-emerald-400" />
                      <span className="text-2xl font-bold text-emerald-300">
                        {ready.data?.status?.toUpperCase() || "READY"}
                      </span>
                    </>
                  )}
                </div>
              </div>
              <div className="h-11 w-11 rounded-xl border border-slate-700 bg-slate-800/40 flex items-center justify-center">
                <Cpu className="h-5 w-5 text-indigo-400" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                  API Base URL
                </div>
                <div className="mt-2">
                  <Copyable
                    value={API_BASE_URL}
                    truncate={false}
                    className="text-sm"
                  />
                </div>
                <div className="mt-2 flex items-center gap-1.5 text-[11px] text-slate-500 font-mono">
                  <Link2 className="h-3 w-3" />
                  Next.js rewrites /api → backend
                </div>
              </div>
              <div className="h-11 w-11 rounded-xl border border-slate-700 bg-slate-800/40 flex items-center justify-center">
                <Database className="h-5 w-5 text-emerald-400" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BrainCircuit className="h-4 w-4 text-indigo-400" />
            AI Module Readiness
          </CardTitle>
          <CardDescription>
            The four pillars of the TruthChain AI subsystem. A green tick means
            the module loaded successfully during server startup.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
          {Object.entries(MODULE_META).map(([k, meta]) => {
            const ok = modules?.[k as ModuleKey];
            const Icon = meta.icon;
            const accents: Record<string, string> = {
              cyan: "text-cyan-400 ring-cyan-500/30 from-cyan-500/15",
              indigo:
                "text-indigo-400 ring-indigo-500/30 from-indigo-500/15",
              amber:
                "text-amber-400 ring-amber-500/30 from-amber-500/15",
              purple:
                "text-purple-400 ring-purple-500/30 from-purple-500/15",
            };
            return (
              <div
                key={k}
                className={cn(
                  "rounded-xl border p-4 flex flex-col gap-3",
                  ok === true
                    ? "border-emerald-800/40 bg-emerald-950/10"
                    : ok === false
                      ? "border-rose-800/40 bg-rose-950/10"
                      : "border-slate-800 bg-slate-950/40",
                )}
              >
                <div className="flex items-center justify-between">
                  <div
                    className={cn(
                      "h-10 w-10 rounded-lg border ring-1 ring-inset bg-gradient-to-b flex items-center justify-center",
                      "border-slate-800",
                      accents[meta.accent],
                    )}
                  >
                    <Icon className={cn("h-5 w-5", accents[meta.accent].split(" ")[0])} />
                  </div>
                  {health.isLoading ? (
                    <Skeleton className="h-6 w-16" />
                  ) : ok === true ? (
                    <Badge variant="success">
                      <CheckCircle2 className="h-3 w-3 mr-1" />
                      Ready
                    </Badge>
                  ) : ok === false ? (
                    <Badge variant="danger">
                      <XCircle className="h-3 w-3 mr-1" />
                      Failed
                    </Badge>
                  ) : (
                    <Badge variant="default">Unknown</Badge>
                  )}
                </div>
                <div>
                  <div className="text-sm font-semibold text-slate-100">
                    {meta.label}
                  </div>
                  <div className="text-[11px] font-mono text-slate-500 mt-0.5 uppercase tracking-wider">
                    {k}
                  </div>
                </div>
                {health.data?.errors?.[k] && (
                  <div className="text-[11px] text-rose-300 leading-relaxed rounded-md border border-rose-900/40 bg-rose-950/30 px-2.5 py-2">
                    <AlertTriangle className="h-3 w-3 inline mr-1 -mt-0.5" />
                    {String(health.data.errors[k])}
                  </div>
                )}
              </div>
            );
          })}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ShieldAlert className="h-4 w-4 text-rose-400" />
              Blockchain Connection
            </CardTitle>
            <CardDescription>
              Audit service binding, ledger type, and database status.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            {bc.isLoading && (
              <div className="space-y-2">
                <Skeleton className="h-6 w-full" />
                <Skeleton className="h-6 w-5/6" />
                <Skeleton className="h-6 w-4/6" />
              </div>
            )}
            {bc.error && (
              <Alert variant="warning">
                <div className="text-xs">
                  {String(bc.error.message || bc.error)}
                </div>
              </Alert>
            )}
            {bc.data && (
              <>
                <div className="grid grid-cols-2 gap-x-4 divide-y divide-slate-800/70">
                  <div className="py-1.5 flex justify-between items-baseline gap-3">
                    <span className="text-xs text-slate-500">Connected</span>
                    <span
                      className={cn(
                        "font-mono text-xs",
                        bc.data.blockchain_connected
                          ? "text-emerald-300"
                          : "text-amber-300",
                      )}
                    >
                      {bc.data.blockchain_connected ? "LIVE RPC" : "AUDIT-ONLY"}
                    </span>
                  </div>
                  <div className="py-1.5 flex justify-between items-baseline gap-3">
                    <span className="text-xs text-slate-500">Ledger Type</span>
                    <span className="text-xs text-slate-200">
                      {bc.data.ledger_type || "—"}
                    </span>
                  </div>
                  <div className="py-1.5 flex justify-between items-baseline gap-3">
                    <span className="text-xs text-slate-500">Contract</span>
                    {bc.data.contract_address ? (
                      <Copyable
                        value={bc.data.contract_address as string}
                        start={6}
                        end={6}
                      />
                    ) : (
                      <span className="text-xs text-slate-500">—</span>
                    )}
                  </div>
                  <div className="py-1.5 flex justify-between items-baseline gap-3">
                    <span className="text-xs text-slate-500">RPC</span>
                    <span className="text-xs text-slate-400 font-mono truncate max-w-[55%] text-right">
                      {bc.data.rpc_url || "—"}
                    </span>
                  </div>
                  <div className="py-1.5 flex justify-between items-baseline gap-3">
                    <span className="text-xs text-slate-500">Database</span>
                    <span className="text-xs text-slate-200">
                      {typeof bc.data.database === "object" &&
                      bc.data.database !== null
                        ? (bc.data.database as { status?: string }).status ||
                          JSON.stringify(bc.data.database)
                        : String(bc.data.database ?? "—")}
                    </span>
                  </div>
                  <div className="py-1.5 flex justify-between items-baseline gap-3">
                    <span className="text-xs text-slate-500">
                      Simulated records
                    </span>
                    <span className="font-mono text-xs text-slate-200 tabular-nums">
                      {typeof bc.data.total_simulated_assessments === "number"
                        ? bc.data.total_simulated_assessments
                        : "—"}
                    </span>
                  </div>
                </div>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Gauge className="h-4 w-4 text-amber-400" />
              Runtime & Limits
            </CardTitle>
            <CardDescription>
              Python runtime, dependencies, and enforced API payload limits.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            {system.isLoading && (
              <div className="space-y-2">
                <Skeleton className="h-6 w-full" />
                <Skeleton className="h-6 w-5/6" />
                <Skeleton className="h-6 w-4/6" />
                <Skeleton className="h-6 w-5/6" />
              </div>
            )}
            {system.error && (
              <Alert variant="warning">
                <div className="text-xs">
                  {String(system.error.message || system.error)}
                </div>
              </Alert>
            )}
            {system.data && (
              <>
                <div className="grid grid-cols-2 gap-x-4 divide-y divide-slate-800/70">
                  <div className="py-1.5 flex justify-between items-baseline gap-3">
                    <span className="text-xs text-slate-500">Service</span>
                    <span className="text-xs text-slate-200 font-mono">
                      {system.data.service || "—"}
                    </span>
                  </div>
                  <div className="py-1.5 flex justify-between items-baseline gap-3">
                    <span className="text-xs text-slate-500">Version</span>
                    <span className="text-xs text-slate-200 font-mono">
                      {system.data.version || "—"}
                    </span>
                  </div>
                  <div className="py-1.5 flex justify-between items-baseline gap-3">
                    <span className="text-xs text-slate-500">Python</span>
                    <span className="text-xs text-slate-200 font-mono">
                      {system.data.python || "—"}
                    </span>
                  </div>
                  <div className="py-1.5 flex justify-between items-baseline gap-3">
                    <span className="text-xs text-slate-500">scikit-learn</span>
                    <span className="text-xs text-slate-200 font-mono">
                      {system.data.dependencies?.scikit_learn || "—"}
                    </span>
                  </div>
                  <Separator className="col-span-2" />
                  <div className="py-1.5 flex justify-between items-baseline gap-3">
                    <span className="text-xs text-slate-500">Max image bytes</span>
                    <span className="text-xs text-slate-200 font-mono tabular-nums">
                      {system.data.limits.max_image_bytes.toLocaleString()}
                    </span>
                  </div>
                  <div className="py-1.5 flex justify-between items-baseline gap-3">
                    <span className="text-xs text-slate-500">
                      Max description
                    </span>
                    <span className="text-xs text-slate-200 font-mono tabular-nums">
                      {system.data.limits.max_description_length.toLocaleString()}
                    </span>
                  </div>
                  <div className="py-1.5 flex justify-between items-baseline gap-3">
                    <span className="text-xs text-slate-500">Max claim ID</span>
                    <span className="text-xs text-slate-200 font-mono tabular-nums">
                      {system.data.limits.max_claim_id_length}
                    </span>
                  </div>
                  <div className="py-1.5 flex justify-between items-baseline gap-3">
                    <span className="text-xs text-slate-500">
                      Max metadata items
                    </span>
                    <span className="text-xs text-slate-200 font-mono tabular-nums">
                      {system.data.limits.max_metadata_items.toLocaleString()}
                    </span>
                  </div>
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-cyan-400" />
            API Endpoints Reference
          </CardTitle>
          <CardDescription>
            Endpoints wired into this frontend.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-800 bg-slate-900/60 text-left text-[11px] uppercase tracking-wider text-slate-400">
                  <th className="px-5 py-3 font-medium">Method</th>
                  <th className="px-5 py-3 font-medium">Path</th>
                  <th className="px-5 py-3 font-medium">Purpose</th>
                </tr>
              </thead>
              <tbody className="font-mono text-xs">
                {[
                  ["GET", "/health", "Module health"],
                  ["GET", "/ready", "Kubernetes readiness"],
                  ["GET", "/api/v1/system/info", "Runtime + limits"],
                  [
                    "POST",
                    "/api/v1/consensus/evaluate",
                    "8-Agent evaluation (main)",
                  ],
                  ["GET", "/api/v1/claims", "List claims"],
                  ["GET", "/api/v1/claims/{id}", "Single claim result"],
                  ["POST", "/api/v1/vision/predict", "Vision model direct"],
                  ["GET", "/api/v1/blockchain/status", "Audit service status"],
                  ["GET", "/api/v1/blockchain/records", "Registered records"],
                  [
                    "GET",
                    "/api/v1/blockchain/record/{id}",
                    "Single on-chain record",
                  ],
                  [
                    "POST",
                    "/api/v1/blockchain/verify",
                    "Integrity verification",
                  ],
                ].map(([m, p, d], i) => (
                  <tr
                    key={i}
                    className="border-b border-slate-800/60 last:border-none hover:bg-slate-900/40"
                  >
                    <td className="px-5 py-2.5">
                      <Badge
                        variant={
                          m === "GET" ? "info" : "blockchain"
                        }
                        className="font-mono"
                      >
                        {m}
                      </Badge>
                    </td>
                    <td className="px-5 py-2.5 text-slate-200">{p}</td>
                    <td className="px-5 py-2.5 text-slate-400 font-sans text-xs">
                      {d}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
