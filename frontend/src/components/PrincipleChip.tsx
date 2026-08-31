import Link from "next/link";
import type { StoryPrincipleRef } from "@/lib/types";
import { cn } from "@/lib/utils";

const REL_STYLE: Record<string, string> = {
  challenges: "border-highlight text-highlight-strong",
  contradicts: "border-highlight text-highlight-strong",
  supports: "border-accent text-accent-strong",
  tests: "border-divider text-secondary",
};

export function PrincipleChip({ p }: { p: StoryPrincipleRef }) {
  return (
    <Link
      href={`/think/beliefs/${p.id}`}
      title={p.note || `${p.relation} · strength ${(p.strength * 100).toFixed(0)}%`}
      className={cn("inline-flex max-w-full items-center gap-1 border px-2 py-0.5 text-[11px] uppercase tracking-[0.03em] hover:opacity-80", REL_STYLE[p.relation] ?? "border-accent text-accent-strong")}
    >
      <span className="truncate">{p.title}</span>
      <span className="opacity-70">· {p.relation}</span>
    </Link>
  );
}
