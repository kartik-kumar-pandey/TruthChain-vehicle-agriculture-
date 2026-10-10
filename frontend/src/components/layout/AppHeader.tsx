"use client";

import { useHealth } from "@/hooks/useTruthChain";
import { Badge } from "@/components/ui/badge";
import { Activity, AlertTriangle, CheckCircle2, LogOut, User, Sun, Moon } from "lucide-react";
import Link from "next/link";
import { GoogleLogin } from "@react-oauth/google";
import { useAuth } from "@/context/AuthContext";
import { useState } from "react";

export function AppHeader() {
  const health = useHealth();
  const { user, login, logout } = useAuth();
  const [isLightMode, setIsLightMode] = useState(false);

  const toggleTheme = () => {
    const isLight = document.documentElement.classList.contains("light");
    if (!isLight) {
      document.documentElement.classList.add("light");
      document.documentElement.classList.remove("dark");
      setIsLightMode(true);
    } else {
      document.documentElement.classList.add("dark");
      document.documentElement.classList.remove("light");
      setIsLightMode(false);
    }
  };

  const modules = health.data?.modules;
  const totalModules = modules ? Object.keys(modules).length : 0;
  const readyModules = modules
    ? Object.values(modules).filter(Boolean).length
    : 0;

  return (
    <header className="sticky top-0 z-20 h-16 border-b border-slate-200 dark:border-slate-800/80 bg-white/80 dark:bg-slate-950/70 backdrop-blur-md transition-colors duration-300">
      <div className="h-full px-4 md:px-6 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3 min-w-0">
          <div className="hidden md:flex items-center gap-2 text-xs text-slate-500 font-mono">
            <Activity className="h-3.5 w-3.5 text-cyan-500 dark:text-cyan-400" />
            TRUTHCHAIN · MULTIMODAL FRAUD ASSESSMENT PLATFORM
          </div>
        </div>
        <div className="flex items-center gap-3 md:gap-4">
          <button
            onClick={toggleTheme}
            className="p-1.5 rounded-full border border-slate-200 dark:border-slate-800 bg-slate-100 dark:bg-slate-900 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-800 transition-colors"
            title="Toggle Light/Dark Theme"
          >
            {isLightMode ? <Moon className="h-3.5 w-3.5 text-slate-700" /> : <Sun className="h-3.5 w-3.5 text-amber-400" />}
          </button>
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

          {user ? (
            <div className="flex items-center gap-2 border border-slate-200 dark:border-slate-700/80 rounded-full pl-1.5 pr-3 py-1 bg-white/90 dark:bg-slate-900/90 shadow-md">
              {user.picture ? (
                <img
                  src={user.picture}
                  alt={user.name}
                  referrerPolicy="no-referrer"
                  className="h-6 w-6 rounded-full object-cover border border-cyan-500/50 shadow-sm"
                  onError={(e) => {
                    // Hide image on error and show fallback icon
                    e.currentTarget.style.display = "none";
                  }}
                />
              ) : (
                <div className="h-6 w-6 rounded-full bg-cyan-950 border border-cyan-800 flex items-center justify-center">
                  <User className="h-3.5 w-3.5 text-cyan-400" />
                </div>
              )}
              <span className="text-xs font-semibold text-slate-700 dark:text-slate-200 hidden sm:inline">{user.name}</span>
              <button
                onClick={logout}
                title="Sign Out"
                className="text-slate-400 hover:text-red-500 ml-1 transition-colors"
              >
                <LogOut className="h-3.5 w-3.5" />
              </button>
            </div>
          ) : (
            <div className="scale-90">
              <GoogleLogin
                onSuccess={(response) => {
                  if (response.credential) login(response.credential);
                }}
                onError={() => console.error("Google Auth Failed")}
                theme="filled_black"
                shape="pill"
                size="small"
              />
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
