"use client";

import { useMemo, useState } from "react";
import { useClaims } from "@/hooks/useTruthChain";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { SectionHeader, Skeleton, Alert } from "@/components/ui/primitives";
import {
  Files,
  ArrowUpDown,
  ExternalLink,
  AlertTriangle,
  CheckCircle2,
} from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { AGENT_ORDER } from "@/lib/constants";
import type { ClaimFilter, ClaimResult } from "@/types/claim";
import { Copyable } from "@/components/ui/copyable";

const FILTERS: { key: ClaimFilter; label: string }[] = [
  { key: "ALL", label: "All" },
  { key: "VERIFIED", label: "Verified" },
  { key: "REVIEW", label: "Review" },
  { key: "FRAUD", label: "Fraud" },
  { key: "BLOCKCHAIN_REGISTERED", label: "On-Chain" },
  { key: "FAILED", label: "Failed" },
];

function claimMatchesFilter(c: ClaimResult, filter: ClaimFilter): boolean {
  switch (filter) {
    case "ALL":
      return true;
    case "VERIFIED":
      return c.final_verdict === "VERIFIED" || c.state === "COMPLETED";
    case "REVIEW":
      return c.final_verdict === "REVIEW" || c.final_verdict === "NEEDS_REVIEW" || c.final_verdict === "REVIEW_REQUIRED";
    case "FRAUD":
      return c.final_verdict === "FRAUD" || c.final_verdict === "REJECTED";
    case "BLOCKCHAIN_REGISTERED":
      return (
        c.certificate?.status === "REGISTERED" ||
        c.certificate?.status === "ALREADY_REGISTERED" ||
        c.state === "BLOCKCHAIN_REGISTERED"
      );
    case "FAILED":
      return (
        c.final_verdict === "FAILED" || c.pipeline_status === "FAILED"
      );
    default:
      return true;
  }
}

function verdictBadge(verdict?: string) {
  const v = (verdict || "PENDING").toUpperCase();
  if (v === "VERIFIED")
    return <Badge variant="success">{v}</Badge>;
  if (v === "FRAUD") return <Badge variant="danger">{v}</Badge>;
  if (v === "REVIEW") return <Badge variant="warning">{v}</Badge>;
  if (v === "PENDING") return <Badge variant="default">{v}</Badge>;
  if (v === "FAILED") return <Badge variant="danger">{v}</Badge>;
  return <Badge variant="default">{v}</Badge>;
}

function vehicleFromClaim(c: ClaimResult): string {
  const d = c.data;
  if (!d) return "—";
  const vin = (d as { vin?: string; vehicle?: string }).vin ||
    (d as { vehicle_registration?: string }).vehicle_registration ||
    (d as { vehicle?: string }).vehicle;
  if (vin) return String(vin);
  return "Motor Vehicle";
}

function incidentDate(c: ClaimResult): string {
  const d = c.data as { incident_date?: string } | undefined;
  return d?.incident_date || "—";
}

