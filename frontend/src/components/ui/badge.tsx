import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva("inline-flex items-center gap-1 rounded border px-1.5 py-0 text-[11px] font-medium leading-[18px] whitespace-nowrap", {
  variants: {
    variant: {
      neutral: "border-zinc-200 bg-zinc-100 text-zinc-700",
      outline: "border-zinc-300 bg-white text-zinc-700",
      accent: "border-accent/30 bg-accent-soft text-[#0f6f74]",
      warn: "border-warn/40 bg-warn-soft text-[#b3401f]",
      success: "border-emerald-200 bg-emerald-50 text-emerald-800",
      danger: "border-red-200 bg-red-50 text-red-800",
      amber: "border-amber-200 bg-amber-50 text-amber-800",
      violet: "border-violet-200 bg-violet-50 text-violet-800",
      blue: "border-sky-200 bg-sky-50 text-sky-800",
    },
  },
  defaultVariants: { variant: "neutral" },
});

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement>, VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}
