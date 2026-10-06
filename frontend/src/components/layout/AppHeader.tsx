"use client";

import { useHealth } from "@/hooks/useTruthChain";
import { Badge } from "@/components/ui/badge";
import { Activity, AlertTriangle, CheckCircle2 } from "lucide-react";
import Link from "next/link";

export function AppHeader() {
  const health = useHealth();

  const modules = health.data?.modules;
  const totalModules = modules ? Object.keys(modules).length : 0;
  const readyModules = modules
    ? Object.values(modules).filter(Boolean).length
    : 0;

  return (
    <header className="sticky top-0 z-20 h-16 border-b border-slate-800 bg-slate-950/70 backdrop-blur-md">
      <div className="h-full px-4 md:px-6 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3 min-w-0">
          <div className="hidden md:flex items-center gap-2 text-xs text-slate-500 font-mono">
            <Activity className="h-3.5 w-3.5 text-cyan-400" />
            TRUTHCHAIN · MULTIMODAL FRAUD ASSESSMENT PLATFORM
          </div>
        </div>
        <div className="flex items-center gap-3 md:gap-4">
          {health.data && (
            <div className="hidden md:flex items-center gap-2 text-xs text-slate-400">
              {readyModules === totalModules ? (
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
              ) : (
                <AlertTriangle className="h-3.5 w-3.5 text-amber-400" />
              )}
              {readyModules}/{totalModules} modules
            </div>
          )}
          <Badge
            variant="blockchain"
            className="hidden sm:inline-flex font-mono text-[10px]"
          >
            Sepolia · AssessmentRegistry
          </Badge>
          <Link
            href="/system"
            className="text-xs text-slate-400 hover:text-slate-200 underline-offset-4 hover:underline hidden md:inline"
          >
            Diagnostics →
          </Link>
        </div>
      </div>
    </header>
  );
}
