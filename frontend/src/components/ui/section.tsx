import * as React from "react";
import { cn } from "@/lib/utils";

export function PageHeader({ title, kicker, meta, description, actions, className }: { title: string; kicker?: React.ReactNode; meta?: React.ReactNode; description?: React.ReactNode; actions?: React.ReactNode; className?: string }) {
  return (
    <div className={cn("mb-7", className)}>
      {kicker || meta ? (
        <div className="mb-1.5 flex items-baseline justify-between gap-4">
          <span className="kicker">{kicker}</span>
          {meta ? <span className="meta">{meta}</span> : null}
        </div>
      ) : null}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-[42px] font-heading leading-[1.12] tracking-[-0.015em] text-ink">{title}</h1>
          {description ? <p className="mt-1.5 max-w-2xl text-[13.5px] text-zinc-600">{description}</p> : null}
        </div>
        {actions ? <div className="flex flex-wrap items-center gap-2 pb-1.5">{actions}</div> : null}
      </div>
      <hr className="rule mt-5" />
    </div>
  );
}

export function Section({ title, description, actions, children, className, id }: { title: string; description?: React.ReactNode; actions?: React.ReactNode; children: React.ReactNode; className?: string; id?: string }) {
  return (
    <section id={id} className={cn("mb-8", className)}>
      <div className="mb-3 flex flex-wrap items-end justify-between gap-2 border-t-2 border-divider pt-3">
        <div>
          <h2 className="font-heading text-[13px] uppercase tracking-[0.08em] text-zinc-500">{title}</h2>
          {description ? <p className="mt-0.5 text-xs text-zinc-500">{description}</p> : null}
        </div>
        {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
      </div>
      {children}
    </section>
  );
}

export function Panel({ children, className, title, actions }: { children: React.ReactNode; className?: string; title?: string; actions?: React.ReactNode }) {
  return (
    <div className={cn("border border-divider bg-paper", className)}>
      {title ? (
        <div className="flex items-center justify-between border-b border-divider px-3 py-2">
          <h3 className="font-heading text-[12px] uppercase tracking-[0.06em] text-zinc-700">{title}</h3>
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
