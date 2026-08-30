"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Loader2, Search } from "lucide-react";
import { api, errorMessage } from "@/lib/api";
import type { SearchHit } from "@/lib/types";
import { cn, humanize } from "@/lib/utils";

const TYPE_ORDER = ["story", "principle", "content_item", "position_brief", "article", "research_note", "video", "transcript_segment", "clip", "book_note"];
const TYPE_LABEL: Record<string, string> = {
  story: "Stories",
  principle: "Principles",
  content_item: "Content",
  position_brief: "Position briefs",
  article: "Articles",
  research_note: "Research notes",
  video: "Videos",
  transcript_segment: "Transcript segments",
  clip: "Clips",
  book_note: "Book notes",
};

export function hitHref(h: SearchHit): string {
  const m = h.meta ?? {};
  switch (h.entity_type) {
    case "story":
      return `/stories/${h.entity_id}`;
    case "principle":
      return `/principles/${h.entity_id}`;
    case "content_item":
      return `/content/${h.entity_id}`;
    case "position_brief":
      return `/think/briefs/${h.entity_id}`;
    case "article":
      return m.story_id ? `/stories/${m.story_id}` : "/stories";
    case "research_note":
      return m.story_id ? `/stories/${m.story_id}` : m.principle_id ? `/principles/${m.principle_id}` : "/research";
    case "video":
      return `/videos/${h.entity_id}`;
    case "transcript_segment":
      return m.video_id ? `/videos/${m.video_id}?t=${m.start ?? 0}` : "/videos";
    case "clip":
      return m.video_id ? `/videos/${m.video_id}#clip-${h.entity_id}` : "/videos";
    case "book_note":
      return "/book";
    default:
      return "/";
  }
}

export function SearchPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const router = useRouter();
  const [q, setQ] = React.useState("");
  const [hits, setHits] = React.useState<SearchHit[]>([]);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [active, setActive] = React.useState(0);
  const inputRef = React.useRef<HTMLInputElement>(null);

  React.useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 10);
    } else {
      setQ("");
      setHits([]);
      setError(null);
    }
  }, [open]);

  React.useEffect(() => {
    if (!open) return;
    const term = q.trim();
    if (term.length < 2) {
      setHits([]);
      return;
    }
    let cancelled = false;
    setLoading(true);
    const t = setTimeout(async () => {
      try {
        const res = await api.search(term);
        if (!cancelled) {
          setHits(res.hits);
          setError(null);
          setActive(0);
        }
      } catch (e) {
        if (!cancelled) setError(errorMessage(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }, 200);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [q, open]);

  const grouped = React.useMemo(() => {
    const map = new Map<string, SearchHit[]>();
    for (const h of hits) {
      const arr = map.get(h.entity_type) ?? [];
      arr.push(h);
      map.set(h.entity_type, arr);
    }
    const keys = [...map.keys()].sort((a, b) => (TYPE_ORDER.indexOf(a) + 100) % 100 - ((TYPE_ORDER.indexOf(b) + 100) % 100));
    return keys.map((k) => ({ type: k, hits: map.get(k)! }));
  }, [hits]);
  const flat = React.useMemo(() => grouped.flatMap((g) => g.hits), [grouped]);

  const go = (h: SearchHit) => {
    onClose();
    router.push(hitHref(h));
  };

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 bg-zinc-900/40 p-4 pt-[10vh]" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="mx-auto w-full max-w-2xl overflow-hidden rounded-lg border border-zinc-200 bg-white shadow-xl">
        <div className="flex items-center gap-2 border-b border-zinc-200 px-3">
          <Search className="h-4 w-4 text-zinc-400" />
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") {
                e.preventDefault();
                setActive((a) => Math.min(a + 1, flat.length - 1));
              } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setActive((a) => Math.max(a - 1, 0));
              } else if (e.key === "Enter" && flat[active]) {
                go(flat[active]);
              } else if (e.key === "Escape") onClose();
            }}
            placeholder="Search everything (hybrid keyword + semantic)"
            className="h-11 flex-1 bg-transparent text-sm outline-none placeholder:text-zinc-400"
          />
          {loading ? <Loader2 className="h-4 w-4 animate-spin text-zinc-400" /> : null}
          <kbd className="rounded border border-zinc-200 px-1 font-mono text-[10px] text-zinc-400">esc</kbd>
        </div>
        <div className="max-h-[60vh] overflow-y-auto">
          {error ? <p className="px-4 py-3 text-xs text-red-700">{error}</p> : null}
          {!error && q.trim().length >= 2 && !loading && hits.length === 0 ? <p className="px-4 py-6 text-center text-xs text-zinc-500">No results for “{q.trim()}”.</p> : null}
          {q.trim().length < 2 ? <p className="px-4 py-6 text-center text-xs text-zinc-500">Type at least two characters. Results are grouped by entity type.</p> : null}
          {grouped.map((g) => (
            <div key={g.type}>
              <div className="sticky top-0 bg-zinc-50 px-4 py-1 text-[11px] font-semibold uppercase tracking-wider text-zinc-500">{TYPE_LABEL[g.type] ?? humanize(g.type)}</div>
              {g.hits.map((h) => {
                const idx = flat.indexOf(h);
                return (
                  <button
                    key={`${h.entity_type}-${h.entity_id}`}
                    type="button"
                    onMouseEnter={() => setActive(idx)}
                    onClick={() => go(h)}
                    className={cn("block w-full px-4 py-2 text-left", idx === active ? "bg-accent-soft" : "hover:bg-zinc-50")}
                  >
                    <div className="truncate text-[13px] font-medium text-zinc-900">{h.title || "(untitled)"}</div>
                    <div className="line-clamp-2 text-xs text-zinc-500">{h.snippet}</div>
                  </button>
                );
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
