import Link from "next/link";
import type { StoryPrincipleRef } from "@/lib/types";
import { cn } from "@/lib/utils";

const REL_STYLE: Record<string, string> = {
  challenges: "border-warn/50 bg-warn-soft text-[#9a3a1c]",
  contradicts: "border-warn/50 bg-warn-soft text-[#9a3a1c]",
  supports: "border-emerald-200 bg-emerald-50 text-emerald-800",
  tests: "border-violet-200 bg-violet-50 text-violet-800",
};

export function PrincipleChip({ p }: { p: StoryPrincipleRef }) {
  return (
    <Link
      href={`/think/beliefs/${p.id}`}
      title={p.note || `${p.relation} · strength ${(p.strength * 100).toFixed(0)}%`}
      className={cn("inline-flex max-w-full items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] hover:opacity-80", REL_STYLE[p.relation] ?? "border-accent/30 bg-accent-soft text-[#0f6f74]")}
    >
      <span className="truncate">{p.title}</span>
      <span className="opacity-70">· {p.relation}</span>
    </Link>
  );
}
