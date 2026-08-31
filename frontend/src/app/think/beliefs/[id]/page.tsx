"use client";

import * as React from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useAction, useApi } from "@/lib/hooks";
import type { Counterargument, Evidence, PrincipleDetail } from "@/lib/types";
import { fmtDate, fmtDateTime, labelFormat, relTime } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/input";
import { ListSkeleton } from "@/components/ui/skeleton";
import { ErrorNotice, Notice } from "@/components/ui/notice";
import { PageHeader, Panel, Section } from "@/components/ui/section";
import { Confidence, RelationBadge, StatusBadge } from "@/components/badges";
import { NotesBlock } from "@/components/NotesBlock";
import { SaveToBookDialog } from "@/components/SaveToBookDialog";

export default function PrincipleDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const p = useApi(() => api.principle(id), [id]);
  const notes = useApi(() => api.research({ principle_id: id }), [id]);
  const categories = useApi(() => api.principleCategories(), []);
  const [form, setForm] = React.useState({ title: "", category: "", current_position: "", rationale: "", status: "provisional", confidence: 0.6, reason_for_change: "" });
  const [dirty, setDirty] = React.useState(false);
  const [saved, setSaved] = React.useState(false);
  const [book, setBook] = React.useState(false);
  const act = useAction();

  React.useEffect(() => {
    if (p.data) {
      setForm({ title: p.data.title, category: p.data.category, current_position: p.data.current_position, rationale: p.data.rationale, status: p.data.status, confidence: p.data.confidence, reason_for_change: "" });
      setDirty(false);
    }
  }, [p.data]);

  const upd = (k: keyof typeof form, v: string | number) => {
    setForm((f) => ({ ...f, [k]: v }));
    setDirty(true);
    setSaved(false);
  };

  const save = async () => {
    const r = await act.run(() => api.patchPrinciple(id, form));
    if (r) {
      setSaved(true);
      p.reload();
    }
  };

  if (p.loading) return <ListSkeleton rows={5} />;
  if (p.error || !p.data) return <ErrorNotice error={p.error ?? "Not found"} />;
  const d = p.data;

  return (
    <div>
      <div className="mb-1 text-xs text-zinc-500">
        <Link href="/think?tab=beliefs" className="hover:text-zinc-800">
          What I believe
        </Link>{" "}
        / {d.category}
      </div>
      <PageHeader
        title={d.title}
        description={
          <span className="flex items-center gap-2">
            <StatusBadge status={d.status} />
            <Confidence value={d.confidence} />
            <span>· updated {relTime(d.updated_at)}</span>
            <span>· created {fmtDate(d.created_at)}</span>
          </span>
        }
        actions={
          <>
            <Button variant="accent" onClick={() => router.push(`/create?source=belief&id=${id}`)}>Create from this</Button>
            <Button onClick={() => setBook(true)}>Save for book</Button>
            <Button variant="default" onClick={save} loading={act.busy} disabled={!dirty}>
              Save changes
            </Button>
          </>
        }
      />
      <ErrorNotice error={act.error} className="mb-3" />
      {saved ? <Notice kind="success" className="mb-3">Saved. A revision was recorded.</Notice> : null}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_300px]">
        <div className="min-w-0 space-y-4">
          <Panel title="What I believe">
            <div className="grid gap-3">
              <div className="grid grid-cols-2 gap-3">
                <Field label="Title">
                  <Input value={form.title} onChange={(e) => upd("title", e.target.value)} />
                </Field>
                <Field label="Category">
                  <Input list="pcats" value={form.category} onChange={(e) => upd("category", e.target.value)} />
                  <datalist id="pcats">
                    {(categories.data ?? []).map((c) => (
                      <option key={c} value={c} />
                    ))}
                  </datalist>
                </Field>
              </div>
              <Field label="My current position">
                <Textarea rows={4} value={form.current_position} onChange={(e) => upd("current_position", e.target.value)} />
              </Field>
              <Field label="Rationale">
                <Textarea rows={5} value={form.rationale} onChange={(e) => upd("rationale", e.target.value)} />
              </Field>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Status">
                  <Select value={form.status} onChange={(e) => upd("status", e.target.value)} className="w-full">
                    <option value="provisional">Provisional</option>
                    <option value="established">Established</option>
                    <option value="retired">Retired</option>
                  </Select>
                </Field>
                <Field label={`Confidence ${Math.round(form.confidence * 100)}%`}>
                  <input type="range" min={0} max={1} step={0.05} value={form.confidence} onChange={(e) => upd("confidence", Number(e.target.value))} className="mt-2 w-full" />
                </Field>
              </div>
              <Field label="Reason for change" hint="recorded in revision history">
                <Input value={form.reason_for_change} onChange={(e) => upd("reason_for_change", e.target.value)} placeholder="Why are you changing this?" />
              </Field>
            </div>
          </Panel>

          <Section title="Revision history">
            {d.revisions.length === 0 ? <p className="text-xs text-zinc-400">No revisions.</p> : null}
            <ol className="relative ml-2 border-l border-zinc-200 pl-4">
              {[...d.revisions]
                .sort((a, b) => b.created_at.localeCompare(a.created_at))
                .map((r) => (
                  <li key={r.id} className="relative mb-3">
                    <span className="absolute -left-[21px] top-1.5 h-2.5 w-2.5 rounded-full border-2 border-white bg-zinc-400" />
                    <div className="text-[11px] text-zinc-500">
                      {fmtDateTime(r.created_at)}
                      {r.old_status !== r.new_status && r.new_status ? (
                        <span>
                          {" "}
                          · status {r.old_status ?? "—"} → {r.new_status}
                        </span>
                      ) : null}
                    </div>
                    <div className="text-[13px] font-medium text-zinc-800">{r.reason_for_change || "No reason given"}</div>
                    {r.old_position !== r.new_position ? (
                      <div className="mt-1 grid gap-2 text-xs md:grid-cols-2">
                        <div className="rounded border border-zinc-200 bg-zinc-50 p-2 text-zinc-500">
                          <span className="text-[10px] uppercase">Old</span>
                          <p>{r.old_position || "—"}</p>
                        </div>
                        <div className="rounded border border-accent/30 bg-accent-soft/40 p-2 text-zinc-800">
                          <span className="text-[10px] uppercase">New</span>
                          <p>{r.new_position}</p>
                        </div>
                      </div>
                    ) : null}
                  </li>
                ))}
            </ol>
          </Section>

          <Section title="Evidence">
            <EvidenceBlock principle={d} onChange={() => p.reload()} />
          </Section>

          <Section title="Counterarguments">
            <CounterBlock principle={d} onChange={() => p.reload()} />
          </Section>

          <Section title="Research notes">
            <NotesBlock principleId={id} notes={notes.data ?? []} onChange={() => notes.reload()} />
          </Section>
        </div>

        <aside className="space-y-3">
          <Panel title="Linked stories">
            {d.stories.length === 0 ? <p className="text-xs text-zinc-400">No stories linked.</p> : null}
            <ul className="space-y-1.5">
              {d.stories.map((s) => (
                <li key={s.story_id} className="text-[13px]">
                  <Link href={`/discover/stories/${s.story_id}`} className="text-zinc-900 hover:text-accent-strong">
                    {s.title}
                  </Link>
                  <div className="flex items-center gap-1.5 text-[11px] text-zinc-500">
                    <RelationBadge relation={s.relation} /> {Math.round(s.strength * 100)} · {relTime(s.last_updated)}
                  </div>
                </li>
              ))}
            </ul>
          </Panel>
          <Panel title="Drafts using this">
            {d.content.length === 0 ? <p className="text-xs text-zinc-400">No content yet.</p> : null}
            <ul className="space-y-1">
              {d.content.map((c) => (
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
          <Panel title="Positions">
            {d.briefs.length === 0 ? <p className="text-xs text-zinc-400">None.</p> : null}
            <ul className="space-y-1">
              {d.briefs.map((b) => (
                <li key={b.id} className="flex items-center gap-2 text-[13px]">
                  <Link href={`/think/positions/${b.id}`} className="min-w-0 flex-1 truncate text-zinc-900 hover:text-accent-strong">
                    {b.issue}
                  </Link>
                  <StatusBadge status={b.status} />
                </li>
              ))}
            </ul>
          </Panel>
        </aside>
      </div>
      <SaveToBookDialog open={book} onClose={() => setBook(false)} defaults={{ title: d.title, body: d.current_position, principle_id: d.id }} />
    </div>
  );
}

function EvidenceBlock({ principle, onChange }: { principle: PrincipleDetail; onChange: () => void }) {
  const blank: Partial<Evidence> = { source: "", source_type: "secondary", summary: "", url: "", publication_date: "", reliability: "unknown", notes: "" };
  const [f, setF] = React.useState<Partial<Evidence>>(blank);
  const [open, setOpen] = React.useState(false);
  const act = useAction();
  const submit = async () => {
    const r = await act.run(() => api.addEvidence(principle.id, { ...f, publication_date: f.publication_date || null }));
    if (r) {
      setF(blank);
      setOpen(false);
      onChange();
    }
  };
  return (
    <div className="space-y-2">
      {principle.evidence.length === 0 ? <p className="text-xs text-zinc-400">No evidence attached.</p> : null}
      {principle.evidence.map((e) => (
        <div key={e.id} className="rounded-md border border-zinc-200 bg-white px-3 py-2">
          <div className="flex flex-wrap items-center gap-2">
            {e.url ? (
              <a href={e.url} target="_blank" rel="noreferrer" className="text-[13px] font-medium text-zinc-900 hover:text-accent-strong">
                {e.source || e.url}
              </a>
            ) : (
              <span className="text-[13px] font-medium text-zinc-900">{e.source || "Unnamed source"}</span>
            )}
            <Badge variant="outline">{e.source_type}</Badge>
            <Badge variant={e.reliability === "high" ? "success" : e.reliability === "low" ? "warn" : "neutral"}>{e.reliability}</Badge>
            {e.publication_date ? <span className="text-[11px] text-zinc-400">{fmtDate(e.publication_date)}</span> : null}
            <Button
              size="sm"
              variant="ghost"
              className="ml-auto"
              onClick={async () => {
                await act.run(() => api.deleteEvidence(principle.id, e.id));
                onChange();
              }}
            >
              Remove
            </Button>
          </div>
          {e.summary ? <p className="mt-0.5 text-[13px] text-zinc-700">{e.summary}</p> : null}
          {e.notes ? <p className="mt-0.5 text-xs text-zinc-500">{e.notes}</p> : null}
        </div>
      ))}
      {!open ? (
        <Button size="sm" onClick={() => setOpen(true)}>
          Add evidence
        </Button>
      ) : (
        <div className="rounded-md border border-dashed border-zinc-300 bg-white p-3">
          <div className="grid grid-cols-2 gap-2">
            <Input placeholder="Source name" value={f.source ?? ""} onChange={(e) => setF({ ...f, source: e.target.value })} />
            <Input placeholder="URL" value={f.url ?? ""} onChange={(e) => setF({ ...f, url: e.target.value })} />
            <Select value={f.source_type} onChange={(e) => setF({ ...f, source_type: e.target.value })}>
              {["primary", "secondary", "analysis", "data", "other"].map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </Select>
            <Select value={f.reliability} onChange={(e) => setF({ ...f, reliability: e.target.value })}>
              {["unknown", "high", "medium", "low"].map((t) => (
                <option key={t} value={t}>
                  reliability: {t}
                </option>
              ))}
            </Select>
            <Input type="date" value={f.publication_date ?? ""} onChange={(e) => setF({ ...f, publication_date: e.target.value })} />
          </div>
          <Textarea className="mt-2" rows={2} placeholder="Summary of what this evidence shows" value={f.summary ?? ""} onChange={(e) => setF({ ...f, summary: e.target.value })} />
          <Input className="mt-2" placeholder="Notes" value={f.notes ?? ""} onChange={(e) => setF({ ...f, notes: e.target.value })} />
          <div className="mt-2 flex items-center gap-2">
            <Button size="sm" variant="default" onClick={submit} loading={act.busy}>
              Add
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <ErrorNotice error={act.error} />
          </div>
        </div>
      )}
    </div>
  );
}

function CounterBlock({ principle, onChange }: { principle: PrincipleDetail; onChange: () => void }) {
  const [editing, setEditing] = React.useState<string | "new" | null>(null);
  const act = useAction();
  return (
    <div className="space-y-2">
      {principle.counterarguments.length === 0 ? <p className="text-xs text-zinc-400">No counterarguments recorded. The strongest opposing case belongs here.</p> : null}
      {principle.counterarguments.map((c) =>
        editing === c.id ? (
          <CounterForm
            key={c.id}
            initial={c}
            busy={act.busy}
            onCancel={() => setEditing(null)}
            onSave={async (v) => {
              const r = await act.run(() => api.updateCounter(principle.id, c.id, v));
              if (r) {
                setEditing(null);
                onChange();
              }
            }}
          />
        ) : (
          <div key={c.id} className="rounded-md border border-zinc-200 bg-white px-3 py-2">
            <div className="flex items-start gap-2">
              <p className="flex-1 text-[13px] font-medium text-zinc-900">{c.argument}</p>
              <Badge variant={c.strength === "strong" ? "warn" : c.strength === "weak" ? "neutral" : "amber"}>{c.strength}</Badge>
              <Button size="sm" variant="ghost" onClick={() => setEditing(c.id)}>
                Edit
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={async () => {
                  await act.run(() => api.deleteCounter(principle.id, c.id));
                  onChange();
                }}
              >
                Remove
              </Button>
            </div>
            {c.source ? <p className="text-xs text-zinc-500">Source: {c.source}</p> : null}
            {c.response ? (
              <p className="mt-1 text-[13px] text-zinc-700">
                <span className="font-medium text-zinc-800">Response: </span>
                {c.response}
              </p>
            ) : null}
            {c.unresolved_questions?.length ? (
              <ul className="mt-1 list-disc pl-4 text-xs text-zinc-600">
                {c.unresolved_questions.map((q, i) => (
                  <li key={i}>{q}</li>
                ))}
              </ul>
            ) : null}
          </div>
        ),
      )}
      {editing === "new" ? (
        <CounterForm
          busy={act.busy}
          onCancel={() => setEditing(null)}
          onSave={async (v) => {
            const r = await act.run(() => api.addCounter(principle.id, v));
            if (r) {
              setEditing(null);
              onChange();
            }
          }}
        />
      ) : (
        <Button size="sm" onClick={() => setEditing("new")}>
          Add counterargument
        </Button>
      )}
      <ErrorNotice error={act.error} />
    </div>
  );
}

function CounterForm({ initial, onSave, onCancel, busy }: { initial?: Counterargument; onSave: (v: { argument: string; source: string; strength: string; response: string; unresolved_questions: string[] }) => void; onCancel: () => void; busy: boolean }) {
  const [argument, setArgument] = React.useState(initial?.argument ?? "");
  const [source, setSource] = React.useState(initial?.source ?? "");
  const [strength, setStrength] = React.useState(initial?.strength ?? "moderate");
  const [response, setResponse] = React.useState(initial?.response ?? "");
  const [questions, setQuestions] = React.useState((initial?.unresolved_questions ?? []).join("\n"));
  return (
    <div className="rounded-md border border-dashed border-zinc-300 bg-white p-3">
      <Textarea rows={2} placeholder="The strongest version of the opposing argument" value={argument} onChange={(e) => setArgument(e.target.value)} />
      <div className="mt-2 grid grid-cols-2 gap-2">
        <Input placeholder="Source" value={source} onChange={(e) => setSource(e.target.value)} />
        <Select value={strength} onChange={(e) => setStrength(e.target.value)}>
          {["weak", "moderate", "strong"].map((s) => (
            <option key={s} value={s}>
              strength: {s}
            </option>
          ))}
        </Select>
      </div>
      <Textarea className="mt-2" rows={2} placeholder="Your response" value={response} onChange={(e) => setResponse(e.target.value)} />
      <Textarea className="mt-2" rows={2} placeholder="Unresolved questions, one per line" value={questions} onChange={(e) => setQuestions(e.target.value)} />
      <div className="mt-2 flex gap-2">
        <Button size="sm" variant="default" loading={busy} disabled={!argument.trim()} onClick={() => onSave({ argument, source, strength, response, unresolved_questions: questions.split("\n").map((q) => q.trim()).filter(Boolean) })}>
          Save
        </Button>
        <Button size="sm" variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
