"use client";

import * as React from "react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import type { Story, StoryRowData } from "@/lib/types";
import { cn } from "@/lib/utils";
import { ListSkeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorNotice } from "@/components/ui/notice";
import { PageHeader } from "@/components/ui/section";
import { StoryRow } from "@/components/StoryRow";

export default function TodayPage() {
  const stories = useApi(() => api.stories({ days: 3, limit: 200 }), []);
  const [topic, setTopic] = React.useState<string | null>(null);
  const [minRel, setMinRel] = React.useState(0);
  const [showIgnored, setShowIgnored] = React.useState(false);

  const topics = React.useMemo(() => {
    const counts = new Map<string, number>();
    for (const s of stories.data ?? []) for (const t of s.topics ?? []) counts.set(t, (counts.get(t) ?? 0) + 1);
    return [...counts.entries()].sort((a, b) => b[1] - a[1]);
  }, [stories.data]);

  const rows = React.useMemo(() => {
    return (stories.data ?? [])
      .filter((s) => (topic ? s.topics.includes(topic) : true))
      .filter((s) => s.relevance_score >= minRel)
      .filter((s) => showIgnored || s.status !== "ignored")
      .sort((a, b) => b.relevance_score - a.relevance_score || b.last_updated.localeCompare(a.last_updated));
  }, [stories.data, topic, minRel, showIgnored]);

  const update = (s: StoryRowData) => stories.setData((prev) => (prev ? prev.map((x) => (x.id === s.id ? ({ ...x, ...s } as Story) : x)) : prev));

  return (
    <div>
      <PageHeader title="Today" description="Stories from the last three days, ranked by relevance to your principles." />
      <div className="mb-3 flex flex-wrap items-center gap-2 rounded-md border border-zinc-200 bg-white px-3 py-2">
        <span className="text-xs text-zinc-500">Topic</span>
        <button type="button" onClick={() => setTopic(null)} className={cn("rounded-full border px-2 py-0.5 text-xs", topic === null ? "border-zinc-800 bg-zinc-800 text-white" : "border-zinc-300 text-zinc-700 hover:bg-zinc-50")}>
          All
        </button>
        {topics.map(([t, n]) => (
          <button key={t} type="button" onClick={() => setTopic(topic === t ? null : t)} className={cn("rounded-full border px-2 py-0.5 text-xs", topic === t ? "border-zinc-800 bg-zinc-800 text-white" : "border-zinc-300 text-zinc-700 hover:bg-zinc-50")}>
            {t} <span className="opacity-60">{n}</span>
          </button>
        ))}
        <div className="ml-auto flex items-center gap-2">
          <label className="text-xs text-zinc-500">Min relevance {Math.round(minRel * 100)}</label>
          <input type="range" min={0} max={1} step={0.05} value={minRel} onChange={(e) => setMinRel(Number(e.target.value))} className="w-32" />
          <label className="flex items-center gap-1 text-xs text-zinc-500">
            <input type="checkbox" checked={showIgnored} onChange={(e) => setShowIgnored(e.target.checked)} /> show ignored
          </label>
        </div>
      </div>
      <ErrorNotice error={stories.error} className="mb-3" />
      {stories.loading ? <ListSkeleton rows={5} /> : null}
      {stories.data && rows.length === 0 ? (
        <EmptyState title="No stories match.">
          {stories.data.length === 0 ? "No stories ingested in the last three days. Run ingest from Home or Research → Feeds." : "Loosen the topic or relevance filter."}
        </EmptyState>
      ) : null}
      {rows.length > 0 ? (
        <div className="rounded-md border border-zinc-200 bg-white px-4">
          {rows.map((s) => (
            <StoryRow key={s.id} story={s} onChange={update} />
          ))}
        </div>
      ) : null}
    </div>
  );
}
