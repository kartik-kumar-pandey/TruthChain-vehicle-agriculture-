import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium transition-colors",
  {
    variants: {
      variant: {
        default:
          "border-slate-300 dark:border-slate-700 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200",
        success:
          "border-emerald-300 dark:border-emerald-800 bg-emerald-50 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300",
        warning:
          "border-amber-300 dark:border-amber-800 bg-amber-50 dark:bg-amber-950 text-amber-700 dark:text-amber-300",
        danger:
          "border-red-300 dark:border-red-800 bg-red-50 dark:bg-red-950 text-red-700 dark:text-red-300",
        info:
          "border-cyan-300 dark:border-cyan-800 bg-cyan-50 dark:bg-cyan-950 text-cyan-700 dark:text-cyan-300",
        blockchain:
          "border-purple-300 dark:border-purple-800 bg-purple-50 dark:bg-purple-950 text-purple-700 dark:text-purple-300",
        evidence:
          "border-teal-300 dark:border-teal-800 bg-teal-50 dark:bg-teal-950 text-teal-700 dark:text-teal-300",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div
      className={cn(badgeVariants({ variant }), className)}
      {...props}
    />
  );
}

export { badgeVariants };
