"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  FilePlus2,
  Files,
  ShieldCheck,
  Blocks,
  Cpu,
  Shield,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { useHealth } from "@/hooks/useTruthChain";

const NAV = [
  {
    href: "/",
    label: "Dashboard",
    icon: LayoutDashboard,
  },
  {
    href: "/claims/new",
    label: "Create Claim",
    icon: FilePlus2,
  },
  {
    href: "/claims",
    label: "Claims",
    icon: Files,
  },
  {
    href: "/evidence",
    label: "Evidence Inspector",
    icon: ShieldCheck,
  },
  {
    href: "/blockchain",
    label: "Blockchain",
    icon: Blocks,
  },
  {
    href: "/system",
    label: "System",
    icon: Cpu,
  },
];

function ServiceBadge() {
  const health = useHealth();
  const status = health.data?.status;
  const allReady = health.data?.modules
    ? Object.values(health.data.modules).every(Boolean)
    : false;

  return (
    <Badge
      variant={
        status === "healthy" || allReady ? "success" : "warning"
      }
      className="border"
    >
      <span
        className={cn(
          "h-1.5 w-1.5 rounded-full",
          status === "healthy" || allReady
            ? "bg-emerald-400"
            : "bg-amber-400",
          health.isFetching && !health.data
            ? "bg-slate-500"
            : "",
        )}
      />
      {health.isLoading
        ? "Connecting…"
        : status === "healthy"
          ? "AI Service Online"
          : status === "degraded"
            ? "AI Service Degraded"
            : health.error
              ? "AI Service Unreachable"
              : status || "AI Service"}
    </Badge>
  );
}

export function AppSidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden lg:flex w-64 shrink-0 flex-col border-r border-slate-800 bg-slate-950/60">
      <div className="h-16 px-5 border-b border-slate-800 flex items-center gap-3">
        <div className="h-9 w-9 rounded-lg bg-gradient-to-br from-cyan-500 via-indigo-500 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-950/40">
          <Shield className="h-5 w-5 text-white" strokeWidth={2.2} />
        </div>
        <div className="leading-tight">
          <div className="text-sm font-semibold tracking-tight text-white">
            TruthChain
          </div>
          <div className="text-[11px] text-slate-400 font-mono">
            v2.0 · Production
          </div>
        </div>
      </div>

      <div className="px-4 py-3">
        <ServiceBadge />
      </div>

      <nav className="px-3 py-2 flex-1 space-y-0.5">
        <div className="px-3 py-2 text-[10px] font-semibold tracking-widest text-slate-500 uppercase">
          Operations
        </div>
        {NAV.map((item) => {
          const Icon = item.icon;
          const active =
            item.href === "/"
              ? pathname === "/"
              : pathname === item.href ||
                pathname.startsWith(item.href + "/");
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "group flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                active
                  ? "bg-cyan-500/10 text-cyan-300 ring-1 ring-inset ring-cyan-500/20"
                  : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-200",
              )}
            >
              <Icon
                className={cn(
                  "h-4 w-4 shrink-0",
                  active
                    ? "text-cyan-400"
                    : "text-slate-500 group-hover:text-slate-300",
                )}
              />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="p-4 border-t border-slate-800 space-y-3">
        <div className="rounded-lg border border-purple-900/40 bg-purple-950/30 p-3">
          <div className="text-[11px] font-semibold tracking-wider text-purple-300 uppercase mb-1.5">
            On-Chain Immutable Proof
          </div>
          <div className="text-xs text-slate-400 leading-relaxed">
            AssessmentRegistry · Sepolia
          </div>
        </div>
        <div className="text-[11px] text-slate-500 leading-relaxed">
          OFF-CHAIN AI EVIDENCE + ON-CHAIN CRYPTOGRAPHIC PROOF
        </div>
      </div>
    </aside>
  );
}
