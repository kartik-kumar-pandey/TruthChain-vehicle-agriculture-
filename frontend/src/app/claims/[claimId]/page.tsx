"use client";

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useClaim, useVerifyBlockchainRecord } from "@/hooks/useTruthChain";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  SectionHeader,
  Skeleton,
  Alert,
  Separator,
} from "@/components/ui/primitives";
import {
  FileText,
  ArrowLeft,
  ShieldCheck,
  Blocks,
  AlertTriangle,
  ExternalLink,
  CheckCircle2,
  XCircle,
  Eye,
  Clock,
  RefreshCw,
  FilePlus2,
  FileImage,
} from "lucide-react";
import { AGENT_ORDER, ETHERSCAN_BASE_URL } from "@/lib/constants";
import { cn, formatDate } from "@/lib/utils";
import { Copyable } from "@/components/ui/copyable";
import {
  SatelliteAgentCard,
  ImageAgentCard,
  SensorAgentCard,
  TextAgentCard,
  CrossModalAgentCard,
  RiskEngineCard,
  AdversarialVerifierCard,
  ExplanationAgentCard,
  CommunicationAgentCard,
} from "@/components/agents/AgentCards";
import type { ClaimResult } from "@/types/claim";
import type { ClaimInputData } from "@/types/claim";

function verdictGlowClass(verdict?: string): string {
  const v = (verdict || "").toUpperCase();
  if (v === "VERIFIED") return "verdict-glow-verified";
  if (v === "FRAUD") return "verdict-glow-fraud";
  if (v === "REVIEW") return "verdict-glow-review";
  return "";
}

function verdictTone(verdict?: string): "emerald" | "rose" | "amber" | "slate" {
  const v = (verdict || "").toUpperCase();
  if (v === "VERIFIED") return "emerald";
  if (v === "FRAUD") return "rose";
  if (v === "REVIEW") return "amber";
  return "slate";
}

