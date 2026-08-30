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
          "relative h-5 w-9 rounded-full border transition-colors",
          checked ? (warn ? "border-warn bg-warn" : "border-accent bg-accent") : "border-zinc-300 bg-zinc-200",
        )}
      >
        <span className={cn("absolute top-0.5 h-3.5 w-3.5 rounded-full bg-white shadow transition-all", checked ? "left-[18px]" : "left-0.5")} />
      </button>
      {label ? <span className="text-[13px] text-zinc-800">{label}</span> : null}
    </label>
  );
}
