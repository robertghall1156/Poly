"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import type { Story, StoryRowData } from "@/lib/types";
import { cn, labelFormat, relTime } from "@/lib/utils";
import { Select } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Tabs } from "@/components/ui/tabs";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { ListSkeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorNotice } from "@/components/ui/notice";
import { PageHeader } from "@/components/ui/section";
import { Relevance, StatusBadge } from "@/components/badges";
import { StoryCard } from "@/components/StoryCard";
import { ResearchSection } from "@/components/discover/ResearchSection";

const TABS = [
  { id: "today", label: "Today" },
  { id: "all", label: "All stories" },
  { id: "research", label: "Research" },
];

export default function DiscoverPage() {
  return (
    <React.Suspense fallback={<ListSkeleton />}>
      <DiscoverInner />
    </React.Suspense>
  );
}

function DiscoverInner() {
  const params = useSearchParams();
  const router = useRouter();
  const tab = TABS.some((t) => t.id === params.get("tab")) ? (params.get("tab") as string) : "today";
  return (
    <div>
      <PageHeader title="Discover" description="What's happening, why it matters, and where it comes from." />
      <Tabs tabs={TABS} value={tab} onChange={(id) => router.replace(`/discover?tab=${id}`)} className="mb-4" />
      {tab === "today" ? <TodayTab /> : tab === "all" ? <AllStoriesTab /> : <ResearchSection />}
    </div>
  );
}

function TodayTab() {
  const stories = useApi(() => api.stories({ days: 3, limit: 200 }), []);
  const [topic, setTopic] = React.useState<string | null>(null);

  const topics = React.useMemo(() => {
    const counts = new Map<string, number>();
    for (const s of stories.data ?? []) for (const t of s.topics ?? []) counts.set(t, (counts.get(t) ?? 0) + 1);
    return [...counts.entries()].sort((a, b) => b[1] - a[1]);
  }, [stories.data]);

  const rows = React.useMemo(() => {
    return (stories.data ?? [])
      .filter((s) => (topic ? s.topics.includes(topic) : true))
      .filter((s) => s.status !== "ignored")
      .sort((a, b) => b.relevance_score - a.relevance_score || b.last_updated.localeCompare(a.last_updated));
  }, [stories.data, topic]);

  const update = (s: StoryRowData) => stories.setData((prev) => (prev ? prev.map((x) => (x.id === s.id ? ({ ...x, ...s } as Story) : x)) : prev));

  return (
    <div>
      {topics.length ? (
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => setTopic(null)}
            className={cn("rounded-full border px-2.5 py-0.5 text-xs", topic === null ? "border-brand bg-brand text-white" : "border-zinc-300 text-zinc-700 hover:bg-zinc-50")}
          >
            All topics
          </button>
          {topics.map(([t, n]) => (
            <button
              key={t}
              type="button"
              onClick={() => setTopic(topic === t ? null : t)}
              className={cn("rounded-full border px-2.5 py-0.5 text-xs", topic === t ? "border-brand bg-brand text-white" : "border-zinc-300 text-zinc-700 hover:bg-zinc-50")}
            >
              {t} <span className="opacity-60">{n}</span>
            </button>
          ))}
        </div>
      ) : null}
      <ErrorNotice error={stories.error} className="mb-3" />
      {stories.loading ? <ListSkeleton rows={5} /> : null}
      {stories.data && rows.length === 0 ? (
        <EmptyState title="No stories yet.">
          {stories.data.length === 0 ? "Press “Get today's news” on Home to fetch the latest." : "No stories match this topic."}
        </EmptyState>
      ) : null}
      {rows.length > 0 ? (
        <div className="rounded-md border border-zinc-200 bg-white px-4">
          {rows.map((s) => (
            <StoryCard key={s.id} story={s} onChange={update} />
          ))}
        </div>
      ) : null}
    </div>
  );
}

function AllStoriesTab() {
  const [days, setDays] = React.useState(30);
  const [topic, setTopic] = React.useState("");
  const stories = useApi(() => api.stories({ days, limit: 300 }), [days]);
  const topics = React.useMemo(() => [...new Set((stories.data ?? []).flatMap((s) => s.topics ?? []))].sort(), [stories.data]);
  const rows = (stories.data ?? []).filter((s) => !topic || s.topics.includes(topic));

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Select value={days} onChange={(e) => setDays(Number(e.target.value))}>
          <option value={3}>Last 3 days</option>
          <option value={7}>Last 7 days</option>
          <option value={30}>Last 30 days</option>
          <option value={365}>Last year</option>
        </Select>
        <Select value={topic} onChange={(e) => setTopic(e.target.value)}>
          <option value="">Any topic</option>
          {topics.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </Select>
      </div>
      <ErrorNotice error={stories.error} className="mb-3" />
      {stories.loading ? <ListSkeleton /> : null}
      {stories.data && rows.length === 0 ? <EmptyState title="No stories yet.">Press &ldquo;Get today&apos;s news&rdquo; on Home to fetch the latest.</EmptyState> : null}
      {rows.length > 0 ? (
        <Table>
          <THead>
            <tr>
              <TH>Story</TH>
              <TH>Publications</TH>
              <TH className="text-right">Articles</TH>
              <TH>Topics</TH>
              <TH className="text-right">Relevance</TH>
              <TH>Status</TH>
              <TH>Updated</TH>
            </tr>
          </THead>
          <TBody>
            {rows.map((s) => (
              <TR key={s.id}>
                <TD className="max-w-md">
                  <Link href={`/discover/stories/${s.id}`} className="font-medium text-zinc-900 hover:text-accent-strong">
                    {s.title}
                  </Link>
                  {s.recommended_format ? <div className="text-[11px] text-zinc-400">Good fit: {labelFormat(s.recommended_format)}</div> : null}
                </TD>
                <TD className="text-xs text-zinc-600">{s.publications.join(", ") || "—"}</TD>
                <TD className="text-right tabular-nums">
                  {s.article_count}
                  {s.duplicate_count ? <span className="text-zinc-400"> +{s.duplicate_count}</span> : null}
                </TD>
                <TD>
                  <div className="flex flex-wrap gap-1">
                    {s.topics.map((t) => (
                      <Badge key={t} variant="neutral">
                        {t}
                      </Badge>
                    ))}
                  </div>
                </TD>
                <TD className="text-right">
                  <Relevance value={s.relevance_score} />
                </TD>
                <TD>
                  <StatusBadge status={s.status} />
                </TD>
                <TD className="whitespace-nowrap text-xs text-zinc-500">{relTime(s.last_updated)}</TD>
              </TR>
            ))}
          </TBody>
        </Table>
      ) : null}
    </div>
  );
}
