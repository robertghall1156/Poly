"use client";

import { cn } from "@/lib/utils";

export function Switch({ checked, onChange, disabled, label, warn, id }: { checked: boolean; onChange: (v: boolean) => void; disabled?: boolean; label?: string; warn?: boolean; id?: string }) {
  return (
    <label className={cn("inline-flex cursor-pointer select-none items-center gap-2", disabled && "cursor-not-allowed opacity-60")}>
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={cn(
          "relative h-5 w-9 border transition-colors",
          checked ? (warn ? "border-highlight bg-highlight" : "border-accent bg-accent") : "border-divider bg-ink/15",
        )}
      >
        <span className={cn("absolute top-0.5 h-3.5 w-3.5 bg-paper shadow transition-all", checked ? "left-[18px]" : "left-0.5")} />
      </button>
      {label ? <span className="text-[13px] text-zinc-800">{label}</span> : null}
    </label>
  );
}
