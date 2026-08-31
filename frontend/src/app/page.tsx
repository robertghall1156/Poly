"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useAction, useApi } from "@/lib/hooks";
import type { Dashboard, StoryRowData } from "@/lib/types";
import { labelFormat, relTime } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { ListSkeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorNotice } from "@/components/ui/notice";
import { Section } from "@/components/ui/section";
import { JobStatus } from "@/components/JobStatus";
import { StoryCard } from "@/components/StoryCard";
import { StatusBadge } from "@/components/badges";

/** Map a story's recommended format onto a Create flow. */
function createFlowFor(format: string | undefined): string {
  if (!format) return "short";
  if (["youtube_short", "tiktok", "instagram_reel"].includes(format)) return "short";
  if (format === "meme") return "meme";
  if (format === "youtube") return "youtube";
  if (format === "podcast") return "podcast";
  if (["article", "newsletter"].includes(format)) return "article";
  if (format.endsWith("_post") || format === "x_thread") return "post";
  return "short";
}

export default function HomePage() {
  const dash = useApi(() => api.dashboard(), []);
  const router = useRouter();
  const [ingestJob, setIngestJob] = React.useState<string | null>(null);
  const act = useAction();

  const runIngest = async () => {
    const j = await act.run(() => api.runIngest());
    if (j) setIngestJob(j.id);
  };

  const updateStory = (s: StoryRowData) => {
    dash.setData((prev) => {
      if (!prev) return prev;
      const fix = (list: StoryRowData[]) => list.map((x) => (x.id === s.id ? s : x));
      return { ...prev, today: fix(prev.today), think_about: fix(prev.think_about), create: fix(prev.create) };
    });
  };

  const d = dash.data;

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold tracking-tight text-brand">Discover the news, think it through, create deliberately.</h1>
          <p className="mt-0.5 text-[13px] text-zinc-500">
            Poly follows your{" "}
            <Link href="/discover?tab=research" className="text-zinc-500 underline decoration-zinc-300 underline-offset-2 hover:text-accent-strong">
              news sources
            </Link>
            , connects stories to what you believe, and nothing is ever posted automatically.
          </p>
        </div>
        <Button variant="default" onClick={runIngest} loading={act.busy}>
          Get today&apos;s news
        </Button>
      </div>
      <ErrorNotice error={act.error} className="mb-3" />
      {ingestJob ? <JobStatus jobId={ingestJob} label="Getting today's news" className="mb-4" onDone={(j) => j.status === "succeeded" && dash.reload()} /> : null}
      <ErrorNotice error={dash.error} className="mb-3" />

      <Section title="What happened?" description="Today's most relevant stories.">
        {dash.loading ? <ListSkeleton rows={3} /> : null}
        {d && d.today.length === 0 ? <EmptyState title="No stories yet.">Press &ldquo;Get today&apos;s news&rdquo; above to fetch the latest.</EmptyState> : null}
        {d && d.today.length > 0 ? (
          <div className="rounded-md border border-zinc-200 bg-white px-4">
            {d.today.slice(0, 5).map((s) => (
              <StoryCard key={s.id} story={s} onChange={updateStory} />
            ))}
          </div>
        ) : null}
      </Section>

      <div className="grid gap-6 lg:grid-cols-2">
        <Section title="What should I think about?" description="Stories that test or sharpen what you believe.">
          {d && d.think_about.length === 0 ? <EmptyState title="Nothing pressing right now." /> : null}
          {d && d.think_about.length > 0 ? (
            <div className="rounded-md border border-zinc-200 bg-white px-4">
              {d.think_about.slice(0, 3).map((s) => (
                <StoryCard key={s.id} story={s} onChange={updateStory} compact />
              ))}
            </div>
          ) : null}
        </Section>

        <Section title="What can I create?" description="The best opportunities right now — one click to start.">
          {d && d.create.length === 0 ? <EmptyState title="No opportunities scored yet.">They appear once stories are analysed.</EmptyState> : null}
          {d && d.create.length > 0 ? (
            <div className="rounded-md border border-zinc-200 bg-white">
              {d.create.map((s) => {
                const opp = s.content_potential[0];
                const flow = createFlowFor(opp?.format || s.recommended_format);
                return (
                  <div key={s.id} className="flex items-start gap-3 border-b border-zinc-200 px-4 py-2.5 last:border-b-0">
                    <div className="min-w-0 flex-1">
                      <Link href={`/discover/stories/${s.id}`} className="text-[13px] font-medium text-zinc-900 hover:text-accent-strong">
                        {s.title}
                      </Link>
                      {opp?.angle ? <p className="text-xs text-zinc-600">{opp.angle}</p> : null}
                      <p className="text-[11px] text-zinc-400">{labelFormat(opp?.format || s.recommended_format) || "Short"}</p>
                    </div>
                    <Button size="sm" variant="accent" className="shrink-0" onClick={() => router.push(`/create?format=${flow}&source=story&id=${s.id}`)}>
                      Create
                    </Button>
                  </div>
                );
              })}
            </div>
          ) : null}
        </Section>
      </div>

      <Section title="What am I working on?" description="Pick up where you left off.">
        {d ? <WorkingOn d={d} /> : null}
      </Section>
    </div>
  );
}

