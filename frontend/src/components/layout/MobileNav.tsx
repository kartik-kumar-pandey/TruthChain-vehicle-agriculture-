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
  Menu,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { useHealth } from "@/hooks/useTruthChain";

const NAV = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/claims/new", label: "Create Claim", icon: FilePlus2 },
  { href: "/claims", label: "Claims", icon: Files },
  { href: "/evidence", label: "Evidence Inspector", icon: ShieldCheck },
  { href: "/blockchain", label: "Blockchain", icon: Blocks },
  { href: "/system", label: "System", icon: Cpu },
];

export function MobileNav() {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();
  const health = useHealth();
  const status = health.data?.status;
  const allReady = health.data?.modules
    ? Object.values(health.data.modules).every(Boolean)
    : false;

  return (
    <div className="lg:hidden">
      <div className="h-16 px-4 border-b border-slate-800 bg-slate-950/60 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="h-8 w-8 rounded-md bg-gradient-to-br from-cyan-500 via-indigo-500 to-purple-600 flex items-center justify-center">
            <Shield className="h-4 w-4 text-white" />
          </div>
          <div className="leading-tight">
            <div className="text-sm font-semibold text-white">TruthChain</div>
            <div className="text-[10px] text-slate-400 font-mono">v2.0</div>
          </div>
        </div>
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="h-9 w-9 rounded-md border border-slate-700 bg-slate-900 text-slate-300 inline-flex items-center justify-center"
          aria-label="Toggle navigation"
        >
          {open ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
        </button>
      </div>
      {open && (
        <div className="border-b border-slate-800 bg-slate-950/80 backdrop-blur-sm px-3 py-3 space-y-0.5">
          <div className="px-3 py-2">
            <Badge
              variant={
                status === "healthy" || allReady ? "success" : "warning"
              }
            >
              {health.isLoading
                ? "Connecting…"
                : status === "healthy"
                  ? "AI Service Online"
                  : "AI Service"}
            </Badge>
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
                onClick={() => setOpen(false)}
                className={cn(
                  "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium",
                  active
                    ? "bg-cyan-500/10 text-cyan-300 ring-1 ring-inset ring-cyan-500/20"
                    : "text-slate-300 hover:bg-slate-800/60",
                )}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
