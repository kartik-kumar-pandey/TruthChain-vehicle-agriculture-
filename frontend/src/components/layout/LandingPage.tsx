"use client";

import { useState } from "react";
import { GoogleLogin } from "@react-oauth/google";
import { useAuth } from "@/context/AuthContext";
import { motion } from "framer-motion";
import {
  ShieldCheck,
  Cpu,
  Database,
  Lock,
  Sparkles,
  ArrowRight,
  Car,
  Sprout,
  Sun,
  Moon,
  Camera,
  Activity,
  CheckCircle2,
  FileText,
  Radio,
  Globe2,
} from "lucide-react";

export function LandingPage() {
  const { login } = useAuth();
  const [isLightMode, setIsLightMode] = useState(false);

  const toggleTheme = () => {
    setIsLightMode(!isLightMode);
    if (!isLightMode) {
      document.documentElement.classList.add("light");
      document.documentElement.classList.remove("dark");
    } else {
      document.documentElement.classList.add("dark");
      document.documentElement.classList.remove("light");
    }
  };

  return (
    <div className={`min-h-screen ${isLightMode ? "bg-slate-50 text-slate-900" : "bg-slate-950 text-slate-100"} transition-colors duration-300 flex flex-col justify-between selection:bg-sky-500 selection:text-white relative grid-bg overflow-hidden`}>
      {/* Background Ambient Glows */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[700px] h-[350px] bg-sky-500/10 rounded-full blur-[160px] pointer-events-none" />
      <div className="absolute top-1/2 right-0 w-[500px] h-[400px] bg-emerald-500/10 rounded-full blur-[160px] pointer-events-none" />

      {/* Header Bar */}
      <motion.header
        initial={{ y: -20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.5 }}
        className={`border-b ${isLightMode ? "border-slate-200 bg-white/80" : "border-slate-800/80 bg-slate-950/70"} backdrop-blur-xl sticky top-0 z-50`}
      >
        <div className="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-sky-500 via-teal-500 to-blue-600 flex items-center justify-center shadow-lg shadow-sky-500/20">
              <ShieldCheck className="h-6 w-6 text-white stroke-[2.5]" />
            </div>
            <div>
              <span className={`font-bold text-xl tracking-tight ${isLightMode ? "text-slate-900" : "text-white"}`}>
                TruthChain
              </span>
              <span className="ml-2.5 px-2.5 py-0.5 text-[11px] font-mono rounded-full bg-sky-500/10 text-sky-600 dark:text-sky-400 border border-sky-500/20">
                v2.0 Production
              </span>
            </div>
          </div>

          <div className="flex items-center gap-4">
            {/* Theme Toggle Button */}
            <button
              onClick={toggleTheme}
              className={`p-2 rounded-full border transition-all ${isLightMode ? "border-slate-300 bg-slate-100 text-slate-700 hover:bg-slate-200" : "border-slate-800 bg-slate-900 text-slate-300 hover:bg-slate-800"}`}
              title="Toggle Light/Dark Theme"
            >
              {isLightMode ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4 text-amber-400" />}
            </button>

            <div className="scale-95">
              <GoogleLogin
                onSuccess={(res) => res.credential && login(res.credential)}
                onError={() => console.error("Login failed")}
                theme={isLightMode ? "outline" : "filled_blue"}
                shape="pill"
                text="signin_with"
                size="large"
              />
            </div>
          </div>
        </div>
      </motion.header>

      {/* Main Content */}
      <main className="flex-1 max-w-7xl mx-auto px-6 py-12 space-y-20 relative z-10">
        {/* Hero Section */}
        <div className="text-center max-w-3xl mx-auto space-y-6 pt-6">
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.5 }}
            className={`inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-mono font-medium ${isLightMode ? "bg-sky-50 text-sky-700 border border-sky-200" : "bg-sky-950/80 text-sky-300 border border-sky-800/60"}`}
          >
            <Sparkles className="h-3.5 w-3.5" />
            Dual-Domain AI Consensus & Sepolia On-Chain Proof
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.1 }}
            className={`text-4xl sm:text-6xl font-extrabold tracking-tight leading-tight ${isLightMode ? "text-slate-900" : "text-white"}`}
          >
            Next-Gen Fraud Assessment for{" "}
            <span className="bg-gradient-to-r from-sky-500 via-teal-500 to-indigo-600 bg-clip-text text-transparent">
              Insurance Claims
            </span>
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
            className={`text-lg ${isLightMode ? "text-slate-600" : "text-slate-400"} leading-relaxed`}
          >
            TruthChain provides structured multi-agent AI verification for both <strong>Motor Vehicle Damage</strong> and <strong>Agricultural Crop Loss</strong> claims.
          </motion.p>
        </div>

        {/* DOMAIN EXPLANATION SECTION (Structured & Separate) */}
        <div className="space-y-8">
          <div className="text-center space-y-2">
            <h2 className={`text-2xl font-bold ${isLightMode ? "text-slate-900" : "text-white"}`}>
              Supported Insurance Domains
            </h2>
            <p className={`text-sm ${isLightMode ? "text-slate-500" : "text-slate-400"}`}>
              Explore our specialized AI analysis pipelines tailored to each domain
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-8">
            {/* DOMAIN 1: MOTOR INSURANCE */}
            <motion.div
              whileHover={{ y: -6 }}
              transition={{ type: "spring", stiffness: 300 }}
              className={`p-8 rounded-3xl border ${isLightMode ? "bg-white border-slate-200/90 shadow-xl shadow-slate-200/50" : "glass-card border-slate-800"} space-y-6 relative overflow-hidden group`}
            >
              <div className="flex items-center justify-between">
                <div className="h-12 w-12 rounded-2xl bg-sky-500/10 text-sky-500 border border-sky-500/20 flex items-center justify-center">
                  <Car className="h-6 w-6" />
                </div>
                <span className="text-xs font-mono font-semibold px-3 py-1 rounded-full bg-sky-500/10 text-sky-600 dark:text-sky-400">
                  8-Agent Pipeline
                </span>
              </div>

              <div>
                <h3 className={`text-2xl font-bold ${isLightMode ? "text-slate-900" : "text-white"} mb-2`}>
                  🚗 Motor Vehicle Insurance
                </h3>
                <p className={`text-sm ${isLightMode ? "text-slate-600" : "text-slate-400"} leading-relaxed`}>
                  Automated physical collision damage classification combined with high-frequency vehicle telemetry analysis.
                </p>
              </div>

              <div className="space-y-3 pt-2">
                <div className={`flex items-start gap-3 text-sm ${isLightMode ? "text-slate-700" : "text-slate-300"}`}>
                  <CheckCircle2 className="h-4 w-4 text-sky-500 shrink-0 mt-0.5" />
                  <span><strong>ResNet-50 Vision CNN:</strong> Detects dent, scratch, glass shatter, crack, lamp broken, and tire flat.</span>
                </div>
                <div className={`flex items-start gap-3 text-sm ${isLightMode ? "text-slate-700" : "text-slate-300"}`}>
                  <CheckCircle2 className="h-4 w-4 text-sky-500 shrink-0 mt-0.5" />
                  <span><strong>XGBoost Sensor Telemetry:</strong> Evaluates acceleration vectors, impact speed, and GPS coordinates.</span>
                </div>
                <div className={`flex items-start gap-3 text-sm ${isLightMode ? "text-slate-700" : "text-slate-300"}`}>
                  <CheckCircle2 className="h-4 w-4 text-sky-500 shrink-0 mt-0.5" />
                  <span><strong>Narrative Consistency:</strong> Cross-checks claimant statement against physical sensor metrics.</span>
                </div>
              </div>
            </motion.div>

            {/* DOMAIN 2: AGRICULTURE INSURANCE */}
            <motion.div
              whileHover={{ y: -6 }}
              transition={{ type: "spring", stiffness: 300 }}
              className={`p-8 rounded-3xl border ${isLightMode ? "bg-white border-slate-200/90 shadow-xl shadow-slate-200/50" : "glass-card border-slate-800"} space-y-6 relative overflow-hidden group`}
            >
              <div className="flex items-center justify-between">
                <div className="h-12 w-12 rounded-2xl bg-emerald-500/10 text-emerald-500 border border-emerald-500/20 flex items-center justify-center">
                  <Sprout className="h-6 w-6" />
                </div>
                <span className="text-xs font-mono font-semibold px-3 py-1 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
                  9-Agent Pipeline
                </span>
              </div>

              <div>
                <h3 className={`text-2xl font-bold ${isLightMode ? "text-slate-900" : "text-white"} mb-2`}>
                  🌾 Agriculture Crop Loss
                </h3>
                <p className={`text-sm ${isLightMode ? "text-slate-600" : "text-slate-400"} leading-relaxed`}>
                  Field polygon crop verification integrating multi-spectral satellite remote sensing and weather analytics.
                </p>
              </div>

              <div className="space-y-3 pt-2">
                <div className={`flex items-start gap-3 text-sm ${isLightMode ? "text-slate-700" : "text-slate-300"}`}>
                  <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0 mt-0.5" />
                  <span><strong>CDSE Sentinel-2 STAC:</strong> Extracts 77 multi-band spectral features and NDVI health indices.</span>
                </div>
                <div className={`flex items-start gap-3 text-sm ${isLightMode ? "text-slate-700" : "text-slate-300"}`}>
                  <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0 mt-0.5" />
                  <span><strong>Geotagged Field Mapping:</strong> Verifies boundary polygons against actual crop classification.</span>
                </div>
                <div className={`flex items-start gap-3 text-sm ${isLightMode ? "text-slate-700" : "text-slate-300"}`}>
                  <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0 mt-0.5" />
                  <span><strong>Meteorological Cross-Validation:</strong> Verifies drought, flood, or hail events against historical weather.</span>
                </div>
              </div>
            </motion.div>
          </div>
        </div>

        {/* CORE PLATFORM FEATURES */}
        <div className="grid md:grid-cols-3 gap-6 pt-6">
          <div className={`p-6 rounded-2xl border ${isLightMode ? "bg-white border-slate-200" : "glass-card border-slate-800"}`}>
            <Cpu className="h-6 w-6 text-sky-500 mb-3" />
            <h4 className={`font-bold text-base ${isLightMode ? "text-slate-900" : "text-white"} mb-1`}>LangGraph Consensus</h4>
            <p className={`text-xs ${isLightMode ? "text-slate-600" : "text-slate-400"}`}>Independent agents generate weighted risk signals before consensus voting.</p>
          </div>

          <div className={`p-6 rounded-2xl border ${isLightMode ? "bg-white border-slate-200" : "glass-card border-slate-800"}`}>
            <Lock className="h-6 w-6 text-purple-500 mb-3" />
            <h4 className={`font-bold text-base ${isLightMode ? "text-slate-900" : "text-white"} mb-1`}>Sepolia Blockchain</h4>
            <p className={`text-xs ${isLightMode ? "text-slate-600" : "text-slate-400"}`}>Cryptographic commitment hashes stored in Ethereum smart contracts.</p>
          </div>

          <div className={`p-6 rounded-2xl border ${isLightMode ? "bg-white border-slate-200" : "glass-card border-slate-800"}`}>
            <Database className="h-6 w-6 text-teal-500 mb-3" />
            <h4 className={`font-bold text-base ${isLightMode ? "text-slate-900" : "text-white"} mb-1`}>Neon Serverless DB</h4>
            <p className={`text-xs ${isLightMode ? "text-slate-600" : "text-slate-400"}`}>Serverless PostgreSQL with instant autoscaling and session persistence.</p>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className={`border-t ${isLightMode ? "border-slate-200 bg-white" : "border-slate-900 bg-slate-950"} py-6`}>
        <div className="max-w-7xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between text-xs text-slate-500 font-mono gap-3">
          <div>TruthChain 2.0 · Motor & Agriculture Fraud Platform</div>
          <div>Google OAuth + Neon Serverless Auth</div>
        </div>
      </footer>
    </div>
  );
}