function FinalVerdictCard({ claim }: { claim: ClaimResult }) {
  const agents = claim.agent_reports || {};
  const completed = Object.keys(agents).length;
  const verdict = claim.final_verdict || "PENDING";
  const tone = verdictTone(verdict);
  const toneClasses = {
    emerald: "text-emerald-300 border-emerald-700/40 bg-emerald-950/30",
    rose: "text-rose-300 border-rose-700/40 bg-rose-950/30",
    amber: "text-amber-300 border-amber-700/40 bg-amber-950/30",
    slate: "text-slate-300 border-slate-700/40 bg-slate-900/40",
  }[tone];
  const bcStatus = claim.certificate?.status || "PENDING";
  const bcReady =
    bcStatus === "REGISTERED" || bcStatus === "ALREADY_REGISTERED";
  return (
    <Card
      className={cn(
        "border-2 overflow-hidden",
        tone === "emerald"
          ? "border-emerald-800/50"
          : tone === "rose"
            ? "border-rose-800/50"
            : tone === "amber"
              ? "border-amber-800/50"
              : "border-slate-800",
        verdictGlowClass(verdict),
      )}
    >
      <CardContent className="p-0">
        <div className="grid grid-cols-1 md:grid-cols-3">
          <div className="md:col-span-2 p-6 md:p-8 flex flex-col justify-center">
            <div className="flex items-center gap-2 mb-3">
              <ShieldCheck className={cn("h-5 w-5", {
                "text-emerald-400": tone === "emerald",
                "text-rose-400": tone === "rose",
                "text-amber-400": tone === "amber",
                "text-slate-400": tone === "slate",
              })} />
              <div className="text-xs font-semibold tracking-[0.18em] uppercase text-slate-400">
                Final Verdict
              </div>
            </div>
            <div
              className={cn(
                "text-5xl md:text-7xl font-black tracking-tight tabular-nums",
                {
                  "text-emerald-300": tone === "emerald",
                  "text-rose-300": tone === "rose",
                  "text-amber-300": tone === "amber",
                  "text-slate-300": tone === "slate",
                },
              )}
            >
              {verdict}
            </div>
            <div className="mt-6 grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div className="rounded-lg border border-slate-800/80 bg-slate-950/40 p-3">
                <div className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">
                  Fraud Score
                </div>
                <div
                  className={cn(
                    "text-2xl font-bold tabular-nums mt-1",
                    (claim.fraud_score ?? 0) === 0
                      ? "text-emerald-300"
                      : (claim.fraud_score ?? 0) >= 65
                        ? "text-rose-300"
                        : "text-amber-300",
                  )}
                >
                  {claim.fraud_score ?? "—"}
                  <span className="text-sm text-slate-500 ml-1 font-medium">
                    /100
                  </span>
                </div>
              </div>
              <div className="rounded-lg border border-slate-800/80 bg-slate-950/40 p-3">
                <div className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">
                  Pipeline
                </div>
                <div className="text-lg font-bold text-slate-100 mt-1">
                  {claim.pipeline_status || "PENDING"}
                </div>
              </div>
              <div className="rounded-lg border border-slate-800/80 bg-slate-950/40 p-3">
                <div className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">
                  Required Agents
                </div>
                <div className="text-2xl font-bold tabular-nums mt-1 text-slate-100">
                  {completed}
                  <span className="text-sm text-slate-500 ml-1 font-medium">
                    / {AGENT_ORDER.length}
                  </span>
                </div>
              </div>
              <div className="rounded-lg border border-purple-800/30 bg-purple-950/20 p-3">
                <div className="text-[10px] uppercase tracking-wider text-purple-400 font-semibold">
                  Blockchain
                </div>
                <div
                  className={cn(
                    "text-lg font-bold mt-1",
                    bcReady ? "text-purple-300" : "text-slate-400",
                  )}
                >
                  {bcStatus}
                </div>
              </div>
            </div>
            <div className="mt-6 flex flex-wrap items-center gap-2">
              <Badge variant="evidence" className="font-mono text-[10px]">
                OFF-CHAIN AI EVIDENCE
              </Badge>
              <span className="text-slate-600 text-xs">+</span>
              <Badge variant="blockchain" className="font-mono text-[10px]">
                ON-CHAIN IMMUTABLE PROOF
              </Badge>
            </div>
          </div>
          <div
            className={cn(
              "md:border-l border-t md:border-t-0 border-slate-800 p-6 md:p-8 flex flex-col justify-center",
              toneClasses,
            )}
          >
            <div className="text-[10px] uppercase tracking-[0.2em] font-semibold opacity-80 mb-1">
              TRUTHCHAIN 2.0 · ASSESSMENT
            </div>
            <div className="text-xs font-mono opacity-90 break-all">
              {claim.claim_id}
            </div>
            <Separator className="my-4 opacity-50" />
            <div className="space-y-1 text-xs opacity-90">
              <div className="flex justify-between">
                <span className="opacity-70">Domain</span>
                <span className="font-mono">{claim.domain || "motor"}</span>
              </div>
              <div className="flex justify-between">
                <span className="opacity-70">State</span>
                <span className="font-mono">{claim.state || "—"}</span>
              </div>
              <div className="flex justify-between">
                <span className="opacity-70">BC Allowed</span>
                <span className="font-mono">
                  {claim.blockchain_allowed ? "YES" : "NO"}
                </span>
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function ClaimOverviewCard({ claim }: { claim: ClaimResult }) {
  const data: ClaimInputData = claim.data || {};
  // Try image_data_url first (set by the frontend on submit), then fall back to
  // data.image (the AI pipeline copies image_data_url → image).
  // Reject bare file-system paths (C:\... or /home/...) that the browser can't load.
  const _candidates = [
    (data as { image_data_url?: string }).image_data_url,
    (data as { image?: string }).image,
    (data as { image_url?: string }).image_url,
  ];
  const imageSrc = _candidates.find(
    (v) => typeof v === "string" && (v.startsWith("data:") || v.startsWith("http"))
  ) ?? undefined;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <FileText className="h-4 w-4 text-cyan-400" />
          Claim Overview
        </CardTitle>
        <CardDescription>Administrative and evidence context.</CardDescription>
      </CardHeader>
      <CardContent className="grid grid-cols-1 lg:grid-cols-5 gap-5">
        <div className="lg:col-span-3 grid grid-cols-1 sm:grid-cols-2 gap-x-4 divide-y divide-slate-800/70 sm:divide-y-0">
          <div className="py-1.5 sm:py-0">
            <div className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold mb-1">
              Claim ID
            </div>
            <Copyable
              value={claim.claim_id}
              truncate={false}
              className="text-sm font-mono text-slate-100"
            />
          </div>
          <div className="py-1.5 sm:py-0">
            <div className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold mb-1">
              Policy Number
            </div>
            <div className="text-sm font-mono text-slate-200">
              {(data as { policy_number?: string }).policy_number || "—"}
            </div>
          </div>
          <div className="py-1.5 sm:py-0">
            <div className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold mb-1">
              Vehicle
            </div>
            <div className="text-sm text-slate-200">
              {(data as { vehicle_make_model?: string }).vehicle_make_model ||
                (data as { vehicle_registration?: string })
                  .vehicle_registration ||
                "—"}
            </div>
          </div>
          <div className="py-1.5 sm:py-0">
            <div className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold mb-1">
              Incident Date
            </div>
            <div className="text-sm text-slate-200">
              {(data as { incident_date?: string }).incident_date || "—"}
            </div>
          </div>
          <div className="py-1.5 sm:py-0 sm:col-span-2">
            <div className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold mb-1">
              Incident Location
            </div>
            <div className="text-sm text-slate-200">
              {(data as { incident_location?: string }).incident_location || "—"}
            </div>
          </div>
          <div className="py-1.5 sm:py-0 sm:col-span-2">
            <div className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold mb-1">
              Claimant Narrative
            </div>
            <div className="text-sm text-slate-200 leading-relaxed rounded-md border border-slate-800 bg-slate-950/40 p-3 whitespace-pre-wrap">
              {data.text || data.claim_text || (
                <span className="text-slate-500 italic">No narrative.</span>
              )}
            </div>
          </div>
        </div>
        <div className="lg:col-span-2 rounded-lg border border-slate-800 bg-slate-950/40 p-3">
          <div className="flex items-center justify-between mb-2 px-1">
            <div className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold flex items-center gap-1.5">
              <FileImage className="h-3 w-3" /> Damage Photo
            </div>
            {(data as { image_filename?: string }).image_filename && (
              <span className="text-[10px] text-slate-500 font-mono truncate max-w-[55%]">
                {(data as { image_filename?: string }).image_filename}
              </span>
            )}
          </div>
          {imageSrc ? (
            <div className="rounded-md overflow-hidden bg-black/40 aspect-video flex items-center justify-center">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={imageSrc}
                alt="Damage photo"
                className="max-h-72 w-full object-contain"
              />
            </div>
          ) : (
            <div className="rounded-md border border-dashed border-slate-800 bg-slate-900/30 aspect-video flex flex-col items-center justify-center gap-2 text-slate-500 text-xs">
              <Eye className="h-5 w-5" />
              No image preview available
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function BlockchainCertificateCard({
  claim,
  onVerify,
  verifying,
  verifyResult,
}: {
  claim: ClaimResult;
  onVerify: () => void;
  verifying: boolean;
  verifyResult: ReturnType<typeof useVerifyBlockchainRecord>["data"] | null;
}) {
  const cert = claim.certificate;
  const txHash = cert?.transaction_hash;
  const etherscanLink = txHash
    ? `${ETHERSCAN_BASE_URL}/tx/${txHash.startsWith("0x") ? txHash : `0x${txHash}`}`
    : null;
  const bcStatus = cert?.status || "PENDING";
  const bcReady =
    bcStatus === "REGISTERED" || bcStatus === "ALREADY_REGISTERED";

  const imgMatch =
    verifyResult?.image_integrity?.matched ??
    verifyResult?.image_hash_match;
  const predMatch =
    verifyResult?.prediction_integrity?.matched ??
    verifyResult?.prediction_hash_match;
  const overall = verifyResult
    ? verifyResult.verified === true || verifyResult.is_match === true
    : null;

  return (
    <Card className="border-purple-900/40 bg-purple-950/5">
      <CardHeader>
        <div className="flex items-start justify-between flex-wrap gap-3">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Blocks className="h-4 w-4 text-purple-400" />
              BLOCKCHAIN CERTIFICATE
            </CardTitle>
            <CardDescription>
              ON-CHAIN IMMUTABLE PROOF · AssessmentRegistry ·{" "}
              {cert?.network || "Sepolia"}
            </CardDescription>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge
              variant={bcReady ? "blockchain" : "default"}
              className="font-mono"
            >
              {bcReady ? cert?.status : bcStatus}
            </Badge>
            {cert?.reused && (
              <Badge variant="info" className="font-mono text-[10px]">
                EXISTING · REUSED
              </Badge>
            )}
            <Button
              size="sm"
              variant="outline"
              onClick={onVerify}
              disabled={!cert?.record_id || verifying}
            >
              {verifying ? (
                <>
                  <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                  Verifying…
                </>
              ) : (
                <>
                  <ShieldCheck className="h-3.5 w-3.5" />
                  Verify Evidence
                </>
              )}
            </Button>
            {etherscanLink && (
              <a
                href={etherscanLink}
                target="_blank"
                rel="noreferrer noopener"
              >
                <Button size="sm" variant="blockchain">
                  View on Sepolia Etherscan
                  <ExternalLink className="h-3.5 w-3.5" />
                </Button>
              </a>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <div className="rounded-lg border border-purple-900/30 bg-slate-950/60 p-4 divide-y divide-slate-800/70">
          <div className="py-1.5 flex items-start justify-between gap-3 flex-wrap">
            <div className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold pt-1">
              Network
            </div>
            <div className="text-sm text-slate-100 font-mono">
              {cert?.network || "Sepolia"}
            </div>
          </div>
          <div className="py-1.5 flex items-start justify-between gap-3 flex-wrap">
            <div className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold pt-1">
              Contract Address
            </div>
            {cert?.contract_address ? (
              <Copyable value={cert.contract_address} />
            ) : (
              <span className="text-slate-500 text-sm">—</span>
            )}
          </div>
          <div className="py-1.5 flex items-start justify-between gap-3 flex-wrap">
            <div className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold pt-1">
              Record ID
            </div>
            {cert?.record_id ? (
              <Copyable value={cert.record_id} />
            ) : (
              <span className="text-slate-500 text-sm">—</span>
            )}
          </div>
          <div className="py-1.5 flex items-start justify-between gap-3 flex-wrap">
            <div className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold pt-1">
              Transaction Hash
            </div>
            {txHash ? (
              <Copyable value={txHash.startsWith("0x") ? txHash : `0x${txHash}`} />
            ) : (
              <span className="text-slate-500 text-sm">—</span>
            )}
          </div>
          <div className="py-1.5 flex items-start justify-between gap-3 flex-wrap">
            <div className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold pt-1">
              Block Number
            </div>
            <div className="text-sm text-slate-100 font-mono tabular-nums">
              {cert?.block_number ?? "—"}
            </div>
          </div>
          <div className="py-1.5 flex items-start justify-between gap-3 flex-wrap">
            <div className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold pt-1">
              Model Version
            </div>
            <div className="text-sm text-slate-100 font-mono">
              {cert?.model_version || "—"}
            </div>
          </div>
          <div className="py-1.5 flex items-start justify-between gap-3 flex-wrap">
            <div className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold pt-1">
              Timestamp / Registered At
            </div>
            <div className="text-sm text-slate-100 font-mono text-right">
              {cert?.registered_at
                ? formatDate(cert.registered_at)
                : "—"}
            </div>
          </div>
          <div className="py-1.5 flex items-start justify-between gap-3 flex-wrap">
            <div className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold pt-1">
              Recorder
            </div>
            {cert?.recorder ? (
              <Copyable value={cert.recorder} />
            ) : (
              <span className="text-slate-500 text-sm">—</span>
            )}
          </div>
        </div>

        <div className="space-y-4">
          <div className="rounded-lg border border-teal-900/30 bg-teal-950/10 p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="text-[11px] font-semibold uppercase tracking-wider text-teal-300">
                EVIDENCE INTEGRITY
              </div>
              {overall !== null && (
                overall ? (
                  <Badge variant="success">OVERALL VERIFIED</Badge>
                ) : (
                  <Badge variant="danger">OVERALL MISMATCH</Badge>
                )
              )}
            </div>
            <div className="space-y-3">
              <div className="flex items-center justify-between gap-3 flex-wrap rounded-md border border-slate-800 bg-slate-950/50 px-3 py-2">
                <div className="min-w-0">
                  <div className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold">
                    Image Hash
                  </div>
                  {cert?.image_hash ? (
                    <div className="mt-0.5">
                      <Copyable
                        value={cert.image_hash}
                        start={8}
                        end={8}
                        className="text-xs"
                      />
                    </div>
                  ) : (
                    <div className="text-xs text-slate-500">—</div>
                  )}
                </div>
                <div className="shrink-0">
                  {imgMatch === true ? (
                    <Badge variant="success">✓ MATCH</Badge>
                  ) : imgMatch === false ? (
                    <Badge variant="danger">✗ MISMATCH</Badge>
                  ) : verifyResult ? (
                    <Badge variant="warning">UNKNOWN</Badge>
                  ) : (
                    <Badge variant="default">UNVERIFIED</Badge>
                  )}
                </div>
              </div>
              <div className="flex items-center justify-between gap-3 flex-wrap rounded-md border border-slate-800 bg-slate-950/50 px-3 py-2">
                <div className="min-w-0">
                  <div className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold">
                    Prediction Hash
                  </div>
                  {cert?.prediction_hash ? (
                    <div className="mt-0.5">
                      <Copyable
                        value={cert.prediction_hash}
                        start={8}
                        end={8}
                        className="text-xs"
                      />
                    </div>
                  ) : (
                    <div className="text-xs text-slate-500">—</div>
                  )}
                </div>
                <div className="shrink-0">
                  {predMatch === true ? (
                    <Badge variant="success">✓ MATCH</Badge>
                  ) : predMatch === false ? (
                    <Badge variant="danger">✗ MISMATCH</Badge>
                  ) : verifyResult ? (
                    <Badge variant="warning">UNKNOWN</Badge>
                  ) : (
                    <Badge variant="default">UNVERIFIED</Badge>
                  )}
                </div>
              </div>
            </div>
            {verifyResult?.message && (
              <div className="mt-3 text-[11px] text-slate-400 leading-relaxed">
                {verifyResult.message}
              </div>
            )}
          </div>

          <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-4 space-y-2 text-xs text-slate-400 leading-relaxed">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-300 mb-1">
              AssessmentRegistry Storage
            </div>
            The on-chain contract stores cryptographic evidence:
            <ul className="list-disc pl-4 space-y-0.5 mt-1">
              <li>Record ID = keccak256(claim_id)</li>
              <li>Image hash = SHA-256(raw image bytes)</li>
              <li>
                Prediction hash = SHA-256(canonical prediction + claim_id)
              </li>
              <li>Model version, timestamp, recorder address</li>
            </ul>
            Raw AI reports remain <strong>OFF-CHAIN</strong>.
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function AgentTimeline({ claim }: { claim: ClaimResult }) {
  const steps = claim.steps || [];
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Clock className="h-4 w-4 text-cyan-400" />
          Pipeline Steps
        </CardTitle>
        <CardDescription>
          Ordered execution of the TruthChain 8-Agent pipeline plus blockchain
          certificate.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ol className="relative border-l border-slate-800 ml-3 space-y-4">
          {steps.length === 0 &&
            Object.entries(claim.agent_reports || {}).length === 0 && (
              <li className="ml-4 text-sm text-slate-500">
                No pipeline steps recorded yet.
              </li>
            )}
          {(steps.length > 0
            ? steps
            : Object.entries(claim.agent_reports || {}).map(([agent, r]) => ({
                agent,
                decision: (r as { decision?: string }).decision,
                risk_score: (r as { risk_score?: number }).risk_score,
                confidence: (r as { confidence?: number }).confidence,
              }))
          ).map((s, i) => {
            const ok =
              s.decision &&
              (s.decision.toUpperCase().includes("VERIFIED") ||
                s.decision.toUpperCase() === "PASS" ||
                s.decision.toUpperCase() === "CONSISTENT" ||
                s.decision.toUpperCase().includes("DETECTED") ||
                (s as { status?: string }).status === "COMPLETED");
            const Icon = ok ? CheckCircle2 : XCircle;
            return (
              <li key={i} className="ml-5">
                <span
                  className={cn(
                    "absolute -left-3 flex h-6 w-6 items-center justify-center rounded-full border border-slate-800 bg-slate-900",
                    ok
                      ? "text-emerald-400"
                      : s.agent === "BlockchainCertificate"
                        ? "text-purple-400"
                        : "text-amber-400",
                  )}
                >
                  <Icon className="h-3 w-3" />
                </span>
                <div className="flex items-center justify-between gap-3 flex-wrap">
                  <div>
                    <div className="text-sm font-semibold text-slate-100 font-mono">
                      {s.agent}
                    </div>
                    {typeof s.risk_score === "number" && (
                      <div className="text-[11px] text-slate-500 font-mono">
                        risk {s.risk_score.toFixed(4)}
                        {typeof s.confidence === "number" &&
                          ` · conf ${(s.confidence * 100).toFixed(1)}%`}
                      </div>
                    )}
                    {(s as { status?: string }).status && (
                      <div className="text-[11px] text-purple-400 font-mono mt-0.5">
                        {(s as { status?: string }).status} · block{" "}
                        {(s as { block_number?: number }).block_number ?? "—"}
                      </div>
                    )}
                  </div>
                  <Badge
                    variant={
                      s.decision === "VERIFIED" ||
                      s.decision === "PASS" ||
                      s.decision === "CONSISTENT" ||
                      (s as { status?: string }).status === "COMPLETED"
                        ? "success"
                        : "default"
                    }
                    className="font-mono"
                  >
                    {s.decision || (s as { status?: string }).status || "—"}
                  </Badge>
                </div>
              </li>
            );
          })}
        </ol>
      </CardContent>
    </Card>
  );
}

export default function ClaimDetailPage() {
  const params = useParams<{ claimId: string }>();
  const router = useRouter();
  const claimId = params?.claimId
    ? decodeURIComponent(params.claimId as string)
    : undefined;
  const query = useClaim(claimId);
  const verify = useVerifyBlockchainRecord();

  const claim = query.data;

  useEffect(() => {
    const recId = claim?.certificate?.record_id || claim?.claim_id || claimId;
    if (recId) {
      verify.mutate({ record_id: recId });
    }
  }, [claim?.certificate?.record_id, claim?.claim_id, claimId]);

  const runVerify = async () => {
    const recId = claim?.certificate?.record_id || claim?.claim_id || claimId;
    if (!recId) return;
    await verify.mutateAsync({
      record_id: recId,
    });
  };

  return (
    <div className="space-y-6">
      <SectionHeader
        eyebrow="Claim Assessment"
        title={claim?.claim_id || claimId || "Claim Details"}
        description="TruthChain 8-Agent AI consensus result plus Sepolia on-chain evidence."
        actions={
          <div className="flex items-center gap-2 flex-wrap">
            <Link href="/claims">
              <Button variant="outline" size="sm">
                <ArrowLeft className="h-3.5 w-3.5" />
                All Claims
              </Button>
            </Link>
            <Link href="/claims/new">
              <Button size="sm">
                <FilePlus2 className="h-3.5 w-3.5" />
                New Claim
              </Button>
            </Link>
          </div>
        }
      />

      {query.isLoading && (
        <div className="space-y-4">
          <Skeleton className="h-40 w-full rounded-xl" />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Skeleton className="h-48 w-full rounded-xl" />
            <Skeleton className="h-48 w-full rounded-xl" />
          </div>
        </div>
      )}

      {query.error && (
        <Alert variant="danger">
          <div className="flex items-start gap-2">
            <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
            <div>
              <div className="font-medium">Could not load claim</div>
              <div className="text-xs opacity-90 mt-0.5">
                {String(query.error.message || query.error)}
              </div>
              <div className="mt-3 flex gap-2 flex-wrap">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => query.refetch()}
                >
                  <RefreshCw className="h-3.5 w-3.5" /> Retry
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => router.back()}
                >
                  Go back
                </Button>
              </div>
            </div>
          </div>
        </Alert>
      )}

      {verify.error && (
        <Alert variant="warning">
          Verification error: {String(verify.error.message || verify.error)}
        </Alert>
      )}

      {claim && (
        <>
          <FinalVerdictCard claim={claim} />
          <ClaimOverviewCard claim={claim} />

          <div>
            <div className="text-[11px] font-semibold tracking-[0.2em] uppercase text-cyan-400 mb-3 flex items-center gap-2">
              <span className="h-px flex-1 bg-gradient-to-r from-transparent via-cyan-700/50 to-transparent" />
              OFF-CHAIN AI EVIDENCE
              <span className="h-px flex-1 bg-gradient-to-r from-transparent via-cyan-700/50 to-transparent" />
            </div>
            <div className="space-y-4">
              <SatelliteAgentCard
                report={claim.agent_reports?.SatelliteAgent}
                order={1}
              />
              <ImageAgentCard
                report={claim.agent_reports?.ImageAgent}
                order={2}
              />
              <SensorAgentCard
                report={claim.agent_reports?.SensorAgent}
                order={3}
                userTelemetry={
                  (claim.data?.sensor_data ||
                    claim.data?.sensor ||
                    claim.data?.telemetry) as Record<string, number>
                }
              />
              <TextAgentCard
                report={claim.agent_reports?.TextAgent}
                order={4}
              />
              <CrossModalAgentCard
                report={claim.agent_reports?.CrossModalAgent}
                order={5}
              />
              <RiskEngineCard
                report={claim.agent_reports?.RiskEngine}
                order={6}
              />
              <AdversarialVerifierCard
                report={claim.agent_reports?.AdversarialVerifier}
                order={7}
              />
              <ExplanationAgentCard
                report={claim.agent_reports?.ExplanationAgent}
                order={7}
              />
              <CommunicationAgentCard
                report={claim.agent_reports?.CommunicationAgent}
                order={8}
              />
            </div>
          </div>

          <div>
            <div className="text-[11px] font-semibold tracking-[0.2em] uppercase text-purple-400 mb-3 flex items-center gap-2">
              <span className="h-px flex-1 bg-gradient-to-r from-transparent via-purple-700/50 to-transparent" />
              ON-CHAIN IMMUTABLE PROOF
              <span className="h-px flex-1 bg-gradient-to-r from-transparent via-purple-700/50 to-transparent" />
            </div>
            <BlockchainCertificateCard
              claim={claim}
              onVerify={runVerify}
              verifying={verify.isPending}
              verifyResult={verify.data ?? null}
            />
          </div>

          <AgentTimeline claim={claim} />
        </>
      )}
    </div>
  );
}
