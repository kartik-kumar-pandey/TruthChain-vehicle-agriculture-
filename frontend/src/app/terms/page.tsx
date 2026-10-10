import Link from "next/link";
import { ArrowLeft, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function TermsPage() {
  return (
    <div className="max-w-4xl mx-auto py-8 space-y-6 text-slate-200">
      <div className="flex items-center justify-between border-b border-slate-800 pb-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
            <FileText className="h-6 w-6 text-sky-400" />
            Terms and Conditions
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
          <h2 className="text-base font-semibold text-slate-100">1. Acceptance of Terms</h2>
          <p>
            By accessing or using the TruthChain verification platform, you agree to be bound by these Terms and Conditions and all applicable laws and regulations.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-base font-semibold text-slate-100">2. Automated Decision Screening</h2>
          <p>
            TruthChain consensus scores and agent outputs provide decision support for insurance claim verification. Final claim approvals or denials remain subject to underwriter review and policy terms.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-base font-semibold text-slate-100">3. Blockchain Immutability</h2>
          <p>
            Cryptographic evidence records written to the Sepolia AssessmentRegistry smart contract are permanent and immutable by design.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-base font-semibold text-slate-100">4. Limitation of Liability</h2>
          <p>
            TruthChain is provided as-is without warranties of any kind. Underwriters and claim handlers must independently verify high-risk flagged claims.
          </p>
        </section>
      </div>
    </div>
  );
}
