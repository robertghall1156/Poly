"use client";

import * as React from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

export function Dialog({ open, onClose, title, children, footer, className, wide }: { open: boolean; onClose: () => void; title: string; children: React.ReactNode; footer?: React.ReactNode; className?: string; wide?: boolean }) {
  React.useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-ink/40 p-4 pt-[8vh]" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div role="dialog" aria-modal="true" className={cn("w-full border-2 border-divider bg-paper shadow-[var(--shadow-lg)]", wide ? "max-w-3xl" : "max-w-lg", className)}>
        <div className="flex items-center justify-between border-b-2 border-divider px-4 py-2.5">
          <h2 className="font-heading text-[15px] tracking-[-0.01em] text-ink">{title}</h2>
          <button type="button" onClick={onClose} className="p-1 text-zinc-500 hover:bg-ink/7 hover:text-ink" aria-label="Close">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="max-h-[70vh] overflow-y-auto px-4 py-3">{children}</div>
        {footer ? <div className="flex items-center justify-end gap-2 border-t border-divider px-4 py-2.5">{footer}</div> : null}
      </div>
    </div>
  );
}
