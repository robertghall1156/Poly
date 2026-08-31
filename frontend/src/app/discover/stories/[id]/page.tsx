"use client";

import * as React from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { ChevronDown, ChevronRight } from "lucide-react";
import { api } from "@/lib/api";
import { useAction, useApi } from "@/lib/hooks";
import type { Article, Claim, StoryDetail } from "@/lib/types";
import { cn, fmtDateTime, humanize, labelFormat, relTime } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/input";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { ListSkeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorNotice } from "@/components/ui/notice";
import { BulletList, Panel } from "@/components/ui/section";
import { ClaimTypeBadge, Relevance, StatusBadge } from "@/components/badges";
import { PrincipleChip } from "@/components/PrincipleChip";
import { JobStatus } from "@/components/JobStatus";
import { NotesBlock } from "@/components/NotesBlock";
import { SaveToBookDialog } from "@/components/SaveToBookDialog";

const VERIFICATION = ["unverified", "verified", "disputed", "false", "outdated"];

function Collapsible({ title, count, defaultOpen, children }: { title: string; count?: number; defaultOpen?: boolean; children: React.ReactNode }) {
  const [open, setOpen] = React.useState(!!defaultOpen);
  return (
    <section className="mb-3 rounded-md border border-zinc-200 bg-white">
      <button type="button" onClick={() => setOpen((o) => !o)} className="flex w-full items-center gap-2 px-3 py-2 text-left">
        {open ? <ChevronDown className="h-3.5 w-3.5 text-zinc-400" /> : <ChevronRight className="h-3.5 w-3.5 text-zinc-400" />}
        <span className="text-[13px] font-semibold text-zinc-800">{title}</span>
        {count != null ? <span className="rounded bg-zinc-100 px-1.5 text-[11px] text-zinc-600">{count}</span> : null}
      </button>
      {open ? <div className="border-t border-zinc-100 px-3 py-3">{children}</div> : null}
    </section>
  );
}

