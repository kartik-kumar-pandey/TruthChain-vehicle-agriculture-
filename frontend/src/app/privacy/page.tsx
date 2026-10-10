import Link from "next/link";
import { ArrowLeft, Shield } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function PrivacyPolicyPage() {
  return (
    <div className="max-w-4xl mx-auto py-8 space-y-6 text-slate-200">
      <div className="flex items-center justify-between border-b border-slate-800 pb-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
            <Shield className="h-6 w-6 text-sky-400" />
            Privacy Policy
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Last Updated: October 10, 2026
          </p>
        </div>
        <Link href="/">
          <Button variant="outline" size="sm">
            <ArrowLeft className="h-4 w-4 mr-2" /> Back to Dashboard
          </Button>
        </Link>
      </div>

      <div className="space-y-6 text-sm leading-relaxed text-slate-300">
        <section className="space-y-2">
          <h2 className="text-base font-semibold text-slate-100">1. Information Collection</h2>
          <p>
            TruthChain collects insurance claim narrative text, telemetry sensor readings, and geotagged field imagery strictly for automated claim verification and consensus analysis.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-base font-semibold text-slate-100">2. Processing & Storage</h2>
          <p>
            Submitted claim imagery and narrative data are processed in real-time by isolated inference services. Only cryptographic hashes (SHA-256) of verified evidence are recorded on the Sepolia AssessmentRegistry blockchain. Raw imagery and private metadata remain stored securely off-chain.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-base font-semibold text-slate-100">3. Data Security</h2>
          <p>
            We implement strict encryption in transit (TLS 1.3) and at rest. No personal identifying information is written to public smart contracts.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-base font-semibold text-slate-100">4. Contact</h2>
          <p>
            For privacy inquiries or data erasure requests, please contact privacy@truthchain.io.
          </p>
        </section>
      </div>
    </div>
  );
}
