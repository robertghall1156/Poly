import * as React from "react";
import { cn } from "@/lib/utils";

export function PageHeader({ title, description, actions, className }: { title: string; description?: React.ReactNode; actions?: React.ReactNode; className?: string }) {
  return (
    <div className={cn("mb-4 flex flex-wrap items-start justify-between gap-3", className)}>
      <div className="min-w-0">
        <h1 className="text-lg font-semibold tracking-tight text-zinc-900">{title}</h1>
        {description ? <p className="mt-0.5 text-[13px] text-zinc-500">{description}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  );
}

export function Section({ title, description, actions, children, className, id }: { title: string; description?: React.ReactNode; actions?: React.ReactNode; children: React.ReactNode; className?: string; id?: string }) {
  return (
    <section id={id} className={cn("mb-6", className)}>
      <div className="mb-2 flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 className="text-[11px] font-semibold uppercase tracking-wider text-zinc-500">{title}</h2>
          {description ? <p className="text-xs text-zinc-500">{description}</p> : null}
        </div>
        {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
      </div>
      {children}
    </section>
  );
}

export function Panel({ children, className, title, actions }: { children: React.ReactNode; className?: string; title?: string; actions?: React.ReactNode }) {
  return (
    <div className={cn("rounded-md border border-zinc-200 bg-white", className)}>
      {title ? (
        <div className="flex items-center justify-between border-b border-zinc-200 px-3 py-2">
          <h3 className="text-[13px] font-semibold text-zinc-800">{title}</h3>
          {actions}
        </div>
      ) : null}
      <div className="px-3 py-2.5">{children}</div>
    </div>
  );
}

export function KV({ label, children, className }: { label: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("py-1", className)}>
      <dt className="text-[11px] uppercase tracking-wide text-zinc-500">{label}</dt>
      <dd className="text-[13px] text-zinc-800">{children}</dd>
    </div>
  );
}

export function BulletList({ items, empty = "None" }: { items: (string | null | undefined)[] | null | undefined; empty?: string }) {
  const list = (items ?? []).filter(Boolean) as string[];
  if (!list.length) return <p className="text-xs text-zinc-400">{empty}</p>;
  return (
    <ul className="list-disc space-y-0.5 pl-4 text-[13px] text-zinc-800">
      {list.map((it, i) => (
        <li key={i}>{it}</li>
      ))}
    </ul>
  );
}
