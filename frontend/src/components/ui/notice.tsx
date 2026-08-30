import * as React from "react";
import { AlertTriangle, CheckCircle2, Info, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";

export function Notice({ kind = "info", children, className, onDismiss }: { kind?: "info" | "success" | "warn" | "error"; children: React.ReactNode; className?: string; onDismiss?: () => void }) {
  const styles = {
    info: "border-zinc-200 bg-zinc-50 text-zinc-700",
    success: "border-emerald-200 bg-emerald-50 text-emerald-800",
    warn: "border-warn/40 bg-warn-soft text-[#9a3a1c]",
    error: "border-red-200 bg-red-50 text-red-800",
  }[kind];
  const Icon = { info: Info, success: CheckCircle2, warn: AlertTriangle, error: XCircle }[kind];
  return (
    <div className={cn("flex items-start gap-2 rounded-md border px-3 py-2 text-[13px]", styles, className)} role={kind === "error" ? "alert" : undefined}>
      <Icon className="mt-0.5 h-3.5 w-3.5 shrink-0" />
      <div className="min-w-0 flex-1 break-words">{children}</div>
      {onDismiss ? (
        <button type="button" onClick={onDismiss} className="text-xs opacity-70 hover:opacity-100">
          Dismiss
        </button>
      ) : null}
    </div>
  );
}

export function ErrorNotice({ error, className }: { error: string | null | undefined; className?: string }) {
  if (!error) return null;
  return (
    <Notice kind="error" className={className}>
      {error}
    </Notice>
  );
}

export function EmptyState({ title, children, className }: { title: string; children?: React.ReactNode; className?: string }) {
  return (
    <div className={cn("rounded-md border border-dashed border-zinc-300 bg-white px-4 py-6 text-center", className)}>
      <p className="text-[13px] font-medium text-zinc-700">{title}</p>
      {children ? <div className="mt-1 text-xs text-zinc-500">{children}</div> : null}
    </div>
  );
}
