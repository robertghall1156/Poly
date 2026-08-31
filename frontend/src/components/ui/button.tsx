"use client";

import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-md border font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-brand text-white border-brand hover:opacity-90",
        secondary: "bg-white text-zinc-800 border-zinc-300 hover:bg-zinc-50",
        ghost: "bg-transparent text-zinc-700 border-transparent hover:bg-zinc-100",
        accent: "bg-accent text-white border-accent hover:bg-accent-strong",
        warn: "bg-warn text-white border-warn hover:opacity-90",
        outlineWarn: "bg-warn-soft text-[#b3401f] border-warn/60 hover:bg-[#fbe0d6]",
        danger: "bg-white text-red-700 border-red-300 hover:bg-red-50",
        link: "bg-transparent border-transparent text-accent-strong underline-offset-2 hover:underline px-0",
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
