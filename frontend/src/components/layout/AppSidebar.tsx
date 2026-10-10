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
    <aside className="hidden lg:flex w-64 shrink-0 flex-col border-r border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950/80 backdrop-blur-xl transition-colors duration-300">
      <div className="h-16 px-5 border-b border-slate-200 dark:border-slate-800 flex items-center gap-3">
        <div className="h-9 w-9 rounded-lg bg-gradient-to-br from-cyan-500 via-indigo-500 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-950/20">
          <Shield className="h-5 w-5 text-white" strokeWidth={2.2} />
        </div>
        <div className="leading-tight">
          <div className="text-sm font-bold tracking-tight text-slate-900 dark:text-white">
            TruthChain
          </div>
          <div className="text-[11px] text-slate-500 dark:text-slate-400 font-mono">
            v2.0 · Production
          </div>
        </div>
      </div>

      <div className="px-4 py-3">
        <ServiceBadge />
      </div>

      <nav className="px-3 py-2 flex-1 space-y-1">
        <div className="px-3 py-2 text-[10px] font-bold tracking-widest text-slate-400 dark:text-slate-500 uppercase">
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
                "group flex items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-150",
                active
                  ? "bg-cyan-50 dark:bg-cyan-500/10 text-cyan-600 dark:text-cyan-300 font-semibold shadow-xs"
                  : "text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800/60 hover:text-slate-900 dark:hover:text-slate-200",
              )}
            >
              <Icon
                className={cn(
                  "h-4 w-4 shrink-0 transition-colors",
                  active
                    ? "text-cyan-600 dark:text-cyan-400"
                    : "text-slate-400 dark:text-slate-500 group-hover:text-slate-700 dark:group-hover:text-slate-300",
                )}
              />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="p-4 border-t border-slate-200 dark:border-slate-800 space-y-3">
        <div className="rounded-xl border border-purple-200 dark:border-purple-900/40 bg-purple-50 dark:bg-purple-950/30 p-3">
          <div className="text-[11px] font-bold tracking-wider text-purple-700 dark:text-purple-300 uppercase mb-1">
            On-Chain Immutable Proof
          </div>
          <div className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed font-mono">
            AssessmentRegistry · Sepolia
          </div>
        </div>
        <div className="text-[10px] font-mono text-slate-400 dark:text-slate-500 leading-relaxed flex items-center justify-between">
          <span>TruthChain Enterprise</span>
          <div className="flex gap-2">
            <Link href="/privacy" className="hover:underline">Privacy</Link>
            <span>·</span>
            <Link href="/terms" className="hover:underline">Terms</Link>
          </div>
        </div>
      </div>
    </aside>
  );
}
