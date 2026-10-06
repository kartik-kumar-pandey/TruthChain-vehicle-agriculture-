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
  Blocks,
  Activity,
  ShieldCheck,
  Database,
  Server,
  ExternalLink,
  AlertTriangle,
  CheckCircle2,
} from "lucide-react";
import { useBlockchainStatus, useBlockchainRecords } from "@/hooks/useTruthChain";
import { ETHERSCAN_BASE_URL } from "@/lib/constants";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Copyable } from "@/components/ui/copyable";
import { formatDate } from "@/lib/utils";
import type { BlockchainRecord } from "@/types/blockchain";

function StatusDot({
  live,
}: {
  live: boolean | null | undefined;
}) {
  return (
    <span className="inline-flex h-2 w-2 rounded-full bg-slate-500 relative">
      {live === true ? (
        <span className="absolute inset-0 rounded-full bg-emerald-400 animate-ping opacity-60" />
      ) : null}
      <span
        className={
          "absolute inset-0 rounded-full " +
          (live === true
            ? "bg-emerald-400"
            : live === false
              ? "bg-amber-400"
              : "bg-slate-500")
        }
      />
    </span>
  );
}

function pickField<T>(r: BlockchainRecord, keys: string[]): T | undefined {
  for (const k of keys) {
    // Support dot-notation paths like "vision.model"
    const parts = k.split(".");
    let val: unknown = r;
    for (const p of parts) {
      if (val == null || typeof val !== "object") { val = undefined; break; }
      val = (val as Record<string, unknown>)[p];
    }
    if (val !== undefined) return val as T;
  }
  return undefined;
}

function isSepolia(networkStr?: string): boolean {
  if (!networkStr) return false;
  const lower = networkStr.toLowerCase();
  return lower.includes("sepolia") || lower.includes("11155111");
}

