"use client";

import { useAuth } from "@/context/AuthContext";
import { AppSidebar } from "@/components/layout/AppSidebar";
import { AppHeader } from "@/components/layout/AppHeader";
import { MobileNav } from "@/components/layout/MobileNav";
import { LandingPage } from "./LandingPage";

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen bg-white dark:bg-slate-950 flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 rounded-full border-2 border-cyan-500 border-t-transparent animate-spin" />
          <p className="text-xs text-slate-400 font-mono">Authenticating with TruthChain...</p>
        </div>
      </div>
    );
  }

  if (!user) {
    return <LandingPage />;
  }

  return (
    <div className="min-h-screen flex lg:h-screen lg:overflow-hidden">
      <AppSidebar />
      <div className="flex-1 min-w-0 flex flex-col lg:h-screen">
        <MobileNav />
        <AppHeader />
        <main className="flex-1 min-w-0 overflow-y-auto">
          <div className="mx-auto max-w-7xl px-4 md:px-6 py-6 md:py-8">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
