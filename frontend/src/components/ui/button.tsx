"use client";

import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-1.5 whitespace-nowrap border font-heading transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40 disabled:pointer-events-none disabled:opacity-45",
  {
    variants: {
      variant: {
        // Primary — filled accent, paper text (Modernist btn-primary)
        default: "bg-accent text-paper border-accent hover:bg-accent-strong",
        accent: "bg-accent text-paper border-accent hover:bg-accent-strong",
        // Secondary — hairline border, transparent bg (Modernist btn-secondary)
        secondary: "bg-transparent text-ink border-divider hover:bg-ink/7",
        // Ghost — plain accent text (Modernist btn-ghost)
        ghost: "bg-transparent text-accent border-transparent hover:bg-accent-soft",
        warn: "bg-highlight text-ink border-highlight hover:opacity-90",
        outlineWarn: "bg-transparent text-highlight-strong border-highlight hover:bg-highlight-soft",
        danger: "bg-transparent text-danger border-danger/50 hover:bg-danger-soft",
        link: "bg-transparent border-transparent text-accent underline-offset-2 hover:underline px-0",
      },
      size: {
        sm: "h-7 px-2.5 text-xs",
        md: "h-8 px-3 text-[13px]",
        lg: "h-9 px-4 text-sm",
        icon: "h-7 w-7 p-0",
      },
    },
    defaultVariants: { variant: "secondary", size: "md" },
  },
);

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {
  loading?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(({ className, variant, size, loading, children, disabled, type, ...props }, ref) => (
  <button ref={ref} type={type ?? "button"} className={cn(buttonVariants({ variant, size }), className)} disabled={disabled || loading} {...props}>
    {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
    {children}
  </button>
));
Button.displayName = "Button";
export { buttonVariants };
