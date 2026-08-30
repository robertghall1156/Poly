"use client";

import * as React from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
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
import { BulletList, PageHeader, Panel, Section } from "@/components/ui/section";
import { ClaimTypeBadge, FormatBadge, Relevance, StatusBadge } from "@/components/badges";
import { PrincipleChip } from "@/components/PrincipleChip";
import { JobStatus } from "@/components/JobStatus";
import { GenerateContentDialog } from "@/components/GenerateContentDialog";
import { NotesBlock } from "@/components/NotesBlock";
import { SaveToBookDialog } from "@/components/SaveToBookDialog";

const VERIFICATION = ["unverified", "verified", "disputed", "false", "outdated"];

export default function StoryDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const story = useApi(() => api.story(id), [id]);
  const act = useAction();
  const [gen, setGen] = React.useState(false);
  const [book, setBook] = React.useState(false);
  const [jobId, setJobId] = React.useState<string | null>(null);

  const s = story.data;

  const think = async () => {
    if (!s) return;
    const sess = await act.run(() => api.startThink({ title: s.title, story_id: s.id, ask_first_question: true }));
    if (sess) router.push(`/think/${sess.id}`);
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
        <Link href="/stories" className="hover:text-zinc-800">
          Stories
        </Link>{" "}
        / {s.slug}
      </div>
      <PageHeader
        title={s.title}
        description={
          <span className="flex flex-wrap items-center gap-2">
            <StatusBadge status={s.status} />
            <span>
              Relevance <Relevance value={s.relevance_score} />
            </span>
            <span>· first seen {fmtDateTime(s.first_seen)}</span>
            <span>· updated {relTime(s.last_updated)}</span>
            <span>· {s.article_count} articles</span>
            {s.analysis_source ? <span className="font-mono text-[11px] text-zinc-400">· {s.analysis_source}</span> : null}
            {s.topics.map((t) => (
              <Badge key={t}>{t}</Badge>
            ))}
          </span>
        }
        actions={
          <>
            <Button variant="default" onClick={think} loading={act.busy}>
              Think Through This
            </Button>
            <Button onClick={() => setGen(true)}>Create Content</Button>
            <Button onClick={() => setBook(true)}>Save to Book</Button>
            <Button variant="ghost" onClick={reanalyse}>
              Re-analyse
            </Button>
          </>
        }
      />
      <ErrorNotice error={act.error} className="mb-3" />
      {jobId ? <JobStatus jobId={jobId} label="Story analysis" className="mb-4" onDone={(j) => j.status === "succeeded" && story.reload()} /> : null}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_300px]">
        <div className="min-w-0">
          <Section title="Summary">
            <Panel>
              <p className="text-[13px] text-zinc-800">{s.summary || <span className="text-zinc-400">No summary yet — run Re-analyse.</span>}</p>
              {s.why_it_matters ? (
                <p className="mt-2 text-[13px] text-zinc-700">
                  <span className="font-medium text-zinc-900">Why it matters: </span>
                  {s.why_it_matters}
                </p>
              ) : null}
            </Panel>
          </Section>

          <Section title="Arguments by side">
            <div className="grid gap-3 md:grid-cols-2">
              <Panel title="For">
                {forArgs.length === 0 ? <p className="text-xs text-zinc-400">None recorded.</p> : <BulletList items={forArgs.map((a) => a.argument)} />}
              </Panel>
              <Panel title="Against / other">
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
          </Section>

          <Section title="Claims" description="Major claims with provenance. Verification status is editable.">
            <ClaimsTable claims={s.claims} onChange={(c) => story.setData((p) => (p ? { ...p, claims: p.claims.map((x) => (x.id === c.id ? c : x)) } : p))} />
          </Section>

          <div className="grid gap-3 md:grid-cols-2">
            <Section title="Unresolved questions">
              <Panel>
                <BulletList items={s.unresolved_questions} empty="None listed." />
              </Panel>
            </Section>
            <Section title="Competing interpretations">
              <Panel>
                <BulletList items={s.competing_interpretations} empty="None listed." />
              </Panel>
            </Section>
          </div>

          <Section title="Timeline" description="How the story evolved.">
            <Timeline story={s} />
          </Section>

          <Section title="Articles" description="Deduplicated; syndicated copies are collapsed.">
            <ArticlesList articles={s.articles} />
          </Section>

          <Section title="Research notes">
            <NotesBlock storyId={s.id} notes={s.notes} onChange={() => story.reload()} />
          </Section>
        </div>

        <aside className="space-y-4">
          <Panel title="Principles touched">
            {s.principles.length === 0 ? <p className="text-xs text-zinc-400">No principle links yet.</p> : null}
            <div className="flex flex-col gap-1.5">
              {s.principles.map((p) => (
                <div key={p.id} className="flex items-center gap-2">
                  <PrincipleChip p={p} />
                  <span className="ml-auto font-mono text-[11px] text-zinc-400">{Math.round(p.strength * 100)}</span>
                </div>
              ))}
            </div>
          </Panel>
          <Panel title="Content potential">
            {s.content_potential.length === 0 ? <p className="text-xs text-zinc-400">Not scored.</p> : null}
            <ul className="space-y-1.5">
              {s.content_potential.map((c, i) => (
                <li key={i} className="text-[13px]">
                  <div className="flex items-center gap-2">
                    <FormatBadge format={c.format} />
                    {c.score != null ? <span className="font-mono text-[11px] text-zinc-500">{Math.round(c.score * 100)}</span> : null}
                  </div>
                  <p className="text-zinc-700">{c.angle}</p>
                </li>
              ))}
            </ul>
            {s.recommended_format ? <p className="mt-2 text-xs text-zinc-500">Recommended: {labelFormat(s.recommended_format)}</p> : null}
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
                    p.title || JSON.stringify(p)
                  )}
                </li>
              ))}
            </ul>
          </Panel>
          <Panel title="Think sessions">
            {s.think_sessions.length === 0 ? <p className="text-xs text-zinc-400">None yet.</p> : null}
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
          <Panel title="Content">
            {s.content.length === 0 ? <p className="text-xs text-zinc-400">No content linked.</p> : null}
            <ul className="space-y-1">
              {s.content.map((c) => (
                <li key={c.id} className="flex items-center gap-2 text-[13px]">
                  <Link href={`/content/${c.id}`} className="min-w-0 flex-1 truncate text-zinc-900 hover:text-accent-strong">
                    {c.title}
                  </Link>
                  <span className="text-[11px] text-zinc-500">{labelFormat(c.format)}</span>
                  <StatusBadge status={c.status} />
                </li>
              ))}
            </ul>
          </Panel>
          {s.book_notes.length ? (
            <Panel title="Book notes">
              <ul className="space-y-1 text-[13px]">
                {s.book_notes.map((n) => (
                  <li key={n.id}>
                    <Link href="/book" className="text-zinc-900 hover:text-accent-strong">
                      {n.title}
                    </Link>{" "}
                    <span className="text-[11px] text-zinc-400">{n.kind.replace(/_/g, " ")}</span>
                  </li>
                ))}
              </ul>
            </Panel>
          ) : null}
          {s.keywords.length ? (
            <Panel title="Keywords">
              <p className="text-xs text-zinc-500">{s.keywords.join(", ")}</p>
            </Panel>
          ) : null}
        </aside>
      </div>

      <GenerateContentDialog open={gen} onClose={() => setGen(false)} defaults={{ story_id: s.id, format: s.recommended_format || "youtube", principle_ids: s.principles.slice(0, 4).map((p) => p.id) }} onCreated={() => story.reload()} />
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
  if (claims.length === 0) return <EmptyState title="No claims extracted yet.">Re-analyse the story to extract typed claims with provenance.</EmptyState>;
  return (
    <>
      <ErrorNotice error={err} className="mb-2" />
      <Table>
        <THead>
          <tr>
            <TH>Claim</TH>
            <TH>Type</TH>
            <TH>Supporting passage</TH>
            <TH>Source</TH>
            <TH>Verification</TH>
          </tr>
        </THead>
        <TBody>
          {claims.map((c) => (
            <TR key={c.id}>
              <TD className="max-w-xs text-zinc-900">{c.text}</TD>
              <TD>
                <ClaimTypeBadge type={c.claim_type} />
              </TD>
              <TD className="max-w-sm text-xs text-zinc-600">{c.supporting_passage || "—"}</TD>
              <TD className="max-w-[10rem] text-xs">
                {c.source_url ? (
                  <a href={c.source_url} target="_blank" rel="noreferrer" className="block truncate text-accent-strong hover:underline">
                    {c.publication || c.source_url}
                  </a>
                ) : (
                  c.publication || "—"
                )}
                {c.is_primary_source ? <Badge variant="accent">primary</Badge> : null}
                {c.primary_source_url ? (
                  <a href={c.primary_source_url} target="_blank" rel="noreferrer" className="block truncate text-zinc-500 hover:underline">
                    primary: {c.primary_source_url}
                  </a>
                ) : null}
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
          <div className="text-[11px] text-zinc-500">
            {fmtDateTime(e.occurred_at)} · <span className="uppercase tracking-wide">{e.kind}</span>
          </div>
          <div className="text-[13px] text-zinc-800">{e.description}</div>
          {e.article_id ? (
            <div className="text-xs text-zinc-500">
              Article: {story.articles.find((a) => a.id === e.article_id)?.title ?? e.article_id}
            </div>
          ) : null}
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
            {a.source.reliability_notes ? <span className="text-[11px] text-zinc-500">{a.source.reliability_notes}</span> : null}
          </>
        ) : null}
        {a.topics.map((t) => (
          <span key={t} className="text-[11px] text-zinc-400">
            #{t}
          </span>
        ))}
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
