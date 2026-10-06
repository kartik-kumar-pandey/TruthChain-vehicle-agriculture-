import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default:
          "bg-cyan-600 text-white shadow hover:bg-cyan-500 active:bg-cyan-700",
        secondary:
          "bg-slate-700 text-slate-100 hover:bg-slate-600 active:bg-slate-800",
        outline:
          "border border-slate-700 bg-transparent text-slate-200 hover:bg-slate-800",
        ghost:
          "bg-transparent text-slate-200 hover:bg-slate-800 hover:text-white",
        destructive:
          "bg-red-600 text-white hover:bg-red-500 active:bg-red-700",
        success:
          "bg-emerald-600 text-white hover:bg-emerald-500 active:bg-emerald-700",
        blockchain:
          "bg-gradient-to-r from-purple-600 to-indigo-600 text-white shadow-lg shadow-purple-900/30 hover:from-purple-500 hover:to-indigo-500",
      },
      size: {
        sm: "h-8 px-3 text-xs",
        md: "h-10 px-4 py-2",
        lg: "h-12 px-6 text-base",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "md",
    },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(buttonVariants({ variant, size }), className)}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";

export { buttonVariants };
