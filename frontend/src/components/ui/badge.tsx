import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 border bg-transparent px-1.5 py-0 text-[10.5px] font-medium uppercase tracking-[0.04em] leading-[18px] whitespace-nowrap",
  {
    variants: {
      variant: {
        neutral: "border-divider text-zinc-600",
        outline: "border-divider text-zinc-700",
        accent: "border-accent text-accent",
        warn: "border-highlight text-highlight-strong",
        success: "border-accent text-accent-strong",
        danger: "border-danger/60 text-danger",
        amber: "border-highlight text-highlight-strong",
        violet: "border-zinc-400 text-zinc-600",
        blue: "border-secondary/60 text-secondary",
      },
    },
    defaultVariants: { variant: "neutral" },
  },
);

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement>, VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}
