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
    <div className={cn("flex gap-0.5 border-b border-zinc-200", className)} role="tablist">
      {tabs.map((t) => (
        <button
          key={t.id}
          role="tab"
          type="button"
          aria-selected={value === t.id}
          onClick={() => onChange(t.id)}
          className={cn(
            "-mb-px border-b-2 px-3 py-2 text-[13px] font-medium transition-colors",
            value === t.id ? "border-accent text-zinc-900" : "border-transparent text-zinc-500 hover:text-zinc-800",
          )}
        >
          {t.label}
          {t.count != null ? <span className="ml-1.5 rounded bg-zinc-100 px-1 text-[11px] text-zinc-600">{t.count}</span> : null}
        </button>
      ))}
    </div>
  );
}
