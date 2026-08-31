"use client";

import * as React from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useAction, useApi } from "@/lib/hooks";
import type { Feed, ResearchNote, Source } from "@/lib/types";
import { relTime } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { Tabs } from "@/components/ui/tabs";
import { ListSkeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorNotice } from "@/components/ui/notice";
import { JobStatus } from "@/components/JobStatus";

export function ResearchSection() {
  const [tab, setTab] = React.useState("notes");
  return (
    <div>
      <p className="mb-3 text-[13px] text-zinc-500">Research notes, the reliability of each publication, and the news sources Poly reads.</p>
      <Tabs
        className="mb-4"
        value={tab}
        onChange={setTab}
        tabs={[
          { id: "notes", label: "Notes" },
          { id: "sources", label: "Publications" },
          { id: "feeds", label: "News sources" },
        ]}
      />
      {tab === "notes" ? <NotesTab /> : tab === "sources" ? <SourcesTab /> : <FeedsTab />}
    </div>
  );
}

function NotesTab() {
  const [storyId, setStoryId] = React.useState("");
  const [principleId, setPrincipleId] = React.useState("");
  const notes = useApi(() => api.research({ story_id: storyId || undefined, principle_id: principleId || undefined }), [storyId, principleId]);
  const stories = useApi(() => api.stories({ days: 365, limit: 500 }), []);
  const principles = useApi(() => api.principles(), []);
  const [editing, setEditing] = React.useState<ResearchNote | "new" | null>(null);
  const act = useAction();
  const sTitle = (id: string | null) => stories.data?.find((s) => s.id === id)?.title;
  const pTitle = (id: string | null) => principles.data?.find((p) => p.id === id)?.title;

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Select value={storyId} onChange={(e) => setStoryId(e.target.value)} className="max-w-xs">
          <option value="">Any story</option>
          {(stories.data ?? []).map((s) => (
            <option key={s.id} value={s.id}>
              {s.title}
            </option>
          ))}
        </Select>
        <Select value={principleId} onChange={(e) => setPrincipleId(e.target.value)} className="max-w-xs">
          <option value="">Any belief</option>
          {(principles.data ?? []).map((p) => (
            <option key={p.id} value={p.id}>
              {p.title}
            </option>
          ))}
        </Select>
        <Button variant="default" className="ml-auto" onClick={() => setEditing("new")}>
          New note
        </Button>
      </div>
      <ErrorNotice error={notes.error ?? act.error} className="mb-3" />
      {editing ? (
        <NoteForm
          initial={editing === "new" ? undefined : editing}
          stories={stories.data ?? []}
          principles={principles.data ?? []}
          busy={act.busy}
          onCancel={() => setEditing(null)}
          onSave={async (v) => {
            const r = editing === "new" ? await act.run(() => api.createResearch(v)) : await act.run(() => api.updateResearch(editing.id, { ...v, content_item_id: editing.content_item_id }));
            if (r) {
              setEditing(null);
              notes.reload();
            }
          }}
        />
      ) : null}
      {notes.loading ? <ListSkeleton /> : null}
      {notes.data && notes.data.length === 0 ? <EmptyState title="No research notes.">Create one here, or from a story or principle page.</EmptyState> : null}
      <div className="space-y-2">
        {(notes.data ?? []).map((n) => (
          <div key={n.id} className="rounded-md border border-zinc-200 bg-white px-3 py-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[13px] font-semibold text-zinc-900">{n.title}</span>
              <Badge variant="outline">{n.kind}</Badge>
              {n.tags.map((t) => (
                <Badge key={t}>{t}</Badge>
              ))}
              <span className="text-[11px] text-zinc-400">{relTime(n.updated_at)}</span>
              <div className="ml-auto flex gap-1">
                <Link href={`/create?source=research&id=${n.id}`} className="inline-flex h-7 items-center rounded-md border border-zinc-300 bg-white px-2.5 text-xs font-medium text-zinc-800 hover:bg-zinc-50">
                  Create from this
                </Link>
                <Button size="sm" variant="ghost" onClick={() => setEditing(n)}>
                  Edit
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={async () => {
                    await act.run(() => api.deleteResearch(n.id));
                    notes.reload();
                  }}
                >
                  Delete
                </Button>
              </div>
            </div>
            {n.body ? <p className="mt-1 whitespace-pre-wrap text-[13px] text-zinc-700">{n.body}</p> : null}
            <div className="mt-1 flex flex-wrap gap-3 text-xs text-zinc-500">
              {n.story_id ? (
                <Link href={`/discover/stories/${n.story_id}`} className="hover:text-accent-strong">
                  Story: {sTitle(n.story_id) ?? n.story_id.slice(0, 8)}
                </Link>
              ) : null}
              {n.principle_id ? (
                <Link href={`/think/beliefs/${n.principle_id}`} className="hover:text-accent-strong">
                  Belief: {pTitle(n.principle_id) ?? n.principle_id.slice(0, 8)}
                </Link>
              ) : null}
              {n.content_item_id ? (
                <Link href={`/library/content/${n.content_item_id}`} className="hover:text-accent-strong">
                  Draft
                </Link>
              ) : null}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function NoteForm({ initial, stories, principles, busy, onSave, onCancel }: { initial?: ResearchNote; stories: { id: string; title: string }[]; principles: { id: string; title: string }[]; busy: boolean; onSave: (v: { title: string; body: string; kind: string; tags: string[]; story_id: string | null; principle_id: string | null }) => void; onCancel: () => void }) {
  const [title, setTitle] = React.useState(initial?.title ?? "");
  const [body, setBody] = React.useState(initial?.body ?? "");
  const [kind, setKind] = React.useState(initial?.kind ?? "note");
  const [tags, setTags] = React.useState((initial?.tags ?? []).join(", "));
  const [storyId, setStoryId] = React.useState(initial?.story_id ?? "");
  const [principleId, setPrincipleId] = React.useState(initial?.principle_id ?? "");
  return (
    <div className="mb-4 rounded-md border border-zinc-300 bg-white p-3">
      <div className="grid gap-2 md:grid-cols-4">
        <Field label="Title" className="md:col-span-2">
          <Input value={title} onChange={(e) => setTitle(e.target.value)} />
        </Field>
        <Field label="Kind">
          <Select value={kind} onChange={(e) => setKind(e.target.value)} className="w-full">
            {["note", "brief", "source", "quote", "question"].map((k) => (
              <option key={k} value={k}>
                {k}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Tags" hint="comma separated">
          <Input value={tags} onChange={(e) => setTags(e.target.value)} />
        </Field>
        <Field label="Story" className="md:col-span-2">
          <Select value={storyId} onChange={(e) => setStoryId(e.target.value)} className="w-full">
            <option value="">None</option>
            {stories.map((s) => (
              <option key={s.id} value={s.id}>
                {s.title}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Belief" className="md:col-span-2">
          <Select value={principleId} onChange={(e) => setPrincipleId(e.target.value)} className="w-full">
            <option value="">None</option>
            {principles.map((p) => (
              <option key={p.id} value={p.id}>
                {p.title}
              </option>
            ))}
          </Select>
        </Field>
      </div>
      <Textarea className="mt-2" rows={5} value={body} onChange={(e) => setBody(e.target.value)} placeholder="Body" />
      <div className="mt-2 flex gap-2">
        <Button variant="default" loading={busy} disabled={!title.trim()} onClick={() => onSave({ title, body, kind, tags: tags.split(",").map((t) => t.trim()).filter(Boolean), story_id: storyId || null, principle_id: principleId || null })}>
          Save
        </Button>
        <Button variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </div>
  );
}

const SOURCE_TYPES = ["wire", "newspaper", "broadcast", "magazine", "government", "think_tank", "academic", "blog", "aggregator", "other"];

function SourcesTab() {
  const sources = useApi(() => api.sources(), []);
  const [err, setErr] = React.useState<string | null>(null);
  const [q, setQ] = React.useState("");
  const update = async (s: Source, body: Partial<Source>) => {
    try {
      const r = await api.patchSource(s.id, body);
      sources.setData((prev) => (prev ? prev.map((x) => (x.id === s.id ? r : x)) : prev));
      setErr(null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  };
  const rows = (sources.data ?? []).filter((s) => !q || s.name.toLowerCase().includes(q.toLowerCase()) || s.domain.includes(q.toLowerCase()));
  return (
    <div>
      <div className="mb-3 flex items-center gap-2">
        <Input placeholder="Filter sources" value={q} onChange={(e) => setQ(e.target.value)} className="max-w-xs" />
        <span className="text-xs text-zinc-500">{rows.length} sources</span>
      </div>
      <ErrorNotice error={sources.error ?? err} className="mb-3" />
      {sources.loading ? <ListSkeleton /> : null}
      {sources.data && sources.data.length === 0 ? <EmptyState title="No sources yet.">Sources are created automatically as articles are ingested.</EmptyState> : null}
      {rows.length ? (
        <Table>
          <THead>
            <tr>
              <TH>Source</TH>
              <TH>Type</TH>
              <TH>Primary</TH>
              <TH>Ideology</TH>
              <TH>Reliability notes</TH>
            </tr>
          </THead>
          <TBody>
            {rows.map((s) => (
              <TR key={s.id}>
                <TD>
                  <div className="font-medium text-zinc-900">{s.name}</div>
                  <div className="text-xs text-zinc-500">{s.domain}</div>
                </TD>
                <TD>
                  <Select value={s.source_type} onChange={(e) => update(s, { source_type: e.target.value })} className="h-7 text-xs">
                    {[...new Set([...SOURCE_TYPES, s.source_type])].map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </Select>
                </TD>
                <TD>
                  <Switch checked={s.is_primary} onChange={(v) => update(s, { is_primary: v })} />
                </TD>
                <TD>
                  <Input defaultValue={s.ideology ?? ""} placeholder="e.g. center-left" className="h-7 w-32 text-xs" onBlur={(e) => e.target.value !== (s.ideology ?? "") && update(s, { ideology: e.target.value })} />
                </TD>
                <TD>
                  <Input defaultValue={s.reliability_notes} placeholder="Notes on reliability" className="h-7 text-xs" onBlur={(e) => e.target.value !== s.reliability_notes && update(s, { reliability_notes: e.target.value })} />
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      ) : null}
    </div>
  );
}

function FeedsTab() {
  const feeds = useApi(() => api.feeds(), []);
  const status = useApi(() => api.ingestStatus(), []);
  const [jobs, setJobs] = React.useState<Record<string, string>>({});
  const [ingestJob, setIngestJob] = React.useState<string | null>(null);
  const [form, setForm] = React.useState({ name: "", url: "", category: "general", provider: "rss" });
  const act = useAction();
  const [err, setErr] = React.useState<string | null>(null);

  const toggle = async (f: Feed, enabled: boolean) => {
    try {
      const r = await api.patchFeed(f.id, { enabled });
      feeds.setData((prev) => (prev ? prev.map((x) => (x.id === f.id ? { ...x, ...r } : x)) : prev));
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  };
  const fetchNow = async (f: Feed) => {
    const j = await act.run(() => api.fetchFeed(f.id));
    if (j) setJobs((m) => ({ ...m, [f.id]: j.id }));
  };
  const add = async () => {
    const r = await act.run(() => api.addFeed(form));
    if (r) {
      setForm({ name: "", url: "", category: "general", provider: "rss" });
      feeds.reload();
    }
  };
  const li = status.data?.last_ingest;
  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-3 rounded-md border border-zinc-200 bg-white px-3 py-2 text-xs text-zinc-600">
        <span>
          {status.data ? `${status.data.story_count} stories · ${status.data.article_count} articles` : "…"}
        </span>
        {li?.at ? (
          <span>
            Last ingest {relTime(li.at)}: {li.inserted} new, {li.duplicates} dupes, {li.feeds_ok}/{li.feeds} feeds ok
          </span>
        ) : (
          <span>No ingest yet.</span>
        )}
        <span className="flex items-center gap-1">
          Providers:
          {(status.data?.providers ?? []).map((p) => (
            <Badge key={p.name} variant={p.available ? "success" : "neutral"} title={p.requires_key ? "requires API key" : ""}>
              {p.name}
            </Badge>
          ))}
        </span>
        <Button
          variant="default"
          size="sm"
          className="ml-auto"
          loading={act.busy}
          onClick={async () => {
            const j = await act.run(() => api.runIngest());
            if (j) setIngestJob(j.id);
          }}
        >
          Run full ingest
        </Button>
      </div>
      {ingestJob ? (
        <JobStatus
          jobId={ingestJob}
          label="Full ingest"
          className="mb-3"
          onDone={() => {
            feeds.reload();
            status.reload();
          }}
        />
      ) : null}
      <ErrorNotice error={feeds.error ?? act.error ?? err} className="mb-3" />
      <div className="mb-3 grid gap-2 rounded-md border border-dashed border-zinc-300 bg-white p-3 md:grid-cols-[1fr_2fr_auto_auto_auto]">
        <Input placeholder="Feed name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        <Input placeholder="https://…/rss.xml" value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} />
        <Input placeholder="category" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} className="w-32" />
        <Select value={form.provider} onChange={(e) => setForm({ ...form, provider: e.target.value })}>
          <option value="rss">rss</option>
          <option value="google_news_rss">google_news_rss</option>
        </Select>
        <Button variant="default" onClick={add} disabled={!form.name || !form.url} loading={act.busy}>
          Add feed
        </Button>
      </div>
      {feeds.loading ? <ListSkeleton /> : null}
      {feeds.data ? (
        <Table>
          <THead>
            <tr>
              <TH>On</TH>
              <TH>Feed</TH>
              <TH>Category</TH>
              <TH className="text-right">Articles</TH>
              <TH>Last fetched</TH>
              <TH>Last error</TH>
              <TH></TH>
            </tr>
          </THead>
          <TBody>
            {feeds.data.map((f) => (
              <TR key={f.id} className={!f.enabled ? "opacity-60" : ""}>
                <TD>
                  <Switch checked={f.enabled} onChange={(v) => toggle(f, v)} />
                </TD>
                <TD className="max-w-sm">
                  <div className="font-medium text-zinc-900">{f.name}</div>
                  <a href={f.url} target="_blank" rel="noreferrer" className="block truncate text-xs text-zinc-500 hover:text-accent-strong">
                    {f.url}
                  </a>
                  {jobs[f.id] ? <JobStatus jobId={jobs[f.id]} label="Fetch" compact className="mt-1" onDone={() => feeds.reload()} /> : null}
                </TD>
                <TD>
                  <Badge>{f.category}</Badge>
                </TD>
                <TD className="text-right tabular-nums">{f.article_count}</TD>
                <TD className="whitespace-nowrap text-xs text-zinc-500">{f.last_fetched_at ? relTime(f.last_fetched_at) : "never"}</TD>
                <TD className="max-w-xs text-xs text-danger">{f.last_error ? <span className="line-clamp-2" title={f.last_error}>{f.last_error}</span> : <span className="text-zinc-400">—</span>}</TD>
                <TD className="whitespace-nowrap">
                  <Button size="sm" onClick={() => fetchNow(f)}>
                    Fetch now
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={async () => {
                      await act.run(() => api.deleteFeed(f.id));
                      feeds.reload();
                    }}
                  >
                    Remove
                  </Button>
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      ) : null}
    </div>
  );
}
