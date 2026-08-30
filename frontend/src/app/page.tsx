"use client";

import * as React from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useAction, useApi } from "@/lib/hooks";
import type { Dashboard, StoryRowData } from "@/lib/types";
import { fmtDuration, fmtDateTime, labelFormat, relTime } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { ListSkeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorNotice } from "@/components/ui/notice";
import { PageHeader, Section } from "@/components/ui/section";
import { JobStatus } from "@/components/JobStatus";
import { StoryRow } from "@/components/StoryRow";
import { FormatBadge, StatusBadge } from "@/components/badges";

export default function HomePage() {
  const dash = useApi(() => api.dashboard(), []);
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
  const li = d?.last_ingest;

  return (
    <div>
      <PageHeader
        title="What matters today?"
        description={
          d ? (
            <>
              {d.counts.stories_3d} stories in the last 3 days · {d.counts.principles} active principles · {d.counts.content} content items · {d.counts.videos} videos
            </>
          ) : (
            "Loading dashboard…"
          )
        }
        actions={
          <>
            <span className="text-xs text-zinc-500">
              {li?.at ? (
                <>
                  Last ingest {relTime(li.at)}: {li.inserted ?? 0} new, {li.duplicates ?? 0} duplicates, {li.analyzed ?? 0} analysed, {li.feeds_ok ?? 0}/{li.feeds ?? 0} feeds ok
                  {li.error_count ? <span className="text-[#b3401f]"> · {li.error_count} feed errors</span> : null}
                </>
              ) : (
                "No ingest has run yet."
              )}
            </span>
            <Button variant="default" onClick={runIngest} loading={act.busy}>
              Run ingest now
            </Button>
          </>
        }
      />
      <ErrorNotice error={act.error} className="mb-3" />
      {ingestJob ? <JobStatus jobId={ingestJob} label="News ingest" className="mb-4" onDone={(j) => j.status === "succeeded" && dash.reload()} /> : null}
      <ErrorNotice error={dash.error} className="mb-3" />

      <Section title="Today" description="Top developments ranked by relevance to your principles.">
        {dash.loading ? <ListSkeleton rows={3} /> : null}
        {d && d.today.length === 0 ? (
          <EmptyState title="No stories in the last three days.">
            Run ingest with the button above, or manage feeds under Research → Feeds and topics under Settings → News.
          </EmptyState>
        ) : null}
        {d && d.today.length > 0 ? (
          <div className="rounded-md border border-zinc-200 bg-white px-4">
            {d.today.map((s) => (
              <StoryRow key={s.id} story={s} onChange={updateStory} />
            ))}
          </div>
        ) : null}
      </Section>

      <div className="grid gap-6 lg:grid-cols-2">
        <Section title="Think about" description="Stories that challenge or connect with your principles.">
          {d && d.think_about.length === 0 ? <EmptyState title="Nothing to think about yet." /> : null}
          {d && d.think_about.length > 0 ? (
            <div className="rounded-md border border-zinc-200 bg-white px-4">
              {d.think_about.map((s) => (
                <StoryRow key={s.id} story={s} onChange={updateStory} compact />
              ))}
            </div>
          ) : null}
        </Section>
        <Section title="Create" description="Best content opportunities right now.">
          {d && d.create.length === 0 ? <EmptyState title="No content opportunities scored yet." /> : null}
          {d && d.create.length > 0 ? (
            <div className="rounded-md border border-zinc-200 bg-white">
              {d.create.map((s) => {
                const opp = s.content_potential[0];
                return (
                  <div key={s.id} className="flex items-start gap-3 border-b border-zinc-200 px-4 py-2.5 last:border-b-0">
                    <div className="min-w-0 flex-1">
                      <Link href={`/stories/${s.id}`} className="text-[13px] font-medium text-zinc-900 hover:text-accent-strong">
                        {s.title}
                      </Link>
                      {opp ? <p className="text-xs text-zinc-600">{opp.angle}</p> : null}
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      <FormatBadge format={opp?.format || s.recommended_format} />
                      {opp?.score != null ? <span className="font-mono text-[11px] text-zinc-500">{Math.round(opp.score * 100)}</span> : null}
                    </div>
                  </div>
                );
              })}
            </div>
          ) : null}
        </Section>
      </div>

      <Section title="Continue" description="In-progress positions and content.">
        {d ? <ContinueBlock d={d} /> : null}
      </Section>

      <Section title="Recent video opportunities" description="Clip candidates and renders from your local video library.">
        {d && d.recent_clips.length === 0 ? (
          <EmptyState title="No clips yet.">Add a video folder under Videos, transcribe a video and run clip discovery.</EmptyState>
        ) : null}
        {d && d.recent_clips.length > 0 ? (
          <div className="rounded-md border border-zinc-200 bg-white">
            {d.recent_clips.map((c) => (
              <div key={c.id} className="flex items-center gap-3 border-b border-zinc-200 px-4 py-2 last:border-b-0">
                <Link href={`/videos/${c.video_id}#clip-${c.id}`} className="min-w-0 flex-1 truncate text-[13px] font-medium text-zinc-900 hover:text-accent-strong">
                  {c.title || "Untitled clip"}
                </Link>
                <span className="truncate text-xs text-zinc-500">{c.video}</span>
                <span className="font-mono text-[11px] text-zinc-500">
                  {fmtDuration(c.start)}–{fmtDuration(c.end)}
                </span>
                <FormatBadge format={c.platform} />
                <StatusBadge status={c.status} />
                <span className="w-8 text-right font-mono text-[11px] text-zinc-500">{Math.round(c.score * 100)}</span>
              </div>
            ))}
          </div>
        ) : null}
      </Section>
      {d ? <p className="text-[11px] text-zinc-400">Dashboard generated {fmtDateTime(d.generated_at)}.</p> : null}
    </div>
  );
}

