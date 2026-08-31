"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

export interface TabDef {
  id: string;
  label: string;
  count?: number;
}

export function Tabs({ tabs, value, onChange, className }: { tabs: TabDef[]; value: string; onChange: (id: string) => void; className?: string }) {
  return (
    <div className={cn("flex gap-4 border-b-2 border-divider", className)} role="tablist">
      {tabs.map((t) => (
        <button
          key={t.id}
          role="tab"
          type="button"
          aria-selected={value === t.id}
          onClick={() => onChange(t.id)}
          className={cn(
            "-mb-0.5 border-b-2 px-0.5 pb-2 pt-1 font-heading text-xs uppercase tracking-[0.08em] transition-colors",
            value === t.id ? "border-accent text-accent" : "border-transparent text-zinc-500 hover:text-zinc-800",
          )}
        >
          {t.label}
          {t.count != null ? <span className="ml-1.5 font-sans font-normal text-[11px] normal-case tracking-normal text-zinc-500">{t.count}</span> : null}
        </button>
      ))}
    </div>
  );
}
