"use client";

import * as React from "react";
import {
  Card,
  CardContent,
  CardHeader,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator, Alert } from "@/components/ui/primitives";
import {
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Clock,
  Gauge,
  BrainCircuit,
  Eye,
  Activity,
  FileText,
  GitMerge,
  ShieldAlert,
  Lightbulb,
  Send,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type {
  AgentReport,
  ImageAgentReport,
  SensorAgentReport,
  TextAgentReport,
  CrossModalAgentReport,
  RiskEngineReport,
  AdversarialVerifierReport,
  ExplanationAgentReport,
  CommunicationAgentReport,
} from "@/types/agents";
import { Copyable } from "@/components/ui/copyable";
import { Button } from "@/components/ui/button";
import { copyToClipboard } from "@/lib/utils";

type AgentIconMap = Record<string, React.ComponentType<{ className?: string }>>;
const AGENT_ICONS: AgentIconMap = {
  ImageAgent: Eye,
  SensorAgent: Activity,
  TextAgent: FileText,
  CrossModalAgent: GitMerge,
  RiskEngine: Gauge,
  AdversarialVerifier: ShieldAlert,
  ExplanationAgent: Lightbulb,
  CommunicationAgent: Send,
};

const AGENT_ACCENTS: Record<
  string,
  { icon: string; ring: string; bg: string; label: string }
> = {
  ImageAgent: {
    icon: "text-cyan-400",
    ring: "ring-cyan-500/20",
    bg: "from-cyan-500/10",
    label: "Vision Inference",
  },
  SensorAgent: {
    icon: "text-orange-400",
    ring: "ring-orange-500/20",
    bg: "from-orange-500/10",
    label: "Telemetry Analysis",
  },
  TextAgent: {
    icon: "text-sky-400",
    ring: "ring-sky-500/20",
    bg: "from-sky-500/10",
    label: "Narrative Analysis",
  },
  CrossModalAgent: {
    icon: "text-violet-400",
    ring: "ring-violet-500/20",
    bg: "from-violet-500/10",
    label: "Cross-Modal Consensus",
  },
  RiskEngine: {
    icon: "text-indigo-400",
    ring: "ring-indigo-500/20",
    bg: "from-indigo-500/10",
    label: "Risk Scoring Engine",
  },
  AdversarialVerifier: {
    icon: "text-rose-400",
    ring: "ring-rose-500/20",
    bg: "from-rose-500/10",
    label: "Adversarial Audit",
  },
  ExplanationAgent: {
    icon: "text-amber-400",
    ring: "ring-amber-500/20",
    bg: "from-amber-500/10",
    label: "Human Explanation",
  },
  CommunicationAgent: {
    icon: "text-emerald-400",
    ring: "ring-emerald-500/20",
    bg: "from-emerald-500/10",
    label: "Comms Generation",
  },
};

function decisionBadge(decision?: string) {
  if (!decision) return <Badge variant="default">UNKNOWN</Badge>;
  const d = decision.toUpperCase();
  if (
    d.includes("VERIFIED") ||
    d === "PASS" ||
    d === "CONSISTENT" ||
    d.includes("DETECTED") ||
    d.includes("SUCCESS")
  ) {
    return <Badge variant="success">{decision}</Badge>;
  }
  if (d.includes("FRAUD") || d === "FAIL" || d.includes("ANOMALY")) {
    return <Badge variant="danger">{decision}</Badge>;
  }
  if (d.includes("REVIEW") || d.includes("WARNING")) {
    return <Badge variant="warning">{decision}</Badge>;
  }
  return <Badge variant="default">{decision}</Badge>;
}

function decisionIcon(decision?: string) {
  if (!decision) return <Clock className="h-4 w-4 text-slate-500" />;
  const d = decision.toUpperCase();
  if (
    d.includes("VERIFIED") ||
    d === "PASS" ||
    d === "CONSISTENT" ||
    d.includes("DETECTED") ||
    d.includes("SUCCESS")
  ) {
    return <CheckCircle2 className="h-4 w-4 text-emerald-400" />;
  }
  if (d.includes("FRAUD") || d === "FAIL" || d.includes("ANOMALY")) {
    return <XCircle className="h-4 w-4 text-rose-400" />;
  }
  if (d.includes("REVIEW") || d.includes("WARNING")) {
    return <AlertTriangle className="h-4 w-4 text-amber-400" />;
  }
  return <Clock className="h-4 w-4 text-slate-400" />;
}

function ValueRow({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: React.ReactNode;
  mono?: boolean;
}) {
  return (
    <div className="flex items-start justify-between gap-4 py-1.5">
      <div className="text-xs text-slate-500 shrink-0">{label}</div>
      <div
        className={cn(
          "text-sm text-slate-200 text-right",
          mono ? "font-mono" : "",
        )}
      >
        {value}
      </div>
    </div>
  );
}

function ProgressBar({
  value,
  max = 1,
  tone = "cyan",
}: {
  value: number;
  max?: number;
  tone?: "cyan" | "emerald" | "amber" | "rose";
}) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  const tones: Record<string, string> = {
    cyan: "bg-cyan-500",
    emerald: "bg-emerald-500",
    amber: "bg-amber-500",
    rose: "bg-rose-500",
  };
  return (
    <div className="w-full h-2 rounded-full bg-slate-800 overflow-hidden">
      <div
        className={cn("h-full rounded-full", tones[tone])}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

function AgentHeader({
  agentName,
  report,
  order,
}: {
  agentName: string;
  report: AgentReport | undefined;
  order: number;
}) {
  const Icon = AGENT_ICONS[agentName] || BrainCircuit;
  const accent = AGENT_ACCENTS[agentName] || {
    icon: "text-slate-400",
    ring: "ring-slate-500/20",
    bg: "from-slate-500/10",
    label: "Agent",
  };
  const confidence = report?.confidence;
  return (
    <div className="flex items-start justify-between gap-4 flex-wrap">
      <div className="flex items-start gap-3 min-w-0">
        <div
          className={cn(
            "h-10 w-10 shrink-0 rounded-xl border bg-gradient-to-b ring-1 ring-inset flex items-center justify-center",
            accent.bg,
            accent.ring,
            "border-slate-800",
          )}
        >
          <Icon className={cn("h-5 w-5", accent.icon)} />
        </div>
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <div className="text-[10px] font-mono text-slate-500">
              STEP {String(order).padStart(2, "0")}
            </div>
            <h3 className="text-sm font-semibold text-slate-100">
              {agentName}
            </h3>
            {report && decisionIcon(report.decision)}
            {report && decisionBadge(report.decision)}
          </div>
          <div className="text-[11px] text-slate-500 mt-0.5">
            {accent.label}
            {report?.model_version && (
              <>
                {" · "}
                <span className="font-mono">{report.model_version}</span>
              </>
            )}
            {typeof report?.processing_time_ms === "number" && (
              <>
                {" · "}
                <span className="font-mono">
                  {report.processing_time_ms.toFixed(0)}ms
                </span>
              </>
            )}
          </div>
        </div>
      </div>
      {typeof confidence === "number" && (
        <div className="shrink-0 w-40 space-y-1">
          <div className="flex items-center justify-between text-[11px]">
            <span className="text-slate-500">Confidence</span>
            <span className="text-slate-200 font-mono tabular-nums">
              {(confidence * 100).toFixed(1)}%
            </span>
          </div>
          <ProgressBar value={confidence} max={1} tone="emerald" />
        </div>
      )}
    </div>
  );
}

function AgentCardWrapper({
  agentName,
  order,
  report,
  children,
}: {
  agentName: string;
  order: number;
  report: AgentReport | undefined;
  children: React.ReactNode;
}) {
  const [open, setOpen] = React.useState(true);
  const hasEvidence = (report?.evidence?.length ?? 0) > 0;
  const hasContradictions = (report?.contradictions?.length ?? 0) > 0;
  return (
    <Card className="border-slate-800 overflow-hidden">
      <CardHeader className="pb-4">
        <div className="space-y-3">
          <AgentHeader agentName={agentName} report={report} order={order} />
          <div className="flex items-center justify-between pt-1">
            <div className="flex items-center gap-2 flex-wrap">
              {typeof report?.risk_score === "number" && (
                <Badge variant="default" className="font-mono text-[10px]">
                  RISK {(report.risk_score).toFixed(4)}
                </Badge>
              )}
              {hasEvidence && (
                <Badge variant="evidence" className="font-mono text-[10px]">
                  {(report?.evidence?.length ?? 0)} EVIDENCE
                </Badge>
              )}
              {hasContradictions ? (
                <Badge variant="danger" className="font-mono text-[10px]">
                  {(report?.contradictions?.length ?? 0)} CONTRADICTION
                </Badge>
              ) : report ? (
                <Badge variant="success" className="font-mono text-[10px]">
                  0 CONTRADICTIONS
                </Badge>
              ) : null}
            </div>
            <button
              type="button"
              onClick={() => setOpen((v) => !v)}
              className="text-xs text-slate-400 hover:text-slate-200 inline-flex items-center gap-1"
            >
              {open ? (
                <>
                  Collapse <ChevronUp className="h-3.5 w-3.5" />
                </>
              ) : (
                <>
                  Expand <ChevronDown className="h-3.5 w-3.5" />
                </>
              )}
            </button>
          </div>
        </div>
      </CardHeader>
      {open && (
        <CardContent className="pt-0 space-y-4 border-t border-slate-800/70">
          {children}
          {hasEvidence && (
            <div>
              <div className="text-[11px] font-semibold tracking-wider uppercase text-slate-400 mb-2">
                Evidence
              </div>
              <ul className="space-y-1.5">
                {report?.evidence?.map((e, i) => (
                  <li
                    key={i}
                    className="rounded-md border border-teal-900/30 bg-teal-950/20 px-3 py-2 text-sm text-slate-300 leading-relaxed"
                  >
                    {e}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {hasContradictions && (
            <div>
              <div className="text-[11px] font-semibold tracking-wider uppercase text-rose-400 mb-2">
                Contradictions
              </div>
              <ul className="space-y-1.5">
                {report?.contradictions?.map((e, i) => (
                  <li key={i} className="rounded-md border border-rose-900/50 bg-rose-950/30 px-3 py-2 text-sm text-rose-200">
                    {e}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </CardContent>
      )}
    </Card>
  );
}

export function ImageAgentCard({
  report,
  order,
}: {
  report?: ImageAgentReport;
  order: number;
}) {
  const predictions = report?.predictions;
  return (
    <AgentCardWrapper
      agentName="ImageAgent"
      order={order}
      report={report}
    >
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-4 divide-y divide-slate-800/70">
          <ValueRow label="Model" value={report?.model_version || "—"} mono />
          <ValueRow
            label="Damage Detected"
            value={
              report?.damage_detected ? (
                <Badge variant="success">YES</Badge>
              ) : (
                <Badge variant="default">NO</Badge>
              )
            }
          />
          <ValueRow
            label="Classes detected"
            value={
              (report?.detected_damage?.length ?? 0) > 0 ? (
                <div className="flex flex-wrap items-center gap-1 justify-end">
                  {report?.detected_damage?.map((d) => (
                    <Badge key={d} variant="info" className="font-mono text-[10px]">
                      {d}
                    </Badge>
                  ))}
                </div>
              ) : (
                <span className="text-slate-500">none</span>
              )
            }
          />
          <ValueRow
            label="Num Detected"
            value={String(report?.num_detected ?? "—")}
            mono
          />
          <ValueRow
            label="Processing time"
            value={
              typeof report?.processing_time_ms === "number"
                ? `${report.processing_time_ms.toFixed(0)} ms`
                : "—"
            }
            mono
          />
        </div>
        <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-4 space-y-2.5">
          <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
            Damage Class Probabilities
          </div>
          {!predictions && (
            <div className="text-xs text-slate-500">No prediction data.</div>
          )}
          {predictions &&
            Object.entries(predictions).map(([cls, p]) => {
              const tone = p.detected
                ? "emerald"
                : p.probability > 0.5
                  ? "amber"
                  : "cyan";
              return (
                <div key={cls} className="space-y-1">
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-slate-300 capitalize">{cls}</span>
                    <span className="font-mono text-slate-400 tabular-nums">
                      {(p.probability * 100).toFixed(1)}% · thr{" "}
                      {(p.threshold * 100).toFixed(0)}%
                      {p.detected && (
                        <span className="ml-1 text-emerald-400">✓</span>
                      )}
                    </span>
                  </div>
                  <ProgressBar value={p.probability} max={1} tone={tone} />
                </div>
              );
            })}
        </div>
      </div>
    </AgentCardWrapper>
  );
}

export function SensorAgentCard({
  report,
  order,
  userTelemetry,
}: {
  report?: SensorAgentReport;
  order: number;
  userTelemetry?: Record<string, number>;
}) {
  const features = report?.features;
  return (
    <AgentCardWrapper
      agentName="SensorAgent"
      order={order}
      report={report}
    >
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-4 divide-y divide-slate-800/70">
          <ValueRow label="Anomaly Flag" value={
            report?.anomaly ? <Badge variant="danger">ANOMALOUS</Badge> : <Badge variant="success">NORMAL</Badge>
          } />
          <ValueRow
            label="Model Score"
            value={
              typeof report?.model_score === "number"
                ? report.model_score.toFixed(4)
                : "—"
            }
            mono
          />
          <ValueRow
            label="Risk Score"
            value={
              typeof report?.risk_score === "number"
                ? report.risk_score.toFixed(4)
                : "—"
            }
            mono
          />
          <ValueRow
            label="Confidence"
            value={
              typeof report?.confidence === "number"
                ? `${(report.confidence * 100).toFixed(1)}%`
                : "—"
            }
            mono
          />
        </div>
        <div className="md:col-span-2 rounded-lg border border-slate-800 bg-slate-950/40 p-4">
          <div className="text-xs font-semibold tracking-wider text-slate-400 uppercase mb-2 flex items-center gap-2">
            <span>USER TELEMETRY (Input)</span>
            <Badge variant="default" className="text-[10px]">
              Provided by user
            </Badge>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-x-4 divide-y divide-slate-800/70 md:divide-y-0">
            {Object.entries(userTelemetry || {}).length === 0 &&
              (!features ? (
                <div className="col-span-full text-xs text-slate-500">
                  No telemetry captured.
                </div>
              ) : null)}
            {Object.entries(userTelemetry || {}).map(([k, v]) => (
              <ValueRow key={`u-${k}`} label={k} value={String(v)} mono />
            ))}
          </div>
          {features && (
            <>
              <Separator className="my-3" />
              <div className="text-xs font-semibold tracking-wider text-slate-400 uppercase mb-2 flex items-center gap-2">
                <span>DERIVED SENSOR ANALYSIS (AI)</span>
                <Badge variant="info" className="text-[10px]">
                  SensorAgent v2
                </Badge>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-x-4 divide-y divide-slate-800/70 md:divide-y-0">
                {Object.entries(features).map(([k, v]) =>
                  k in (userTelemetry || {}) ? null : (
                    <ValueRow
                      key={`f-${k}`}
                      label={k}
                      value={
                        typeof v === "number" ? v.toFixed(4) : String(v)
                      }
                      mono
                    />
                  ),
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </AgentCardWrapper>
  );
}

export function TextAgentCard({
  report,
  order,
}: {
  report?: TextAgentReport;
  order: number;
}) {
  const info = report?.extracted_information;
  return (
    <AgentCardWrapper agentName="TextAgent" order={order} report={report}>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-4 divide-y divide-slate-800/70">
          <ValueRow
            label="Incident Type"
            value={info?.incident_type || "—"}
          />
          <ValueRow
            label="Text Length"
            value={String(report?.text_length ?? "—")}
            mono
          />
          <ValueRow
            label="Decision"
            value={decisionBadge(report?.decision)}
          />
          <ValueRow
            label="Confidence"
            value={
              typeof report?.confidence === "number"
                ? `${(report.confidence * 100).toFixed(1)}%`
                : "—"
            }
            mono
          />
          <div className="py-1.5">
            <div className="text-xs text-slate-500 mb-1.5">
              Claimant-described damage
            </div>
            <div className="flex flex-wrap gap-1 justify-end">
              {info?.damage_types?.length ? (
                info.damage_types.map((d) => (
                  <Badge key={d} variant="info" className="font-mono text-[10px]">
                    {d}
                  </Badge>
                ))
              ) : (
                <span className="text-xs text-slate-500">—</span>
              )}
            </div>
          </div>
        </div>
        <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-4 space-y-3">
          <div>
            <div className="text-[11px] font-semibold tracking-wider uppercase text-slate-400 mb-1.5">
              Summary (LLM)
            </div>
            <div className="text-sm text-slate-300 leading-relaxed rounded-md border border-slate-800/80 bg-slate-900/50 p-3">
              {report?.summary || (
                <span className="text-slate-500 italic">No summary.</span>
              )}
            </div>
          </div>
          {report?.signals?.length ? (
            <div>
              <div className="text-[11px] font-semibold tracking-wider uppercase text-slate-400 mb-1.5">
                Narrative Signals
              </div>
              <ul className="space-y-1 text-xs text-slate-300">
                {report.signals.map((s, i) => (
                  <li
                    key={i}
                    className="rounded border border-slate-800 bg-slate-900/30 px-2.5 py-1.5"
                  >
                    • {s}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      </div>
    </AgentCardWrapper>
  );
}

export function CrossModalAgentCard({
  report,
  order,
}: {
  report?: CrossModalAgentReport;
  order: number;
}) {
  return (
    <AgentCardWrapper
      agentName="CrossModalAgent"
      order={order}
      report={report}
    >
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-4 divide-y divide-slate-800/70">
          <ValueRow
            label="Agreement State"
            value={
              report?.agreement_state ? (
                <Badge
                  variant={
                    report.agreement_state === "CONSISTENT"
                      ? "success"
                      : report.agreement_state === "FULL_CONSENSUS"
                        ? "success"
                        : report.agreement_state === "INCONSISTENT"
                          ? "danger"
                          : "warning"
                  }
                  className="font-mono"
                >
                  {report.agreement_state}
                </Badge>
              ) : (
                "—"
              )
            }
          />
          <ValueRow
            label="Decision"
            value={decisionBadge(report?.decision)}
          />
          <ValueRow
            label="Confidence"
            value={
              typeof report?.confidence === "number"
                ? `${(report.confidence * 100).toFixed(1)}%`
                : "—"
            }
            mono
          />
          <ValueRow
            label="Risk Score"
            value={
              typeof report?.risk_score === "number"
                ? report.risk_score.toFixed(4)
                : "—"
            }
            mono
          />
        </div>
        <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-4">
          <div className="text-[11px] font-semibold tracking-wider uppercase text-slate-400 mb-3">
            Modal Decisions
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between rounded-md border border-slate-800 bg-slate-900/40 px-3 py-2">
              <span className="text-xs text-slate-400">Vision ↔ Sensor</span>
              <Badge variant="evidence" className="font-mono text-[10px]">
                {report?.modal_results?.image_decision || "—"} /{" "}
                {report?.modal_results?.sensor_decision || "—"}
              </Badge>
            </div>
            <div className="flex items-center justify-between rounded-md border border-slate-800 bg-slate-900/40 px-3 py-2">
              <span className="text-xs text-slate-400">Vision ↔ Text</span>
              <Badge variant="evidence" className="font-mono text-[10px]">
                {report?.modal_results?.image_decision || "—"} /{" "}
                {report?.modal_results?.text_decision || "—"}
              </Badge>
            </div>
            <div className="flex items-center justify-between rounded-md border border-slate-800 bg-slate-900/40 px-3 py-2">
              <span className="text-xs text-slate-400">Sensor ↔ Text</span>
              <Badge variant="evidence" className="font-mono text-[10px]">
                {report?.modal_results?.sensor_decision || "—"} /{" "}
                {report?.modal_results?.text_decision || "—"}
              </Badge>
            </div>
          </div>
        </div>
      </div>
    </AgentCardWrapper>
  );
}

export function RiskEngineCard({
  report,
  order,
}: {
  report?: RiskEngineReport;
  order: number;
}) {
  return (
    <AgentCardWrapper agentName="RiskEngine" order={order} report={report}>
      <div className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="rounded-lg border border-emerald-800/40 bg-emerald-950/10 p-4 space-y-2">
            <div className="text-[11px] uppercase tracking-wider text-emerald-400 font-semibold">
              Final Decision
            </div>
            <div className="text-2xl font-bold text-slate-100 tabular-nums">
              {report?.decision || "—"}
            </div>
            <div className="text-xs text-slate-400">
              {report?.final_verdict || ""}
            </div>
          </div>
          <div className="rounded-lg border border-rose-800/40 bg-rose-950/10 p-4 space-y-2">
            <div className="text-[11px] uppercase tracking-wider text-rose-400 font-semibold">
              Fraud Score
            </div>
            <div className="text-2xl font-bold text-slate-100 tabular-nums">
              {typeof report?.fraud_score === "number"
                ? report.fraud_score
                : "—"}
              <span className="text-base ml-1 text-slate-500">/100</span>
            </div>
            <ProgressBar
              value={report?.fraud_score ?? 0}
              max={100}
              tone={
                (report?.fraud_score ?? 0) >= 65
                  ? "rose"
                  : (report?.fraud_score ?? 0) >= 30
                    ? "amber"
                    : "emerald"
              }
            />
          </div>
          <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-4 divide-y divide-slate-800/70">
            <ValueRow
              label="Pipeline"
              value={
                report?.pipeline_status ? (
                  <Badge
                    variant={
                      report.pipeline_status === "COMPLETE"
                        ? "success"
                        : "warning"
                    }
                    className="font-mono"
                  >
                    {report.pipeline_status}
                  </Badge>
                ) : (
                  "—"
                )
              }
            />
            <ValueRow
              label="Active Weight Total"
              value={
                typeof report?.active_weight_total === "number"
                  ? report.active_weight_total.toFixed(2)
                  : "—"
              }
              mono
            />
            <ValueRow
              label="Stage"
              value={report?.risk_stage || "—"}
              mono
            />
            <ValueRow
              label="Failures"
              value={
                (report?.pipeline_failures?.length ?? 0) > 0 ? (
                  <Badge variant="danger">
                    {report?.pipeline_failures?.length}
                  </Badge>
                ) : (
                  <Badge variant="success">0</Badge>
                )
              }
            />
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-4">
            <div className="text-[11px] font-semibold tracking-wider uppercase text-slate-400 mb-2">
              Formula Components (Fraud Signals)
            </div>
            <div className="divide-y divide-slate-800/70">
              {report?.formula_components ? (
                Object.entries(report.formula_components).map(([k, v]) => (
                  <ValueRow
                    key={k}
                    label={k}
                    value={v.toFixed(4)}
                    mono
                  />
                ))
              ) : (
                <div className="text-xs text-slate-500 py-2">
                  No component data.
                </div>
              )}
            </div>
          </div>
          <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-4">
            <div className="text-[11px] font-semibold tracking-wider uppercase text-slate-400 mb-2">
              Agent Contributions
            </div>
            <div className="space-y-2">
              {report?.weights ? (
                Object.entries(report.weights).map(([agent, w]) => {
                  const raw =
                    report.raw_agent_scores?.[
                      `${agent}_risk_score` as keyof typeof report.raw_agent_scores
                    ] ?? 0;
                  const contribution =
                    typeof raw === "number" ? raw * w : null;
                  return (
                    <div key={agent} className="space-y-1">
                      <div className="flex items-center justify-between text-[11px]">
                        <span className="text-slate-300 capitalize">
                          {agent}
                        </span>
                        <span className="font-mono text-slate-400 tabular-nums">
                          w={w.toFixed(2)} · raw={Number(raw).toFixed(2)}
                          {typeof contribution === "number" && (
                            <>
                              {" · "}
                              <span className="text-indigo-300">
                                Σ {contribution.toFixed(3)}
                              </span>
                            </>
                          )}
                        </span>
                      </div>
                      <ProgressBar
                        value={Number(raw)}
                        max={1}
                        tone={
                          agent === "cross_modal"
                            ? "emerald"
                            : agent === "image"
                              ? "cyan"
                              : agent === "sensor"
                                ? "amber"
                                : "rose"
                        }
                      />
                    </div>
                  );
                })
              ) : (
                <div className="text-xs text-slate-500">
                  No contribution data.
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </AgentCardWrapper>
  );
}

export function AdversarialVerifierCard({
  report,
  order,
}: {
  report?: AdversarialVerifierReport;
  order: number;
}) {
  return (
    <AgentCardWrapper
      agentName="AdversarialVerifier"
      order={order}
      report={report}
    >
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="md:col-span-1 rounded-lg border border-rose-900/40 bg-rose-950/10 p-4 space-y-2">
          <div className="text-[11px] uppercase tracking-wider text-rose-400 font-semibold">
            Final Verdict
          </div>
          <div className="text-2xl font-bold text-slate-100 tabular-nums">
            {report?.final_verdict || report?.decision || "—"}
          </div>
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <span className="font-mono">
              Conf {typeof report?.confidence === "number"
                ? `${(report.confidence * 100).toFixed(0)}%`
                : "—"}
            </span>
            <Separator orientation="vertical" className="h-3 w-px" />
            <span className="font-mono">
              Prelim risk{" "}
              {typeof report?.preliminary_risk === "number"
                ? report.preliminary_risk.toFixed(4)
                : "—"}
            </span>
          </div>
          {report?.adversarial_flagged ? (
            <Badge variant="danger">ADVERSARIAL FLAGGED</Badge>
          ) : (
            <Badge variant="success">NO ADVERSARIAL FLAGS</Badge>
          )}
        </div>
        <div className="md:col-span-2 rounded-lg border border-slate-800 bg-slate-950/40 p-4 space-y-3">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-0.5">
              <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                Audited Agents
              </div>
              <div className="flex flex-wrap gap-1 pt-1">
                {report?.audited_agents?.length ? (
                  report.audited_agents.map((a) => (
                    <Badge key={a} variant="info" className="font-mono text-[10px]">
                      {a}
                    </Badge>
                  ))
                ) : (
                  <span className="text-xs text-slate-500">—</span>
                )}
              </div>
            </div>
            <div className="space-y-0.5">
              <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                Failed Agents
              </div>
              <div className="flex flex-wrap gap-1 pt-1">
                {report?.failed_agents?.length ? (
                  report.failed_agents.map((a) => (
                    <Badge key={a} variant="danger" className="font-mono text-[10px]">
                      {a}
                    </Badge>
                  ))
                ) : (
                  <Badge variant="success" className="font-mono text-[10px]">
                    0 FAILED
                  </Badge>
                )}
              </div>
            </div>
          </div>
          <Separator />
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-2">
              Audited Evidence Snapshot
            </div>
            {report?.audited_evidence?.length ? (
              <div className="max-h-52 overflow-y-auto space-y-1 pr-1">
                {report.audited_evidence.map((e, i) => (
                  <div
                    key={i}
                    className="rounded border border-slate-800 bg-slate-900/40 px-2.5 py-1.5 text-xs text-slate-300 leading-relaxed"
                  >
                    {e}
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-xs text-slate-500 italic">
                No audited evidence returned.
              </div>
            )}
          </div>
        </div>
      </div>
    </AgentCardWrapper>
  );
}

export function ExplanationAgentCard({
  report,
  order,
}: {
  report?: ExplanationAgentReport;
  order: number;
}) {
  return (
    <AgentCardWrapper
      agentName="ExplanationAgent"
      order={order}
      report={report}
    >
      <div className="space-y-3">
        {report?.executive_summary && (
          <Alert variant="info">
            <div className="text-[11px] font-semibold uppercase tracking-wider opacity-80 mb-1">
              Executive Summary
            </div>
            <div className="text-sm leading-relaxed">
              {report.executive_summary}
            </div>
          </Alert>
        )}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-4">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-2">
              Key Highlights
            </div>
            {report?.key_highlights?.length ? (
              <ul className="space-y-1.5">
                {report.key_highlights.map((h, i) => (
                  <li
                    key={i}
                    className="text-xs text-slate-300 leading-relaxed rounded border border-slate-800 bg-slate-900/40 px-2.5 py-1.5"
                  >
                    <span className="text-amber-400 mr-1.5">▸</span>
                    {h}
                  </li>
                ))}
              </ul>
            ) : (
              <div className="text-xs text-slate-500 italic">
                No highlights provided.
              </div>
            )}
          </div>
          <div className="space-y-3">
            <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-4">
              <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-2">
                Recommended Actions
              </div>
              {report?.recommended_actions?.length ? (
                <ul className="space-y-1.5">
                  {report.recommended_actions.map((a, i) => (
                    <li
                      key={i}
                      className="text-xs text-slate-300 leading-relaxed rounded border border-emerald-900/30 bg-emerald-950/10 px-2.5 py-1.5"
                    >
                      <CheckCircle2 className="h-3 w-3 text-emerald-400 inline mr-1.5 -mt-0.5" />
                      {a}
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="text-xs text-slate-500 italic">
                  No recommended actions provided.
                </div>
              )}
            </div>
            <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-4 divide-y divide-slate-800/70">
              <ValueRow
                label="Final Verdict"
                value={decisionBadge(report?.final_verdict)}
              />
              <ValueRow
                label="Verifier Decision"
                value={decisionBadge(report?.verifier_decision)}
              />
              <ValueRow
                label="Contradictions"
                value={String(report?.contradiction_count ?? "—")}
                mono
              />
              <ValueRow
                label="Pipeline"
                value={
                  report?.pipeline_status ? (
                    <Badge
                      variant={
                        report.pipeline_status === "COMPLETE"
                          ? "success"
                          : "warning"
                      }
                      className="font-mono"
                    >
                      {report.pipeline_status}
                    </Badge>
                  ) : (
                    "—"
                  )
                }
              />
            </div>
          </div>
        </div>
      </div>
    </AgentCardWrapper>
  );
}

export function CommunicationAgentCard({
  report,
  order,
}: {
  report?: CommunicationAgentReport;
  order: number;
}) {
  const [copied, setCopied] = React.useState(false);
  const copyMessage = async () => {
    if (!report?.message_body) return;
    const ok = await copyToClipboard(report.message_body);
    if (ok) {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    }
  };
  return (
    <AgentCardWrapper
      agentName="CommunicationAgent"
      order={order}
      report={report}
    >
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-4 divide-y divide-slate-800/70">
          <ValueRow label="Recipient" value={report?.recipient || "—"} />
          <ValueRow
            label="Final Verdict"
            value={decisionBadge(report?.final_verdict)}
          />
          <ValueRow
            label="Fraud Score"
            value={
              typeof report?.fraud_score === "number"
                ? `${report.fraud_score} / 100`
                : "—"
            }
            mono
          />
          <ValueRow
            label="Contradictions"
            value={String(report?.contradiction_count ?? "—")}
            mono
          />
          <ValueRow
            label="Evidence Highlights"
            value={String(report?.evidence_highlight_count ?? "—")}
            mono
          />
          <ValueRow
            label="Pipeline"
            value={
              report?.pipeline_status ? (
                <Badge
                  variant={
                    report.pipeline_status === "COMPLETE"
                      ? "success"
                      : "warning"
                  }
                  className="font-mono"
                >
                  {report.pipeline_status}
                </Badge>
              ) : (
                "—"
              )
            }
          />
        </div>
        <div className="md:col-span-2 rounded-lg border border-slate-800 bg-slate-950/40 p-4 space-y-3">
          <div className="flex items-start justify-between gap-3 flex-wrap">
            <div className="min-w-0">
              <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                Subject
              </div>
              <div className="text-sm font-medium text-slate-100 mt-0.5">
                {report?.subject || (
                  <span className="text-slate-500 italic">
                    No subject provided.
                  </span>
                )}
              </div>
            </div>
            <Button size="sm" variant="outline" onClick={copyMessage}>
              {copied ? (
                <>
                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                  Copied
                </>
              ) : (
                "Copy Message"
              )}
            </Button>
          </div>
          <Separator />
          <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
            Generated Message
          </div>
          <div className="rounded-md border border-slate-800 bg-slate-900/60 p-4 text-sm text-slate-200 leading-relaxed whitespace-pre-wrap max-h-80 overflow-y-auto">
            {report?.message_body || (
              <span className="text-slate-500 italic">
                No message body generated.
              </span>
            )}
          </div>
          {report?.explanation_summary && (
            <>
              <Separator />
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
                  Explanation Summary
                </div>
                <div className="text-xs text-slate-300 leading-relaxed">
                  {report.explanation_summary}
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </AgentCardWrapper>
  );
}

export { decisionBadge, Copyable };