export default function ClaimsListPage() {
  const query = useClaims();
  const [filter, setFilter] = useState<ClaimFilter>("ALL");

  const rows = useMemo(() => {
    const list = query.data?.claims || [];
    return list.filter((c) => claimMatchesFilter(c, filter));
  }, [query.data, filter]);

  return (
    <div className="space-y-6">
      <SectionHeader
        eyebrow="Claim Registry"
        title="Claims"
        description="All processed claims with 8-agent AI consensus status, fraud score, and Sepolia blockchain registration. Filters are applied from real backend data."
      />

      <div className="flex flex-wrap gap-2">
        {FILTERS.map((f) => (
          <Button
            key={f.key}
            size="sm"
            variant={filter === f.key ? "default" : "outline"}
            onClick={() => setFilter(f.key)}
          >
            {f.label}
          </Button>
        ))}
      </div>

      {query.error && (
        <Alert variant="danger">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4" />
            Could not load claims: {String(query.error.message || query.error)}
          </div>
        </Alert>
      )}

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div className="flex items-center gap-2">
              <Files className="h-4 w-4 text-cyan-400" />
              <CardTitle>Assessment Records</CardTitle>
              <Badge variant="info" className="font-mono">
                {query.isLoading
                  ? "…"
                  : `${rows.length} / ${query.data?.count || 0}`}
              </Badge>
            </div>
            <CardDescription className="flex items-center gap-1.5">
              <ArrowUpDown className="h-3 w-3" />
              Most recent first
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-800 bg-slate-900/60 text-left text-[11px] uppercase tracking-wider text-slate-400">
                  <th className="px-5 py-3 font-medium">Claim ID</th>
                  <th className="px-5 py-3 font-medium">Vehicle</th>
                  <th className="px-5 py-3 font-medium">Date</th>
                  <th className="px-5 py-3 font-medium">Verdict</th>
                  <th className="px-5 py-3 font-medium text-right">Fraud</th>
                  <th className="px-5 py-3 font-medium">Pipeline</th>
                  <th className="px-5 py-3 font-medium">Blockchain</th>
                  <th className="px-5 py-3 font-medium">Record ID</th>
                </tr>
              </thead>
              <tbody>
                {query.isLoading &&
                  Array.from({ length: 4 }).map((_, i) => (
                    <tr
                      key={i}
                      className="border-b border-slate-800/70 last:border-none"
                    >
                      {Array.from({ length: 8 }).map((__, j) => (
                        <td key={j} className="px-5 py-4">
                          <Skeleton className="h-5 w-full" />
                        </td>
                      ))}
                    </tr>
                  ))}
                {!query.isLoading && rows.length === 0 && (
                  <tr>
                    <td
                      colSpan={8}
                      className="px-5 py-16 text-center text-sm text-slate-500"
                    >
                      No claims match the current filter.
                      <div className="mt-3">
                        <Link href="/claims/new">
                          <Button size="sm" variant="outline">
                            Submit a claim for evaluation
                          </Button>
                        </Link>
                      </div>
                    </td>
                  </tr>
                )}
                {rows.map((c, index) => {
                  const claimId =
                    c.claim_id ||
                    (c.meta as { claim_id?: string } | undefined)?.claim_id ||
                    (c.claim_metadata as { claim_id?: string } | undefined)?.claim_id ||
                    `claim-${index}`;
                  const agents = c.agent_reports || {};
                  const agentCount = Object.keys(agents).length;
                  const bcStatus = c.certificate?.status || "PENDING";
                  const fraud = typeof c.fraud_score === "number"
                    ? c.fraud_score
                    : null;
                  return (
                    <tr
                      key={claimId}
                      className="border-b border-slate-800/70 last:border-none hover:bg-slate-900/40 transition-colors"
                    >
                      <td className="px-5 py-4">
                        <Link
                          href={`/claims/${encodeURIComponent(claimId)}`}
                          className="group inline-flex items-center gap-2"
                        >
                          <span className="font-mono text-sm text-slate-100 group-hover:text-cyan-300 transition-colors">
                            {claimId}
                          </span>
                          <ExternalLink className="h-3 w-3 text-slate-500 group-hover:text-cyan-400" />
                        </Link>
                      </td>
                      <td className="px-5 py-4 text-slate-300">
                        {vehicleFromClaim(c)}
                      </td>
                      <td className="px-5 py-4 text-slate-400 text-xs font-mono">
                        {incidentDate(c)}
                      </td>
                      <td className="px-5 py-4">
                        {verdictBadge(c.final_verdict)}
                      </td>
                      <td className="px-5 py-4 text-right tabular-nums">
                        <span
                          className={
                            fraud === 0
                              ? "text-emerald-400"
                              : fraud !== null && fraud >= 65
                                ? "text-red-400"
                                : fraud !== null && fraud >= 30
                                  ? "text-amber-400"
                                  : "text-slate-300"
                          }
                        >
                          {fraud === null ? "—" : fraud}
                        </span>
                        <span className="text-xs text-slate-500 ml-1">/100</span>
                      </td>
                      <td className="px-5 py-4">
                        <span className="inline-flex items-center gap-2">
                          {c.pipeline_status === "COMPLETE" ? (
                            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                          ) : (
                            <AlertTriangle className="h-3.5 w-3.5 text-amber-400" />
                          )}
                          <span className="font-mono text-[11px] text-slate-300">
                            {agentCount}
                            <span className="text-slate-500">
                              /{AGENT_ORDER.length}
                            </span>
                          </span>
                        </span>
                      </td>
                      <td className="px-5 py-4">
                        <Badge
                          variant={
                            bcStatus === "REGISTERED" ||
                            bcStatus === "ALREADY_REGISTERED"
                              ? "blockchain"
                              : "default"
                          }
                          className="font-mono text-[10px]"
                        >
                          {bcStatus}
                        </Badge>
                      </td>
                      <td className="px-5 py-4 max-w-[180px]">
                        {c.certificate?.record_id ? (
                          <Copyable
                            value={c.certificate.record_id}
                            start={6}
                            end={6}
                          />
                        ) : (
                          <span className="text-xs text-slate-500">—</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