function WorkingOn({ d }: { d: Dashboard }) {
  const c = d.continue;
  const empty = c.think_sessions.length === 0 && c.briefs.length === 0 && c.content.length === 0;
  if (empty)
    return (
      <EmptyState title="Nothing in progress.">
        Think through a story above, or press <span className="font-medium">+ Create</span> in the top bar to start something.
      </EmptyState>
    );
  return (
    <div className="grid gap-3 md:grid-cols-3">
      <div className="rounded-md border border-zinc-200 bg-white">
        <div className="border-b border-zinc-200 px-3 py-1.5 text-xs font-semibold text-zinc-700">Ideas I&apos;m thinking through</div>
        {c.think_sessions.length === 0 ? <p className="px-3 py-2 text-xs text-zinc-400">None right now.</p> : null}
        {c.think_sessions.map((t) => (
          <Link key={t.id} href={`/think/${t.id}`} className="block border-b border-zinc-100 px-3 py-2 last:border-b-0 hover:bg-zinc-50">
            <div className="truncate text-[13px] font-medium text-zinc-900">{t.title}</div>
            <div className="text-xs text-zinc-500">
              {t.exchanges} exchange{t.exchanges === 1 ? "" : "s"} · {relTime(t.updated_at)}
            </div>
          </Link>
        ))}
      </div>
      <div className="rounded-md border border-zinc-200 bg-white">
        <div className="border-b border-zinc-200 px-3 py-1.5 text-xs font-semibold text-zinc-700">Positions in draft</div>
        {c.briefs.length === 0 ? <p className="px-3 py-2 text-xs text-zinc-400">No drafts.</p> : null}
        {c.briefs.map((b) => (
          <Link key={b.id} href={`/think/positions/${b.id}`} className="block border-b border-zinc-100 px-3 py-2 last:border-b-0 hover:bg-zinc-50">
            <div className="truncate text-[13px] font-medium text-zinc-900">{b.issue}</div>
            <div className="text-xs text-zinc-500">Confidence {Math.round(b.confidence * 100)}%</div>
          </Link>
        ))}
      </div>
      <div className="rounded-md border border-zinc-200 bg-white">
        <div className="border-b border-zinc-200 px-3 py-1.5 text-xs font-semibold text-zinc-700">Drafts in progress</div>
        {c.content.length === 0 ? <p className="px-3 py-2 text-xs text-zinc-400">No drafts in progress.</p> : null}
        {c.content.map((it) => (
          <Link key={it.id} href={`/library/content/${it.id}`} className="flex items-center gap-2 border-b border-zinc-100 px-3 py-2 last:border-b-0 hover:bg-zinc-50">
            <span className="min-w-0 flex-1 truncate text-[13px] font-medium text-zinc-900">{it.title}</span>
            <span className="text-[11px] text-zinc-500">{labelFormat(it.format)}</span>
            {it.status ? <StatusBadge status={it.status} /> : null}
          </Link>
        ))}
      </div>
    </div>
  );
}