export default function StoryDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const story = useApi(() => api.story(id), [id]);
  const act = useAction();
  const [book, setBook] = React.useState(false);
  const [jobId, setJobId] = React.useState<string | null>(null);

  const s = story.data;

  const think = async () => {
    if (!s) return;
    const sess = await act.run(() => api.startThink({ title: s.title, story_id: s.id, ask_first_question: true }));
    if (sess) router.push(`/think/${sess.id}`);
  };
  const ignore = async () => {
    await act.run(() => api.storyAction(id, "ignored"));
    story.reload();
  };
  const saveForBook = () => {
    void act.run(() => api.storyAction(id, "save_for_book"));
    setBook(true);
  };
  const reanalyse = async () => {
    const j = await act.run(() => api.analyzeStory(id));
    if (j) setJobId(j.id);
  };

  if (story.loading) return <ListSkeleton rows={6} />;
  if (story.error || !s) return <ErrorNotice error={story.error ?? "Story not found"} />;

  const forArgs = s.arguments.filter((a) => a.side === "for" || a.side === "pro");
  const otherArgs = s.arguments.filter((a) => !(a.side === "for" || a.side === "pro"));

  return (
    <div>
      <div className="mb-1 text-xs text-zinc-500">
        <Link href="/discover" className="hover:text-zinc-800">
          Discover
        </Link>{" "}
        / story
      </div>

      <div className="mb-4 rounded-md border border-zinc-200 bg-white p-4">
        <div className="flex flex-wrap items-center gap-2 text-xs text-zinc-500">
          <StatusBadge status={s.status} />
          <span>
            Relevance <Relevance value={s.relevance_score} />
          </span>
          <span>· updated {relTime(s.last_updated)}</span>
          <span>· {s.article_count} articles</span>
          {s.topics.map((t) => (
            <Badge key={t}>{t}</Badge>
          ))}
        </div>
        <h1 className="mt-1.5 text-[clamp(28px,3vw,36px)] [text-wrap:pretty]">{s.title}</h1>
        <p className="mt-1.5 text-[13px] text-zinc-800">{s.summary || <span className="text-zinc-400">No summary yet — press Refresh analysis below.</span>}</p>
        {s.why_it_matters ? (
          <p className="mt-1.5 text-[13px] text-zinc-700">
            <span className="font-medium text-zinc-900">Why it matters: </span>
            {s.why_it_matters}
          </p>
        ) : null}
        {s.principles.length ? (
          <div className="mt-2 flex flex-wrap gap-1">
            {s.principles.map((p) => (
              <PrincipleChip key={p.id} p={p} />
            ))}
          </div>
        ) : null}
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Button variant="default" onClick={think} loading={act.busy}>
            Think this through
          </Button>
          <Button variant="accent" onClick={() => router.push(`/create?source=story&id=${s.id}`)}>
            Create from this
          </Button>
          <Button onClick={saveForBook}>Save for book</Button>
          <Button variant="ghost" onClick={ignore}>
            Ignore
          </Button>
          <Button variant="ghost" onClick={reanalyse}>
            Refresh analysis
          </Button>
        </div>
        <ErrorNotice error={act.error} className="mt-2" />
      </div>
      {jobId ? <JobStatus jobId={jobId} label="Story analysis" className="mb-4" onDone={(j) => j.status === "succeeded" && story.reload()} /> : null}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_300px]">
        <div className="min-w-0">
          <Collapsible title="What's claimed" count={s.claims.length} defaultOpen>
            <ClaimsTable claims={s.claims} onChange={(c) => story.setData((p) => (p ? { ...p, claims: p.claims.map((x) => (x.id === c.id ? c : x)) } : p))} />
          </Collapsible>

          <Collapsible title="Both sides" count={s.arguments.length}>
            <div className="grid gap-3 md:grid-cols-2">
              <Panel title="The case for">
                {forArgs.length === 0 ? <p className="text-xs text-zinc-400">None recorded.</p> : <BulletList items={forArgs.map((a) => a.argument)} />}
              </Panel>
              <Panel title="The case against">
                {otherArgs.length === 0 ? (
                  <p className="text-xs text-zinc-400">None recorded.</p>
                ) : (
                  <ul className="list-disc space-y-0.5 pl-4 text-[13px] text-zinc-800">
                    {otherArgs.map((a, i) => (
                      <li key={i}>
                        {a.side && a.side !== "against" ? <span className="mr-1 text-[11px] uppercase text-zinc-400">{a.side}</span> : null}
                        {a.argument}
                      </li>
                    ))}
                  </ul>
                )}
              </Panel>
            </div>
            {s.unresolved_questions.length || s.competing_interpretations.length ? (
              <div className="mt-3 grid gap-3 md:grid-cols-2">
                <Panel title="Open questions">
                  <BulletList items={s.unresolved_questions} empty="None listed." />
                </Panel>
                <Panel title="Competing readings">
                  <BulletList items={s.competing_interpretations} empty="None listed." />
                </Panel>
              </div>
            ) : null}
          </Collapsible>

          <Collapsible title="Timeline" count={s.events.length}>
            <Timeline story={s} />
          </Collapsible>

          <Collapsible title="Coverage" count={s.articles.length}>
            <ArticlesList articles={s.articles} />
          </Collapsible>

          <Collapsible title="Notes" count={s.notes.length}>
            <NotesBlock storyId={s.id} notes={s.notes} onChange={() => story.reload()} />
          </Collapsible>
        </div>

        <aside className="space-y-4">
          <Panel title="Good fits for this story">
            {s.content_potential.length === 0 ? <p className="text-xs text-zinc-400">Not scored yet.</p> : null}
            <ul className="space-y-1.5">
              {s.content_potential.map((c, i) => (
                <li key={i} className="text-[13px]">
                  <div className="flex items-center gap-2">
                    <Badge variant="outline">{labelFormat(c.format)}</Badge>
                  </div>
                  <p className="text-zinc-700">{c.angle}</p>
                </li>
              ))}
            </ul>
          </Panel>
          <Panel title="Primary sources">
            {s.primary_sources.length === 0 ? <p className="text-xs text-zinc-400">None identified.</p> : null}
            <ul className="space-y-1 text-[13px]">
              {s.primary_sources.map((p, i) => (
                <li key={i} className="truncate">
                  {p.url ? (
                    <a href={p.url} target="_blank" rel="noreferrer" className="text-accent-strong hover:underline">
                      {p.title || p.publication || p.url}
                    </a>
                  ) : (
                    p.title || p.publication || ""
                  )}
                </li>
              ))}
            </ul>
          </Panel>
          <Panel title="My thinking on this">
            {s.think_sessions.length === 0 ? <p className="text-xs text-zinc-400">Not thought through yet.</p> : null}
            <ul className="space-y-1">
              {s.think_sessions.map((t) => (
                <li key={t.id} className="flex items-center gap-2 text-[13px]">
                  <Link href={`/think/${t.id}`} className="min-w-0 flex-1 truncate text-zinc-900 hover:text-accent-strong">
                    {t.title}
                  </Link>
                  <StatusBadge status={t.status} />
                </li>
              ))}
            </ul>
          </Panel>
          <Panel title="Drafts from this story">
            {s.content.length === 0 ? <p className="text-xs text-zinc-400">Nothing created yet.</p> : null}
            <ul className="space-y-1">
              {s.content.map((c) => (
                <li key={c.id} className="flex items-center gap-2 text-[13px]">
                  <Link href={`/library/content/${c.id}`} className="min-w-0 flex-1 truncate text-zinc-900 hover:text-accent-strong">
                    {c.title}
                  </Link>
                  <span className="text-[11px] text-zinc-500">{labelFormat(c.format)}</span>
                  <StatusBadge status={c.status} />
                </li>
              ))}
            </ul>
          </Panel>
          {s.book_notes.length ? (
            <Panel title="Saved for the book">
              <ul className="space-y-1 text-[13px]">
                {s.book_notes.map((n) => (
                  <li key={n.id}>
                    <Link href="/library?tab=book" className="text-zinc-900 hover:text-accent-strong">
                      {n.title}
                    </Link>
                  </li>
                ))}
              </ul>
            </Panel>
          ) : null}
        </aside>
      </div>

      <SaveToBookDialog open={book} onClose={() => setBook(false)} defaults={{ title: s.title, body: s.why_it_matters || s.summary, story_id: s.id }} />
    </div>
  );
}

