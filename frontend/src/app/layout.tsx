import type { Metadata } from "next";
import "./globals.css";
import { QueryProvider } from "./providers";
import { AppShell } from "@/components/layout/AppShell";

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
    <html lang="en" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `document.documentElement.classList.add('dark');`,
          }}
        />
      </head>
      <body className="grid-bg min-h-screen antialiased" suppressHydrationWarning>
        <QueryProvider>
          <AppShell>{children}</AppShell>
        </QueryProvider>
      </body>
    </html>
  );
}
