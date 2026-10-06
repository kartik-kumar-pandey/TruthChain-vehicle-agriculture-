"use client";

import { useClaims, useBlockchainRecords } from "@/hooks/useTruthChain";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { SectionHeader, Skeleton, Separator } from "@/components/ui/primitives";
import {
  Activity,
  ShieldCheck,
  AlertTriangle,
  Blocks,
  FileText,
  ArrowRight,
  Clock,
  CheckCircle2,
} from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { AGENT_ORDER } from "@/lib/constants";
import type { ClaimResult } from "@/types/claim";
import { Copyable } from "@/components/ui/copyable";

function StatCard({
  title,
  value,
  description,
  icon: Icon,
  accent,
}: {
  title: string;
  value: React.ReactNode;
  description?: string;
  icon: React.ComponentType<{ className?: string }>;
  accent:
    | "cyan"
    | "emerald"
    | "amber"
    | "purple"
    | "slate";
}) {
  const accents: Record<string, string> = {
    cyan: "from-cyan-500/20 to-cyan-500/0 text-cyan-400 border-cyan-500/30",
    emerald:
      "from-emerald-500/20 to-emerald-500/0 text-emerald-400 border-emerald-500/30",
    amber:
      "from-amber-500/20 to-amber-500/0 text-amber-400 border-amber-500/30",
    purple:
      "from-purple-500/20 to-purple-500/0 text-purple-400 border-purple-500/30",
    slate:
      "from-slate-500/20 to-slate-500/0 text-slate-400 border-slate-500/30",
  };
  return (
    <Card className="overflow-hidden">
      <CardContent className="p-5">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="text-xs font-medium text-slate-400 uppercase tracking-wider">
              {title}
            </div>
            <div className="mt-2 text-2xl md:text-3xl font-semibold text-slate-50 tabular-nums">
              {value}
            </div>
            {description && (
              <div className="mt-1.5 text-xs text-slate-500">
                {description}
              </div>
            )}
          </div>
          <div
            className={`h-11 w-11 shrink-0 rounded-xl border bg-gradient-to-b ${accents[accent]} flex items-center justify-center`}
          >
            <Icon className="h-5 w-5" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function PipelineActivity({ claims }: { claims: ClaimResult[] }) {
  const recent = claims.slice(0, 6);
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-4 w-4 text-cyan-400" />
              Pipeline Activity
            </CardTitle>
            <CardDescription>
              Real AI consensus & blockchain certification status
            </CardDescription>
          </div>
          <Badge variant="info" className="font-mono text-[10px]">
            {AGENT_ORDER.length}-Agent Pipeline
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-2">
        {recent.length === 0 && (
          <div className="py-10 text-center text-sm text-slate-500 border border-dashed border-slate-800 rounded-lg">
            No claims evaluated yet.
            <div className="mt-3">
              <Link href="/claims/new">
                <Button size="sm" variant="outline">
                  Create first claim <ArrowRight className="h-3.5 w-3.5" />
                </Button>
              </Link>
            </div>
          </div>
        )}
        {recent.map((c, idx) => {
          const claimId =
            c.claim_id ||
            (c.meta as { claim_id?: string } | undefined)?.claim_id ||
            (c.claim_metadata as { claim_id?: string } | undefined)?.claim_id ||
            `recent-claim-${idx}`;
          const agents = c.agent_reports || {};
          const completed = Object.keys(agents).length;
          const bc = c.certificate?.status || "PENDING";
          const verdict = c.final_verdict || "PENDING";
          const verdictVariant =
            verdict === "VERIFIED"
              ? "success"
              : verdict === "FRAUD"
                ? "danger"
                : verdict === "REVIEW"
                  ? "warning"
                  : "default";
          return (
            <div
              key={claimId}
              className="rounded-lg border border-slate-800 bg-slate-900/40 p-3.5 hover:bg-slate-900/70 transition-colors"
            >
              <div className="flex items-start justify-between gap-4 flex-wrap">
                <div className="min-w-0">
                  <Link
                    href={`/claims/${encodeURIComponent(claimId)}`}
                    className="text-sm font-medium text-slate-100 hover:text-cyan-300 transition-colors font-mono truncate"
                  >
                    {claimId}
                  </Link>
                  <div className="mt-1 flex items-center gap-2 flex-wrap">
                    <Badge variant={verdictVariant as never}>
                      {verdict}
                    </Badge>
                    <Badge variant="blockchain" className="font-mono">
                      {bc}
                    </Badge>
                    <span className="text-[11px] text-slate-500 font-mono">
                      Agents {completed}/{AGENT_ORDER.length}
                    </span>
                  </div>
                </div>
                <div className="text-right shrink-0">
                  <div className="text-[11px] text-slate-500">Fraud Score</div>
                  <div className="text-lg font-semibold tabular-nums text-slate-200">
                    {c.fraud_score ?? "—"}
                    <span className="text-xs text-slate-500 ml-1">/100</span>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}

export default function DashboardPage() {
  const claimsQuery = useClaims();
  const bcQuery = useBlockchainRecords(20);

  const claims = claimsQuery.data?.claims || [];

  const total = claims.length;
  const verified = claims.filter(
    (c) => c.final_verdict === "VERIFIED",
  ).length;
  const reviewOrFraud = claims.filter(
    (c) => c.final_verdict === "REVIEW" || c.final_verdict === "FRAUD",
  ).length;
  const bcRegistered = claims.filter(
    (c) =>
      c.certificate?.status === "REGISTERED" ||
      c.certificate?.status === "ALREADY_REGISTERED",
  ).length;
  const pipelineComplete = claims.filter(
    (c) => c.pipeline_status === "COMPLETE",
  ).length;

  const bcRecords = (bcQuery.data || []).slice(0, 5);

  return (
    <div className="space-y-6">
      <SectionHeader
        eyebrow="Operations Overview"
        title="TruthChain Control Center"
        description="8-Agent AI consensus engine with cryptographic evidence anchoring on Sepolia. All values are loaded from the live backend API."
        actions={
          <Link href="/claims/new">
            <Button size="lg">
              <FileText className="h-4 w-4" />
              Evaluate New Claim
            </Button>
          </Link>
        }
      />

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard
          title="Total Claims"
          value={claimsQuery.isLoading ? <Skeleton className="w-16 h-8 inline-block" /> : total}
          description={
            claimsQuery.isLoading
              ? "Loading…"
              : `${pipelineComplete} pipelines completed`
          }
          icon={Activity}
          accent="cyan"
        />
        <StatCard
          title="Verified Claims"
          value={claimsQuery.isLoading ? <Skeleton className="w-16 h-8 inline-block" /> : verified}
          description="Final verdict: VERIFIED"
          icon={CheckCircle2}
          accent="emerald"
        />
        <StatCard
          title="Review / Fraud"
          value={claimsQuery.isLoading ? <Skeleton className="w-16 h-8 inline-block" /> : reviewOrFraud}
          description="Manual review queue or fraud flag"
          icon={AlertTriangle}
          accent="amber"
        />
        <StatCard
          title="Blockchain Registered"
          value={claimsQuery.isLoading ? <Skeleton className="w-16 h-8 inline-block" /> : bcRegistered}
          description="Anchored on Sepolia AssessmentRegistry"
          icon={Blocks}
          accent="purple"
        />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <div className="xl:col-span-2">
          <PipelineActivity claims={claims} />
        </div>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <Blocks className="h-4 w-4 text-purple-400" />
                  Blockchain Registrations
                </CardTitle>
                <CardDescription>
                  Recent on-chain Sepolia records
                </CardDescription>
              </div>
              <Link
                href="/blockchain"
                className="text-xs text-cyan-400 hover:text-cyan-300 inline-flex items-center gap-1"
              >
                View all <ArrowRight className="h-3 w-3" />
              </Link>
            </div>
          </CardHeader>
          <CardContent className="space-y-2.5">
            {bcQuery.isLoading &&
              Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-14 w-full" />
              ))}
            {!bcQuery.isLoading && bcRecords.length === 0 && (
              <div className="py-8 text-center text-xs text-slate-500 border border-dashed border-slate-800 rounded-lg">
                No on-chain records yet.
              </div>
            )}
            {bcRecords.map((r, idx) => (
              <div
                key={r.record_id || String(idx)}
                className="rounded-lg border border-purple-900/30 bg-purple-950/10 p-3"
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <div className="text-xs font-mono text-purple-300">
                      {r.claim_id || r.vehicle_id || "—"}
                    </div>
                    {r.record_id && (
                      <div className="mt-1 text-[11px] text-slate-400">
                        <Copyable value={r.record_id} start={6} end={6} />
                      </div>
                    )}
                  </div>
                  <div className="text-right shrink-0">
                    {r.block_number ? (
                      <div className="flex items-center gap-1 text-[11px] text-slate-400">
                        <Clock className="h-3 w-3" />
                        Block {r.block_number}
                      </div>
                    ) : (
                      <Badge variant="blockchain" className="font-mono">
                        Registered
                      </Badge>
                    )}
                  </div>
                </div>
              </div>
            ))}
            <Separator />
            <div className="flex items-center justify-between text-[11px] text-slate-500 pt-1">
              <div>Verification Status</div>
              <div className="flex items-center gap-1.5">
                <ShieldCheck className="h-3.5 w-3.5 text-teal-400" />
                Off-chain evidence + On-chain proof
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
