import type { Metadata } from "next";
import "./globals.css";
import { QueryProvider } from "./providers";
import { AppSidebar } from "@/components/layout/AppSidebar";
import { AppHeader } from "@/components/layout/AppHeader";
import { MobileNav } from "@/components/layout/MobileNav";

export const metadata: Metadata = {
  title: "TruthChain 2.0 · AI Consensus & Blockchain Fraud Verification",
  description:
    "TruthChain 8-Agent AI Consensus Engine with Sepolia AssessmentRegistry for motor insurance fraud detection and cryptographic evidence verification.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body className="grid-bg min-h-screen antialiased" suppressHydrationWarning>
        <QueryProvider>
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
        </QueryProvider>
      </body>
    </html>
  );
}
