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

function isContested(s: StoryRowData): boolean {
  return s.principles.some((p) => p.relation === "challenges" || p.relation === "contradicts");
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
  const today = (d?.today ?? []).filter((s) => s.dashboard_action !== "ignored");
  const lead = today[0];
  const rest = today.slice(1, 5);
  const now = new Date();
  const dateLine = `${now.toLocaleDateString("en-GB", { weekday: "long" })} ${now.getDate()} ${now.toLocaleDateString("en-GB", { month: "long" })}`;

  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between gap-4">
        <span className="kicker">{dateLine}</span>
        <span className="meta">
          {d ? `${today.length} ${today.length === 1 ? "story" : "stories"} moved today` : "…"}
        </span>
      </div>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h1 className="text-[clamp(40px,4vw,48px)]">What happened</h1>
        <Button variant="secondary" onClick={runIngest} loading={act.busy} className="mb-1.5">
          Get today&apos;s news
        </Button>
      </div>
      <hr className="rule mb-7 mt-5" />

      <ErrorNotice error={act.error} className="mb-3" />
      {ingestJob ? <JobStatus jobId={ingestJob} label="Getting today's news" className="mb-4" onDone={(j) => j.status === "succeeded" && dash.reload()} /> : null}
      <ErrorNotice error={dash.error} className="mb-3" />

      {dash.loading ? <ListSkeleton rows={3} /> : null}
      {d && today.length === 0 ? <EmptyState title="No stories yet.">Press &ldquo;Get today&apos;s news&rdquo; above to fetch the latest.</EmptyState> : null}

      {lead ? <LeadStory story={lead} /> : null}

      {rest.length > 0 ? (
        <div className="flex flex-col">
          {rest.map((s) => (
            <Link key={s.id} href={`/discover/stories/${s.id}`} className="group grid grid-cols-[1fr_auto] gap-6 border-t border-divider py-4">
              <div className="flex items-baseline gap-2.5">
                {isContested(s) ? <span className="tag tag-highlight shrink-0">Contested</span> : null}
                <div className="min-w-0">
                  <h4 className="mb-1 text-[20px] group-hover:text-accent-strong">{s.title}</h4>
                  {s.summary ? <p className="line-clamp-1 text-sm text-zinc-600">{s.summary}</p> : null}
                </div>
              </div>
              <div className="meta whitespace-nowrap text-right">
                {s.topics[0] ? `${s.topics[0]} · ` : ""}
                {s.article_count} source{s.article_count === 1 ? "" : "s"}
                <br />
                {relTime(s.last_updated)}
              </div>
            </Link>
          ))}
          <div className="border-t border-divider pt-3.5">
            <Link href="/discover" className="font-heading text-sm text-accent hover:underline">
              All {d?.counts.stories_3d ?? today.length} stories today
            </Link>
          </div>
        </div>
      ) : null}

      {d ? (
        <>
          <hr className="rule mb-6 mt-10" />
          <h6 className="mb-4 text-muted">What should I think about?</h6>
          {d.think_about.length === 0 ? <EmptyState title="Nothing pressing right now." /> : null}
          {d.think_about.length > 0 ? (
            <div>
              {d.think_about.slice(0, 3).map((s) => (
                <StoryCard key={s.id} story={s} onChange={updateStory} compact />
              ))}
            </div>
          ) : null}

          <hr className="rule mb-6 mt-9" />
          <h6 className="mb-4 text-muted">What can I create?</h6>
          {d.create.length === 0 ? <EmptyState title="No opportunities scored yet.">They appear once stories are analysed.</EmptyState> : null}
          {d.create.length > 0 ? (
            <div className="flex flex-col">
              {d.create.map((s, i) => {
                const opp = s.content_potential[0];
                const flow = createFlowFor(opp?.format || s.recommended_format);
                return (
                  <div key={s.id} className={`grid grid-cols-[1fr_auto] items-center gap-6 py-3.5 ${i > 0 ? "border-t border-divider" : ""}`}>
                    <div className="min-w-0">
                      <div className="kicker mb-0.5">{labelFormat(opp?.format || s.recommended_format) || "Short"}</div>
                      <Link href={`/discover/stories/${s.id}`} className="font-heading text-base text-ink hover:text-accent-strong">
                        {s.title}
                      </Link>
                      {opp?.angle ? <p className="text-[13px] text-zinc-600">{opp.angle}</p> : null}
                    </div>
                    <Button size="sm" variant="accent" className="shrink-0" onClick={() => router.push(`/create?format=${flow}&source=story&id=${s.id}`)}>
                      Create
                    </Button>
                  </div>
                );
              })}
            </div>
          ) : null}

          <hr className="rule mb-6 mt-9" />
          <h6 className="mb-4 text-muted">What am I working on?</h6>
          <WorkingOn d={d} />
        </>
      ) : null}
    </div>
  );
}