function ClaimsTable({ claims, onChange }: { claims: Claim[]; onChange: (c: Claim) => void }) {
  const [err, setErr] = React.useState<string | null>(null);
  const update = async (c: Claim, verification_status: string) => {
    try {
      onChange(await api.patchClaim(c.id, { verification_status }));
      setErr(null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  };
  if (claims.length === 0) return <EmptyState title="No claims pulled out yet.">Press &ldquo;Refresh analysis&rdquo; to extract the story&apos;s key claims with their sources.</EmptyState>;
  return (
    <>
      <ErrorNotice error={err} className="mb-2" />
      <Table>
        <THead>
          <tr>
            <TH>Claim</TH>
            <TH>Type</TH>
            <TH>Where it comes from</TH>
            <TH>Checked?</TH>
          </tr>
        </THead>
        <TBody>
          {claims.map((c) => (
            <TR key={c.id}>
              <TD className="max-w-md text-zinc-900">
                {c.text}
                {c.supporting_passage ? <div className="mt-0.5 text-xs text-zinc-500">&ldquo;{c.supporting_passage}&rdquo;</div> : null}
              </TD>
              <TD>
                <ClaimTypeBadge type={c.claim_type} />
              </TD>
              <TD className="max-w-[12rem] text-xs">
                {c.source_url ? (
                  <a href={c.source_url} target="_blank" rel="noreferrer" className="block truncate text-accent-strong hover:underline">
                    {c.publication || c.source_url}
                  </a>
                ) : (
                  c.publication || "—"
                )}
                {c.is_primary_source ? <Badge variant="accent">primary</Badge> : null}
              </TD>
              <TD>
                <Select value={c.verification_status} onChange={(e) => update(c, e.target.value)} className="h-7 text-xs">
                  {[...new Set([...VERIFICATION, c.verification_status])].map((v) => (
                    <option key={v} value={v}>
                      {humanize(v)}
                    </option>
                  ))}
                </Select>
              </TD>
            </TR>
          ))}
        </TBody>
      </Table>
    </>
  );
}

function Timeline({ story }: { story: StoryDetail }) {
  const events = [...story.events].sort((a, b) => a.occurred_at.localeCompare(b.occurred_at));
  if (events.length === 0) return <EmptyState title="No events recorded yet." />;
  return (
    <ol className="relative ml-2 border-l border-zinc-200 pl-4">
      {events.map((e) => (
        <li key={e.id} className="relative mb-3 last:mb-0">
          <span className={cn("absolute -left-[21px] top-1.5 h-2.5 w-2.5 rounded-full border-2 border-white", e.kind === "user" ? "bg-warn" : e.kind === "created" || e.kind === "new" ? "bg-accent" : "bg-zinc-400")} />
          <div className="text-[11px] text-zinc-500">{fmtDateTime(e.occurred_at)}</div>
          <div className="text-[13px] text-zinc-800">{e.description}</div>
        </li>
      ))}
    </ol>
  );
}

function ArticlesList({ articles }: { articles: Article[] }) {
  const [showDupes, setShowDupes] = React.useState<Record<string, boolean>>({});
  const primaries = articles.filter((a) => !a.duplicate_of_id);
  const dupesOf = (id: string) => articles.filter((a) => a.duplicate_of_id === id);
  const orphanDupes = articles.filter((a) => a.duplicate_of_id && !articles.some((p) => p.id === a.duplicate_of_id));
  if (articles.length === 0) return <EmptyState title="No articles." />;
  const row = (a: Article, dup?: boolean) => (
    <div key={a.id} className={cn("border-b border-zinc-200 px-3 py-2 last:border-b-0", dup && "bg-zinc-50 pl-8")}>
      <div className="flex flex-wrap items-baseline gap-x-2">
        <a href={a.url} target="_blank" rel="noreferrer" className="text-[13px] font-medium text-zinc-900 hover:text-accent-strong">
          {a.title}
        </a>
        <span className="text-xs text-zinc-500">{a.publication}</span>
        {a.author ? <span className="text-xs text-zinc-400">by {a.author}</span> : null}
        <span className="text-xs text-zinc-400">{fmtDateTime(a.published_at ?? a.fetched_at)}</span>
      </div>
      {a.summary ? <p className="mt-0.5 text-xs text-zinc-600">{a.summary}</p> : null}
      <div className="mt-1 flex flex-wrap items-center gap-1.5">
        {a.source ? (
          <>
            <Badge variant="outline">{humanize(a.source.source_type)}</Badge>
            {a.source.is_primary ? <Badge variant="accent">primary source</Badge> : null}
            {a.source.ideology ? <Badge variant="neutral">{a.source.ideology}</Badge> : null}
          </>
        ) : null}
      </div>
    </div>
  );
  return (
    <div className="rounded-md border border-zinc-200 bg-white">
      {primaries.map((a) => {
        const d = dupesOf(a.id);
        return (
          <React.Fragment key={a.id}>
            {row(a)}
            {d.length ? (
              <div className="border-b border-zinc-200 bg-zinc-50 px-3 py-1 last:border-b-0">
                <button type="button" className="text-xs text-accent-strong hover:underline" onClick={() => setShowDupes((s) => ({ ...s, [a.id]: !s[a.id] }))}>
                  {showDupes[a.id] ? "Hide" : "Show"} {d.length} syndicated cop{d.length === 1 ? "y" : "ies"}
                </button>
              </div>
            ) : null}
            {showDupes[a.id] ? d.map((x) => row(x, true)) : null}
          </React.Fragment>
        );
      })}
      {orphanDupes.map((a) => row(a, true))}
    </div>
  );
}
