import * as React from "react";
import { cn } from "@/lib/utils";

export function Separator({
  className,
  orientation = "horizontal",
}: {
  className?: string;
  orientation?: "horizontal" | "vertical";
}) {
  return (
    <div
      role="separator"
      className={cn(
        "bg-slate-800 shrink-0",
        orientation === "horizontal" ? "h-px w-full" : "h-full w-px",
        className,
      )}
    />
  );
}

export function Alert({
  variant = "default",
  className,
  children,
}: {
  variant?: "default" | "success" | "warning" | "danger" | "info";
  className?: string;
  children: React.ReactNode;
}) {
  const styles = {
    default: "border-slate-700 bg-slate-900/60 text-slate-200",
    success: "border-emerald-800 bg-emerald-950/40 text-emerald-200",
    warning: "border-amber-800 bg-amber-950/40 text-amber-200",
    danger: "border-red-800 bg-red-950/40 text-red-200",
    info: "border-cyan-800 bg-cyan-950/40 text-cyan-200",
  };
  return (
    <div
      role="alert"
      className={cn(
        "rounded-lg border px-4 py-3 text-sm",
        styles[variant],
        className,
      )}
    >
      {children}
    </div>
  );
}

export function Skeleton({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "shimmer rounded-md bg-slate-800/60 text-transparent select-none",
        className,
      )}
      {...props}
    >
      &nbsp;
    </div>
  );
}

export function SectionHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: React.ReactNode;
}) {
  return (
    <div className="flex items-end justify-between gap-4 mb-6">
      <div>
        {eyebrow && (
          <div className="text-xs font-medium tracking-widest text-cyan-400 uppercase mb-2">
            {eyebrow}
          </div>
        )}
        <h1 className="text-2xl font-semibold text-slate-50 tracking-tight">
          {title}
        </h1>
        {description && (
          <p className="text-sm text-slate-400 mt-1.5 max-w-2xl">
            {description}
          </p>
        )}
      </div>
      {actions && <div className="shrink-0">{actions}</div>}
    </div>
  );
}