function ContinueBlock({ d }: { d: Dashboard }) {
  const c = d.continue;
  const empty = c.think_sessions.length === 0 && c.briefs.length === 0 && c.content.length === 0;
  if (empty) return <EmptyState title="Nothing in progress.">Start a Think session or generate content from a story.</EmptyState>;
  return (
    <div className="grid gap-3 md:grid-cols-3">
      <div className="rounded-md border border-zinc-200 bg-white">
        <div className="border-b border-zinc-200 px-3 py-1.5 text-xs font-semibold text-zinc-700">Active think sessions</div>
        {c.think_sessions.length === 0 ? <p className="px-3 py-2 text-xs text-zinc-400">None active.</p> : null}
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
        <div className="border-b border-zinc-200 px-3 py-1.5 text-xs font-semibold text-zinc-700">Draft position briefs</div>
        {c.briefs.length === 0 ? <p className="px-3 py-2 text-xs text-zinc-400">No drafts.</p> : null}
        {c.briefs.map((b) => (
          <Link key={b.id} href={`/think/briefs/${b.id}`} className="block border-b border-zinc-100 px-3 py-2 last:border-b-0 hover:bg-zinc-50">
            <div className="truncate text-[13px] font-medium text-zinc-900">{b.issue}</div>
            <div className="text-xs text-zinc-500">Confidence {Math.round(b.confidence * 100)}%</div>
          </Link>
        ))}
      </div>
      <div className="rounded-md border border-zinc-200 bg-white">
        <div className="border-b border-zinc-200 px-3 py-1.5 text-xs font-semibold text-zinc-700">Content in progress</div>
        {c.content.length === 0 ? <p className="px-3 py-2 text-xs text-zinc-400">Nothing in progress.</p> : null}
        {c.content.map((it) => (
          <Link key={it.id} href={`/content/${it.id}`} className="flex items-center gap-2 border-b border-zinc-100 px-3 py-2 last:border-b-0 hover:bg-zinc-50">
            <span className="min-w-0 flex-1 truncate text-[13px] font-medium text-zinc-900">{it.title}</span>
            <span className="text-[11px] text-zinc-500">{labelFormat(it.format)}</span>
            <StatusBadge status={it.status} />
          </Link>
        ))}
      </div>
    </div>
  );
}