export default function BlockchainPage() {
  const status = useBlockchainStatus();
  const records = useBlockchainRecords(50);

  const live =
    status.data?.blockchain_connected ??
    status.data?.connected ??
    null;

  const list = records.data || [];

  return (
    <div className="space-y-6">
      <SectionHeader
        eyebrow="Ledger & Audit"
        title="Blockchain"
        description="AssessmentRegistry on Sepolia. Network status, contract binding, and list of registered cryptographic commitments."
        actions={
          <Badge variant="blockchain" className="font-mono text-[10px]">
            GET /api/v1/blockchain/status & /records
          </Badge>
        }
      />

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        <Card className="border-purple-900/40 bg-purple-950/10">
          <CardContent className="p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                  Connection
                </div>
                <div className="mt-2 flex items-center gap-2">
                  <StatusDot live={live} />
                  <span className="text-xl font-bold text-slate-100">
                    {status.isLoading
                      ? "…"
                      : live
                        ? "Live RPC"
                        : status.data
                          ? "Ledger Mode"
                          : "Unknown"}
                  </span>
                </div>
              </div>
              <div className="h-11 w-11 rounded-xl border border-purple-700/40 bg-gradient-to-b from-purple-500/20 flex items-center justify-center">
                <Blocks className="h-5 w-5 text-purple-400" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                  Network
                </div>
                <div className="mt-2 text-xl font-bold text-slate-100">
                  {status.isLoading ? (
                    <Skeleton className="h-7 w-32" />
                  ) : (
                    status.data?.network || status.data?.ledger_type || "—"
                  )}
                </div>
              </div>
              <div className="h-11 w-11 rounded-xl border border-slate-700 bg-slate-800/40 flex items-center justify-center">
                <Server className="h-5 w-5 text-slate-400" />
              </div>
            </div>
            {status.data?.chain_id && (
              <div className="mt-2 text-xs font-mono text-slate-400">
                Chain ID: {status.data.chain_id}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                  Contract
                </div>
                <div className="mt-2">
                  {status.isLoading ? (
                    <Skeleton className="h-5 w-44" />
                  ) : (
                    status.data?.contract_address && (
                      <Copyable
                        value={status.data.contract_address as string}
                        start={6}
                        end={6}
                        className="text-sm"
                      />
                    )
                  )}
                </div>
              </div>
              <div className="h-11 w-11 rounded-xl border border-slate-700 bg-slate-800/40 flex items-center justify-center">
                <ShieldCheck className="h-5 w-5 text-cyan-400" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                  Assessments
                </div>
                <div className="mt-2 text-2xl font-bold text-slate-100 tabular-nums">
                  {records.isLoading
                    ? "…"
                    : records.data?.length ?? 0}
                </div>
              </div>
              <div className="h-11 w-11 rounded-xl border border-slate-700 bg-slate-800/40 flex items-center justify-center">
                <Database className="h-5 w-5 text-emerald-400" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {status.error && (
        <Alert variant="warning">
          <div className="flex items-start gap-2">
            <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
            <div>
              <div className="font-medium">Blockchain status unavailable</div>
              <div className="text-xs opacity-90 mt-0.5">
                {String(status.error.message || status.error)}
              </div>
            </div>
          </div>
        </Alert>
      )}

      <Card>
        <CardHeader>
          <div className="flex items-start justify-between flex-wrap gap-3">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Activity className="h-4 w-4 text-purple-400" />
                Recent Registered Records
              </CardTitle>
              <CardDescription>
                Each record stores cryptographic hashes only. Raw AI reports
                remain OFF-CHAIN.
              </CardDescription>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              <Badge variant="evidence" className="font-mono text-[10px]">
                OFF-CHAIN AI EVIDENCE
              </Badge>
              <span className="text-slate-600 text-xs">+</span>
              <Badge variant="blockchain" className="font-mono text-[10px]">
                ON-CHAIN HASH PROOF
              </Badge>
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-800 bg-slate-900/60 text-[11px] uppercase tracking-wider text-slate-400 text-left">
                  <th className="px-5 py-3 font-medium">Claim</th>
                  <th className="px-5 py-3 font-medium">Record ID</th>
                  <th className="px-5 py-3 font-medium">Model</th>
                  <th className="px-5 py-3 font-medium">Timestamp</th>
                  <th className="px-5 py-3 font-medium">Transaction / Block</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {records.isLoading &&
                  Array.from({ length: 5 }).map((_, i) => (
                    <tr
                      key={i}
                      className="border-b border-slate-800/60 last:border-none"
                    >
                      {Array.from({ length: 6 }).map((__, j) => (
                        <td key={j} className="px-5 py-4">
                          <Skeleton className="h-5 w-full" />
                        </td>
                      ))}
                    </tr>
                  ))}
                {!records.isLoading && list.length === 0 && (
                  <tr>
                    <td
                      colSpan={6}
                      className="px-5 py-16 text-center text-sm text-slate-500"
                    >
                      No records found in the blockchain registry yet.
                      <div className="mt-3">
                        <Link href="/claims/new">
                          <Button size="sm" variant="outline">
                            Register a new assessment
                          </Button>
                        </Link>
                      </div>
                    </td>
                  </tr>
                )}
                {list.map((r, idx) => {
                  const claimId =
                    pickField<string>(r, ["claim_id"]) ||
                    (r as { vehicle_id?: string }).vehicle_id ||
                    "—";
                  const recordId =
                    pickField<string>(r, ["record_id"]) || "";
                  const modelVersion =
                    pickField<string>(r, [
                      "model_version",
                      "vision.model",
                    ]) || "—";
                  const ts = pickField<number | string>(r, [
                    "created_at",
                    "timestamp",
                    "blockchain.timestamp",
                  ]);
                  const bc = r.blockchain as
                    | Record<string, unknown>
                    | undefined;
                  const tx =
                    pickField<string>(r, ["transaction_hash", "blockchain.transaction"]) ||
                    (bc?.transaction as string | undefined) ||
                    "";
                  const block =
                    pickField<number>(r, ["block_number", "blockchain.block_number"]) ||
                    (bc?.block_number as number | undefined) ||
                    null;
                  const networkName =
                    pickField<string>(r, ["network", "blockchain.network"]) ||
                    (bc?.network as string | undefined) ||
                    "";
                  const isRealSepolia = isSepolia(networkName);
                  return (
                    <tr
                      key={recordId || String(idx)}
                      className="border-b border-slate-800/60 last:border-none hover:bg-slate-900/40 transition-colors"
                    >
                      <td className="px-5 py-4">
                        <span className="font-mono text-slate-100">
                          {claimId}
                        </span>
                      </td>
                      <td className="px-5 py-4 max-w-[220px]">
                        {recordId ? (
                          <Copyable value={recordId} start={8} end={6} />
                        ) : (
                          <span className="text-xs text-slate-500">—</span>
                        )}
                      </td>
                      <td className="px-5 py-4">
                        <span className="text-xs font-mono text-slate-300">
                          {modelVersion}
                        </span>
                      </td>
                      <td className="px-5 py-4 text-xs text-slate-400 font-mono">
                        {ts ? (typeof ts === "string" ? new Date(ts).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" }) : formatDate(ts as number)) : "—"}
                      </td>
                      <td className="px-5 py-4 max-w-[260px]">
                        {tx ? (
                          <div className="space-y-0.5">
                            <Copyable
                              value={tx.startsWith("0x") ? tx : `0x${tx}`}
                              start={6}
                              end={6}
                              className="text-xs"
                            />
                            <div className="text-[11px] text-slate-500 font-mono flex items-center gap-2">
                              Block {block ?? "—"}
                              {isRealSepolia ? (
                                <a
                                  href={`${ETHERSCAN_BASE_URL}/tx/${tx.startsWith("0x") ? tx : `0x${tx}`}`}
                                  target="_blank"
                                  rel="noreferrer noopener"
                                  className="inline-flex items-center gap-1 text-purple-300 hover:text-purple-200"
                                >
                                  <ExternalLink className="h-3 w-3" />
                                  Etherscan
                                </a>
                              ) : (
                                <span className="text-teal-400/80">
                                  Audit Ledger
                                </span>
                              )}
                            </div>
                          </div>
                        ) : (
                          <span className="text-xs text-slate-500">—</span>
                        )}
                      </td>
                      <td className="px-5 py-4">
                        <Badge
                          variant={
                            tx || recordId ? "blockchain" : "default"
                          }
                          className="font-mono text-[10px]"
                        >
                          {tx || recordId ? (
                            <>
                              <CheckCircle2 className="h-3 w-3 mr-1" />
                              REGISTERED
                            </>
                          ) : (
                            "PENDING"
                          )}
                        </Badge>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </CardContent>
        <div className="border-t border-slate-800 px-5 py-3 flex items-center justify-between text-[11px] text-slate-500">
          <div>
            TruthChain AssessmentRegistry · Cryptographic proof layer
          </div>
          <Separator orientation="vertical" className="h-3 w-px" />
          <div className="font-mono">
            {status.data?.rpc_url
              ? String(status.data.rpc_url).replace(
                  /(http[s]?:\/\/[^/]+\/).+/,
                  "$1…",
                )
              : "RPC: N/A"}
          </div>
        </div>
      </Card>
    </div>
  );
}
