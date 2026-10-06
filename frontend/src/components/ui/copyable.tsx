"use client";

import * as React from "react";
import { cn, copyToClipboard, truncateHash } from "@/lib/utils";
import { Check, Copy } from "lucide-react";

interface CopyableProps {
  value: string;
  truncate?: boolean;
  start?: number;
  end?: number;
  className?: string;
  mono?: boolean;
  label?: string;
}

export function Copyable({
  value,
  truncate = true,
  start = 10,
  end = 8,
  className,
  mono = true,
  label,
}: CopyableProps) {
  const [copied, setCopied] = React.useState(false);

  const onCopy = async () => {
    const ok = await copyToClipboard(value);
    if (ok) {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    }
  };

  const display =
    truncate && value ? truncateHash(value, start, end) : value;

  return (
    <div className="flex items-center gap-2">
      {label && (
        <span className="text-xs text-slate-400 mr-1">{label}</span>
      )}
      <span
        className={cn(
          "text-sm",
          mono ? "font-mono" : "",
          "text-slate-200",
          className,
        )}
        title={value}
      >
        {display}
      </span>
      <button
        type="button"
        onClick={onCopy}
        className="inline-flex h-6 w-6 items-center justify-center rounded-md border border-slate-700 bg-slate-800/50 text-slate-400 hover:bg-slate-700 hover:text-slate-200 transition-colors shrink-0"
        title="Copy to clipboard"
      >
        {copied ? (
          <Check className="h-3.5 w-3.5 text-emerald-400" />
        ) : (
          <Copy className="h-3.5 w-3.5" />
        )}
      </button>
    </div>
  );
}
