import * as React from "react";
import { AlertTriangle, CheckCircle2, Info, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";

export function Notice({ kind = "info", children, className, onDismiss }: { kind?: "info" | "success" | "warn" | "error"; children: React.ReactNode; className?: string; onDismiss?: () => void }) {
  const styles = {
    info: "border-divider bg-surface text-zinc-700",
    success: "border-accent bg-accent-soft text-accent-strong",
    warn: "border-highlight bg-highlight-soft text-highlight-strong",
    error: "border-danger/60 bg-danger-soft text-danger",
  }[kind];
  const Icon = { info: Info, success: CheckCircle2, warn: AlertTriangle, error: XCircle }[kind];
  return (
    <div className={cn("flex items-start gap-2 border px-3 py-2 text-[13px]", styles, className)} role={kind === "error" ? "alert" : undefined}>
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
    <div className={cn("border border-dashed border-divider px-4 py-6 text-center", className)}>
      <p className="font-heading text-[14px] text-zinc-700">{title}</p>
      {children ? <div className="mt-1 text-xs text-zinc-500">{children}</div> : null}
    </div>
  );
}
