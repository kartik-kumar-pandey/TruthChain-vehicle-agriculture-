"use client";

import { useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { FormField, Input } from "@/components/ui/input";
import { SectionHeader, Alert, Skeleton, Separator } from "@/components/ui/primitives";
import {
  ShieldCheck,
  Search,
  Activity,
  FileText,
  Blocks,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  RefreshCw,
} from "lucide-react";
import Link from "next/link";
import { AGENT_ORDER, ETHERSCAN_BASE_URL } from "@/lib/constants";
import { Copyable } from "@/components/ui/copyable";
import {
  useBlockchainRecord,
  useClaim,
  useVerifyBlockchainRecord,
} from "@/hooks/useTruthChain";
import { cn, formatDate } from "@/lib/utils";

type IntegrityRowProps = {
  label: string;
  match: boolean | null;
  expected?: string;
  computed?: string;
};
function IntegrityRow({ label, match, expected, computed }: IntegrityRowProps) {
  return (
    <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950/50 p-4 transition-colors">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
            {label}
          </div>
          {expected && (
            <div className="mt-1">
              <Copyable
                value={expected}
                start={8}
                end={8}
                className="text-xs"
                label="Expected"
              />
            </div>
          )}
          {computed && computed !== expected && (
            <div className="mt-1">
              <Copyable
                value={computed}
                start={8}
                end={8}
                className="text-xs text-rose-300"
                label="Computed"
              />
            </div>
          )}
        </div>
        <div className="shrink-0">
          {match === true ? (
            <Badge variant="success" className="font-mono">
              <CheckCircle2 className="h-3.5 w-3.5 mr-1" /> MATCH
            </Badge>
          ) : match === false ? (
            <Badge variant="danger" className="font-mono">
              <XCircle className="h-3.5 w-3.5 mr-1" /> MISMATCH
            </Badge>
          ) : (
            <Badge variant="default" className="font-mono">
              NOT CHECKED
            </Badge>
          )}
        </div>
      </div>
    </div>
  );
}

export default function EvidenceInspectorPage() {
  const [claimIdInput, setClaimIdInput] = useState("");
  const [activeClaim, setActiveClaim] = useState<string | null>(null);
  const [activeRecordId, setActiveRecordId] = useState<string | null>(null);

  const claimQuery = useClaim(activeClaim);
  const recordQuery = useBlockchainRecord(activeRecordId);
  const verify = useVerifyBlockchainRecord();

  const runSearch = (e?: React.FormEvent) => {
    e?.preventDefault();
    const id = claimIdInput.trim();
    if (!id) return;
    setActiveClaim(id);
    setActiveRecordId(null);
  };

  const claim = claimQuery.data;
  const cert = claim?.certificate;

  const runVerify = async () => {
    const recId = cert?.record_id || activeRecordId || activeClaim;
    if (!recId) return;
    await verify.mutateAsync({ record_id: recId });
  };

  const verified = verify.data;
  const imgMatch =
    verified?.image_integrity?.matched ?? verified?.image_hash_match ?? null;
  const predMatch =
    verified?.prediction_integrity?.matched ??
    verified?.prediction_hash_match ?? null;
  const overall = verified
    ? verified.verified === true || verified.is_match === true
    : null;

  return (
    <div className="space-y-6">
      <SectionHeader
        eyebrow="Forensic Integrity"
        title="Evidence Inspector"
        description="Independent cryptographic verification. Searches claim results from the backend and cross-checks image + prediction hashes against the on-chain AssessmentRegistry."
        actions={
          <Badge variant="evidence" className="font-mono text-[10px]">
            POST /api/v1/blockchain/verify
          </Badge>
        }
      />

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Search className="h-4 w-4 text-cyan-400" />
            Search Evidence
          </CardTitle>
          <CardDescription>
            Enter a TruthChain Claim ID (e.g. TC-PRODUCTION-E2E-002) to load
            the AI consensus result and verify its integrity on-chain.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form
            onSubmit={runSearch}
            className="flex flex-col sm:flex-row items-stretch sm:items-end gap-3"
          >
            <div className="flex-1 min-w-0">
              <FormField label="Claim ID" required>
                <Input
                  placeholder="TC-PRODUCTION-E2E-002"
                  value={claimIdInput}
                  onChange={(e) => setClaimIdInput(e.target.value)}
                />
              </FormField>
            </div>
            <div className="flex gap-2">
              <Button type="submit" size="md">
                <Search className="h-4 w-4" />
                Inspect
              </Button>
              {activeClaim && (
                <Link href={`/claims/${encodeURIComponent(activeClaim)}`}>
                  <Button type="button" variant="outline" size="md">
                    Open claim
                  </Button>
                </Link>
              )}
            </div>
          </form>
        </CardContent>
      </Card>

      {claimQuery.isLoading && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <Skeleton className="h-64 w-full rounded-xl" />
          <Skeleton className="h-64 w-full rounded-xl" />
          <Skeleton className="h-64 w-full rounded-xl" />
        </div>
      )}

      {claimQuery.error && (
        <Alert variant="warning">
          <div className="flex items-start gap-2">
            <AlertTriangle className="h-4 w-4 mt-0.5" />
            <div>
              <div className="font-medium">
                Could not load claim{" "}
                <span className="font-mono">{activeClaim}</span>
              </div>
              <div className="text-xs opacity-90 mt-0.5">
                {String(claimQuery.error.message || claimQuery.error)}
              </div>
              <div className="mt-2 text-xs">
                Try also verifying directly by Record ID:
              </div>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  const rec = (
                    document.getElementById(
                      "direct-record-id",
                    ) as HTMLInputElement
                  ).value.trim();
                  if (rec) {
                    setActiveRecordId(rec);
                    setActiveClaim(null);
                  }
                }}
                className="mt-2 flex items-end gap-2 max-w-lg"
              >
                <div className="flex-1 min-w-0">
                  <Input
                    id="direct-record-id"
                    placeholder="0x record id hex"
                  />
                </div>
                <Button size="sm" variant="outline">
                  Lookup Record
                </Button>
              </form>
            </div>
          </div>
        </Alert>
      )}

      {claim && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileText className="h-4 w-4 text-cyan-400" />
                CLAIM
              </CardTitle>
              <CardDescription>Identifiers</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-1">
                  Claim ID
                </div>
                <Copyable
                  value={claim.claim_id}
                  truncate={false}
                  className="text-sm"
                />
              </div>
              <Separator />
              <IntegrityRow
                label="Image Hash"
                match={imgMatch}
                expected={cert?.image_hash || ""}
                computed={verified?.supplied_image_hash}
              />
              <IntegrityRow
                label="Prediction Hash"
                match={predMatch}
                expected={cert?.prediction_hash || ""}
                computed={verified?.supplied_prediction_hash}
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Activity className="h-4 w-4 text-indigo-400" />
                AI PIPELINE
              </CardTitle>
              <CardDescription>
                8-Agent Consensus Engine (OFF-CHAIN)
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              {AGENT_ORDER.map((name, i) => {
                const report = claim.agent_reports?.[name as keyof typeof claim.agent_reports];
                const present = Boolean(report);
                const decision = (report as { decision?: string } | undefined)
                  ?.decision;
                const ok =
                  present &&
                  decision &&
                  (decision.toUpperCase().includes("VERIFIED") ||
                    decision.toUpperCase() === "PASS" ||
                    decision.toUpperCase() === "CONSISTENT" ||
                    decision.toUpperCase().includes("DETECTED"));
                return (
                  <div
                    key={name}
                    className={cn(
                      "flex items-center justify-between rounded-md border px-3 py-2",
                      present
                        ? "border-slate-800 bg-slate-900/50"
                        : "border-dashed border-slate-800 bg-slate-950/30",
                    )}
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <span
                        className={cn(
                          "h-5 w-5 rounded-full border border-slate-700 flex items-center justify-center text-[10px] font-mono shrink-0",
                          ok
                            ? "bg-emerald-500/10 border-emerald-800 text-emerald-300"
                            : present
                              ? "bg-amber-500/10 border-amber-800 text-amber-300"
                              : "bg-slate-900 text-slate-500",
                        )}
                      >
                        {i + 1}
                      </span>
                      <span
                        className={cn(
                          "text-sm font-medium",
                          present ? "text-slate-100" : "text-slate-500 italic",
                        )}
                      >
                        {name}
                      </span>
                    </div>
                    <div>
                      {present ? (
                        <Badge
                          variant={
                            ok
                              ? "success"
                              : decision?.toUpperCase().includes("FAIL") ||
                                  decision?.toUpperCase().includes("FRAUD")
                                ? "danger"
                                : "warning"
                          }
                          className="font-mono text-[10px]"
                        >
                          {decision}
                        </Badge>
                      ) : (
                        <span className="text-[10px] text-slate-600 font-mono uppercase">
                          Not in result
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </CardContent>
          </Card>

          <Card className="border-purple-900/40 bg-purple-950/5">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Blocks className="h-4 w-4 text-purple-400" />
                BLOCKCHAIN
              </CardTitle>
              <CardDescription>
                AssessmentRegistry · ON-CHAIN
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              {cert ? (
                <>
                  <div className="flex justify-between items-baseline gap-3">
                    <span className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold">
                      Network
                    </span>
                    <span className="font-mono text-slate-100">
                      {cert.network || "Sepolia"}
                    </span>
                  </div>
                  <div className="flex justify-between items-baseline gap-3">
                    <span className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold">
                      Contract
                    </span>
                    {cert.contract_address ? (
                      <Copyable
                        value={cert.contract_address}
                        start={6}
                        end={6}
                      />
                    ) : (
                      <span className="text-slate-500">—</span>
                    )}
                  </div>
                  <div className="flex justify-between items-baseline gap-3 flex-wrap">
                    <span className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold">
                      Record ID
                    </span>
                    {cert.record_id ? (
                      <Copyable value={cert.record_id} start={6} end={6} />
                    ) : (
                      <span className="text-slate-500">—</span>
                    )}
                  </div>
                  <div className="flex justify-between items-baseline gap-3 flex-wrap">
                    <span className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold">
                      Transaction
                    </span>
                    {cert.transaction_hash ? (
                      <a
                        href={`${ETHERSCAN_BASE_URL}/tx/${cert.transaction_hash.startsWith("0x") ? cert.transaction_hash : `0x${cert.transaction_hash}`}`}
                        target="_blank"
                        rel="noreferrer noopener"
                        className="text-purple-300 hover:text-purple-200"
                      >
                        <Copyable
                          value={
                            cert.transaction_hash.startsWith("0x")
                              ? cert.transaction_hash
                              : `0x${cert.transaction_hash}`
                          }
                          start={6}
                          end={6}
                        />
                      </a>
                    ) : (
                      <span className="text-slate-500">—</span>
                    )}
                  </div>
                  <div className="flex justify-between items-baseline gap-3">
                    <span className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold">
                      Block
                    </span>
                    <span className="font-mono text-slate-100 tabular-nums">
                      {cert.block_number ?? "—"}
                    </span>
                  </div>
                  <div className="flex justify-between items-baseline gap-3">
                    <span className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold">
                      Model
                    </span>
                    <span className="font-mono text-slate-100">
                      {cert.model_version || "—"}
                    </span>
                  </div>
                  <div className="flex justify-between items-baseline gap-3">
                    <span className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold">
                      Timestamp
                    </span>
                    <span className="font-mono text-slate-100 text-right text-xs">
                      {formatDate(cert.registered_at as number)}
                    </span>
                  </div>
                  <div className="flex justify-between items-baseline gap-3 flex-wrap">
                    <span className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold">
                      Recorder
                    </span>
                    {cert.recorder ? (
                      <Copyable value={cert.recorder} start={6} end={6} />
                    ) : (
                      <span className="text-slate-500">—</span>
                    )}
                  </div>
                </>
              ) : (
                <div className="text-xs text-slate-500 italic">
                  No certificate attached to this claim result.
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {(claim || recordQuery.data) && (
        <Card className="border-teal-900/40 bg-teal-950/5">
          <CardHeader>
            <div className="flex items-start justify-between flex-wrap gap-3">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <ShieldCheck className="h-4 w-4 text-teal-400" />
                  INTEGRITY
                </CardTitle>
                <CardDescription>
                  Independent re-hash and on-chain comparison. Click Verify
                  Evidence to invoke the backend verifier.
                </CardDescription>
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                {overall === true ? (
                  <Badge variant="success">OVERALL · VERIFIED</Badge>
                ) : overall === false ? (
                  <Badge variant="danger">OVERALL · TAMPER DETECTED</Badge>
                ) : null}
                <Button
                  size="sm"
                  onClick={runVerify}
                  disabled={
                    !(cert?.record_id || activeRecordId) || verify.isPending
                  }
                  variant="success"
                >
                  {verify.isPending ? (
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
              </div>
            </div>
          </CardHeader>
          <CardContent className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <IntegrityRow
              label="Image hash"
              match={imgMatch}
              expected={
                verified?.image_integrity?.expected_hash ||
                verified?.on_chain_image_hash ||
                cert?.image_hash ||
                ""
              }
              computed={
                verified?.image_integrity?.computed_hash ||
                verified?.supplied_image_hash ||
                undefined
              }
            />
            <IntegrityRow
              label="Prediction hash"
              match={predMatch}
              expected={
                verified?.prediction_integrity?.expected_hash ||
                verified?.on_chain_prediction_hash ||
                cert?.prediction_hash ||
                ""
              }
              computed={
                verified?.prediction_integrity?.computed_hash ||
                verified?.supplied_prediction_hash ||
                undefined
              }
            />
            <div className="rounded-lg border-2 p-4 flex flex-col items-start justify-between gap-2 bg-slate-950/50 border-teal-800/50">
              <div className="text-[11px] font-semibold uppercase tracking-wider text-teal-300">
                Overall
              </div>
              <div
                className={cn(
                  "text-2xl font-black tabular-nums tracking-tight",
                  overall === true
                    ? "text-emerald-300"
                    : overall === false
                      ? "text-rose-300"
                      : "text-slate-400",
                )}
              >
                {overall === true
                  ? "VERIFIED"
                  : overall === false
                    ? "TAMPERED"
                    : "NOT VERIFIED"}
              </div>
              <div className="text-xs text-slate-400 leading-relaxed">
                {verified?.message ||
                  "Run Verify Evidence to independently confirm hashes match Sepolia storage."}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {recordQuery.data && !claim && (
        <Alert variant="info">
          <div className="font-mono text-xs break-all">
            Direct record result: {JSON.stringify(recordQuery.data, null, 2)}
          </div>
        </Alert>
      )}
    </div>
  );
}