function LeadStory({ story }: { story: StoryRowData }) {
  const router = useRouter();
  const act = useAction();
  const chips = story.principles.slice(0, 3);

  const think = async () => {
    const sess = await act.run(() => api.startThink({ title: story.title, story_id: story.id, ask_first_question: true }));
    if (sess) router.push(`/think/${sess.id}`);
  };

  return (
    <article className={`mb-9 items-start gap-8 ${chips.length ? "grid lg:grid-cols-[1.15fr_minmax(0,1fr)]" : ""}`}>
      <div>
        {story.topics[0] ? <span className="tag">{story.topics[0]}</span> : null}
        <h2 className="mb-3 mt-2.5 text-[clamp(28px,3vw,36px)] [text-wrap:pretty]">
          <Link href={`/discover/stories/${story.id}`} className="hover:text-accent-strong">
            {story.title}
          </Link>
        </h2>
        {story.summary ? <p className="mb-3.5 max-w-[62ch] text-[17px] leading-normal text-ink/80">{story.summary}</p> : null}
        {story.why_it_matters ? (
          <p className="mb-5 max-w-[68ch] text-[15px]">
            <strong className="font-heading">Why it matters — </strong>
            {story.why_it_matters}
          </p>
        ) : null}
        <div className="flex flex-wrap items-center gap-2.5">
          <Button variant="accent" onClick={() => router.push(`/discover/stories/${story.id}`)}>
            Understand
          </Button>
          <Button variant="secondary" onClick={think} loading={act.busy}>
            Think about this
          </Button>
          <Button variant="ghost" onClick={() => router.push(`/create?source=story&id=${story.id}`)}>
            Create from this
          </Button>
        </div>
        <div className="meta mt-4">
          {story.article_count} source{story.article_count === 1 ? "" : "s"}
          {story.primary_sources.length ? ` · ${story.primary_sources.length} primary` : ""}
          {` · moved ${relTime(story.last_updated)}`}
        </div>
        <ErrorNotice error={act.error} className="mt-3" />
      </div>
      {chips.length ? (
        <div className="hidden flex-col gap-2 border-l-2 border-divider pl-6 lg:flex">
          <span className="meta">Touches what you believe</span>
          {chips.map((p) => (
            <Link key={p.id} href={`/think/beliefs/${p.id}`} className="flex min-w-0 items-baseline gap-1.5 hover:opacity-80">
              <span className={`tag ${p.relation === "challenges" || p.relation === "contradicts" ? "tag-highlight" : "tag-accent"} min-w-0 overflow-hidden`}>
                <span className="truncate">{p.title}</span>
              </span>
              <span className="shrink-0 text-[11px] text-muted">{p.relation}</span>
            </Link>
          ))}
        </div>
      ) : null}
    </article>
  );
}

function WorkingOn({ d }: { d: Dashboard }) {
  const c = d.continue;
  const empty = c.think_sessions.length === 0 && c.briefs.length === 0 && c.content.length === 0;
  if (empty)
    return (
      <EmptyState title="Nothing in progress.">
        Think through a story above, or press <span className="font-medium">Create</span> in the sidebar to start something.
      </EmptyState>
    );
  const rows: React.ReactNode[] = [];
  for (const t of c.think_sessions) {
    rows.push(
      <Link key={`t-${t.id}`} href={`/think/${t.id}`} className="flex items-center gap-3.5 border-t border-divider py-3.5 first:border-t-0">
        <span className="tag shrink-0">Idea</span>
        <span className="min-w-0 flex-1 truncate font-heading text-base text-ink">{t.title}</span>
        <span className="text-xs text-muted">
          {t.exchanges} exchange{t.exchanges === 1 ? "" : "s"} · {relTime(t.updated_at)}
        </span>
      </Link>,
    );
  }
  for (const b of c.briefs) {
    rows.push(
      <Link key={`b-${b.id}`} href={`/think/positions/${b.id}`} className="flex items-center gap-3.5 border-t border-divider py-3.5 first:border-t-0">
        <span className="tag tag-accent shrink-0">Position</span>
        <span className="min-w-0 flex-1 truncate font-heading text-base text-ink">{b.issue}</span>
        <span className="text-xs text-muted">Confidence {Math.round(b.confidence * 100)}%</span>
      </Link>,
    );
  }
  for (const it of c.content) {
    rows.push(
      <Link key={`c-${it.id}`} href={`/library/content/${it.id}`} className="flex items-center gap-3.5 border-t border-divider py-3.5 first:border-t-0">
        <span className="tag shrink-0">Draft</span>
        <span className="min-w-0 flex-1 truncate font-heading text-base text-ink">{it.title}</span>
        <span className="text-xs text-muted">{labelFormat(it.format)}</span>
        {it.status ? <StatusBadge status={it.status} /> : null}
      </Link>,
    );
  }
  return <div className="flex flex-col [&>*:first-child]:border-t-0">{rows}</div>;
}
