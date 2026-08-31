"use client";

import * as React from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useAction, useApi } from "@/lib/hooks";
import type { PositionBrief } from "@/lib/types";
import { fmtDateTime } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Field, Input, Select, Textarea } from "@/components/ui/input";
import { ListSkeleton } from "@/components/ui/skeleton";
import { ErrorNotice, Notice } from "@/components/ui/notice";
import { PageHeader, Panel } from "@/components/ui/section";
import { Confidence, StatusBadge } from "@/components/badges";

type TextKey = "issue" | "position" | "rationale" | "strongest_for" | "strongest_against" | "response";
type ListKey = "factual_assumptions" | "unresolved_questions" | "policy_mechanisms";

const TEXT_SECTIONS: { key: TextKey; label: string; rows: number }[] = [
  { key: "issue", label: "Issue", rows: 2 },
  { key: "position", label: "Position", rows: 3 },
  { key: "rationale", label: "Rationale", rows: 5 },
  { key: "strongest_for", label: "Strongest argument for", rows: 3 },
  { key: "strongest_against", label: "Strongest argument against", rows: 3 },
  { key: "response", label: "Response to the strongest counterargument", rows: 3 },
];
const LIST_SECTIONS: { key: ListKey; label: string }[] = [
  { key: "factual_assumptions", label: "Factual assumptions (need verification)" },
  { key: "unresolved_questions", label: "Unresolved questions" },
  { key: "policy_mechanisms", label: "Policy mechanisms" },
];

export default function BriefPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const brief = useApi(() => api.brief(id), [id]);
  const principles = useApi(() => api.principles(), []);
  const [draft, setDraft] = React.useState<PositionBrief | null>(null);
  const [dirty, setDirty] = React.useState(false);
  const [saved, setSaved] = React.useState(false);
  const [approveOpen, setApproveOpen] = React.useState(false);
  const act = useAction();

  React.useEffect(() => {
    if (brief.data) {
      setDraft(brief.data);
      setDirty(false);
    }
  }, [brief.data]);

  const set = <K extends keyof PositionBrief>(k: K, v: PositionBrief[K]) => {
    setDraft((d) => (d ? { ...d, [k]: v } : d));
    setDirty(true);
    setSaved(false);
  };

  const save = async () => {
    if (!draft) return;
    const r = await act.run(() =>
      api.patchBrief(id, {
        issue: draft.issue,
        position: draft.position,
        rationale: draft.rationale,
        strongest_for: draft.strongest_for,
        strongest_against: draft.strongest_against,
        response: draft.response,
        factual_assumptions: draft.factual_assumptions,
        unresolved_questions: draft.unresolved_questions,
        policy_mechanisms: draft.policy_mechanisms,
        confidence: draft.confidence,
        governing_principle_id: draft.governing_principle_id ?? undefined,
      }),
    );
    if (r) {
      brief.setData({ ...r, markdown: brief.data?.markdown });
      setDirty(false);
      setSaved(true);
    }
  };

  if (brief.loading || !draft) return brief.error ? <ErrorNotice error={brief.error} /> : <ListSkeleton rows={5} />;
  const b = draft;
  const governing = principles.data?.find((p) => p.id === b.governing_principle_id);
  const approvedPrinciple = principles.data?.find((p) => p.id === b.approved_principle_id);

  return (
    <div>
      <div className="mb-1 text-xs text-zinc-500">
        <Link href="/think" className="hover:text-zinc-800">
          Think
        </Link>{" "}
        /{" "}
        {b.think_session_id ? (
          <Link href={`/think/${b.think_session_id}`} className="hover:text-zinc-800">
            session
          </Link>
        ) : (
          "brief"
        )}{" "}
        / my position
      </div>
      <PageHeader
        title={b.issue || "My position"}
        description={
          <span className="flex flex-wrap items-center gap-2">
            <StatusBadge status={b.status} />
            <span>created {fmtDateTime(b.created_at)}</span>
            {b.approved_at ? <span>· approved {fmtDateTime(b.approved_at)}</span> : null}
            {b.story_id ? (
              <Link href={`/discover/stories/${b.story_id}`} className="text-accent-strong hover:underline">
                Open story
              </Link>
            ) : null}
          </span>
        }
        actions={
          <>
            <Button variant="accent" onClick={() => router.push(`/create?source=position&id=${b.id}`)}>Create from this</Button>
            <Button variant="default" onClick={save} loading={act.busy} disabled={!dirty}>
              Save changes
            </Button>
            <Button variant="accent" onClick={() => setApproveOpen(true)} disabled={b.status === "approved"}>
              Adopt this position
            </Button>
          </>
        }
      />
      <ErrorNotice error={act.error} className="mb-3" />
      {saved ? <Notice kind="success" className="mb-3">Brief saved.</Notice> : null}
      {b.status === "approved" && approvedPrinciple ? (
        <Notice kind="success" className="mb-3">
          Now part of what you believe:{" "}
          <Link href={`/think/beliefs/${approvedPrinciple.id}`} className="font-medium underline">
            {approvedPrinciple.title}
          </Link>
          .
        </Notice>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_280px]">
        <div className="space-y-4">
          {TEXT_SECTIONS.map((sec) => (
            <Panel key={sec.key} title={sec.label}>
              <Textarea rows={sec.rows} value={b[sec.key] ?? ""} onChange={(e) => set(sec.key, e.target.value)} />
            </Panel>
          ))}
          {LIST_SECTIONS.map((sec) => (
            <Panel key={sec.key} title={sec.label}>
              <ListEditor items={b[sec.key] ?? []} onChange={(v) => set(sec.key, v)} />
            </Panel>
          ))}
        </div>
        <aside className="space-y-3">
          <Panel title="Linked belief">
            <Select value={b.governing_principle_id ?? ""} onChange={(e) => set("governing_principle_id", e.target.value || null)} className="w-full">
              <option value="">— none selected —</option>
              {(principles.data ?? []).map((p) => (
                <option key={p.id} value={p.id}>
                  {p.title}
                </option>
              ))}
            </Select>
            {b.governing_principle_text ? <p className="mt-2 text-xs text-zinc-600">Interviewer suggestion: “{b.governing_principle_text}”</p> : null}
            {governing ? (
              <Link href={`/think/beliefs/${governing.id}`} className="mt-1 block text-xs text-accent-strong hover:underline">
                Open this belief
              </Link>
            ) : null}
          </Panel>
          <Panel title="Confidence">
            <div className="flex items-center gap-2">
              <input type="range" min={0} max={1} step={0.05} value={b.confidence} onChange={(e) => set("confidence", Number(e.target.value))} className="flex-1" />
              <Confidence value={b.confidence} />
            </div>
          </Panel>
          {b.markdown ? (
            <Panel title="Markdown">
              <Button size="sm" onClick={() => navigator.clipboard?.writeText(b.markdown ?? "")}>
                Copy markdown
              </Button>
              <pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap rounded bg-zinc-50 p-2 font-mono text-[11px] text-zinc-700">{b.markdown}</pre>
            </Panel>
          ) : null}
        </aside>
      </div>

      <ApproveDialog
        open={approveOpen}
        onClose={() => setApproveOpen(false)}
        brief={b}
        onApproved={() => {
          brief.reload();
          principles.reload();
        }}
      />
    </div>
  );
}

function ListEditor({ items, onChange }: { items: string[]; onChange: (v: string[]) => void }) {
  const [draft, setDraft] = React.useState("");
  return (
    <div className="space-y-1.5">
      {items.length === 0 ? <p className="text-xs text-zinc-400">None.</p> : null}
      {items.map((it, i) => (
        <div key={i} className="flex items-start gap-2">
          <Input value={it} onChange={(e) => onChange(items.map((x, j) => (j === i ? e.target.value : x)))} />
          <Button size="sm" variant="ghost" onClick={() => onChange(items.filter((_, j) => j !== i))}>
            Remove
          </Button>
        </div>
      ))}
      <div className="flex items-start gap-2">
        <Input
          value={draft}
          placeholder="Add item"
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && draft.trim()) {
              onChange([...items, draft.trim()]);
              setDraft("");
            }
          }}
        />
        <Button
          size="sm"
          onClick={() => {
            if (draft.trim()) {
              onChange([...items, draft.trim()]);
              setDraft("");
            }
          }}
        >
          Add
        </Button>
      </div>
    </div>
  );
}

function ApproveDialog({ open, onClose, brief, onApproved }: { open: boolean; onClose: () => void; brief: PositionBrief; onApproved: () => void }) {
  const principles = useApi(() => (open ? api.principles() : Promise.resolve([])), [open]);
  const categories = useApi(() => (open ? api.principleCategories() : Promise.resolve([])), [open]);
  const [mode, setMode] = React.useState("auto");
  const [pid, setPid] = React.useState(brief.governing_principle_id ?? "");
  const [title, setTitle] = React.useState(brief.issue);
  const [category, setCategory] = React.useState("");
  const [reason, setReason] = React.useState("");
  const [result, setResult] = React.useState<{ id: string; title: string } | null>(null);
  const act = useAction();

  React.useEffect(() => {
    if (open) {
      setMode("auto");
      setPid(brief.governing_principle_id ?? "");
      setTitle(brief.issue);
      setReason("");
      setResult(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const submit = async () => {
    const r = await act.run(() => api.approveBrief(brief.id, { mode, principle_id: mode === "revise" ? pid || null : null, title: mode === "new" ? title : null, category: mode === "new" ? category || null : null, reason }));
    if (r) {
      setResult({ id: r.principle.id, title: r.principle.title });
      onApproved();
    }
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Adopt this position"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Close
          </Button>
          <Button variant="accent" onClick={submit} loading={act.busy} disabled={!!result || (mode === "revise" && !pid) || (mode === "new" && !title.trim())}>
            Approve
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        <p className="text-xs text-zinc-600">Approving makes this position part of what you believe. Every change is recorded with your reason.</p>
        <Field label="Mode">
          <Select value={mode} onChange={(e) => setMode(e.target.value)} className="w-full">
            <option value="auto">Auto — update the linked belief, or add a new one</option>
            <option value="revise">Update an existing belief</option>
            <option value="new">Add a new belief</option>
          </Select>
        </Field>
        {mode === "revise" ? (
          <Field label="Belief to update">
            <Select value={pid} onChange={(e) => setPid(e.target.value)} className="w-full">
              <option value="">Select…</option>
              {(principles.data ?? []).map((p) => (
                <option key={p.id} value={p.id}>
                  {p.title} ({p.category})
                </option>
              ))}
            </Select>
          </Field>
        ) : null}
        {mode === "new" ? (
          <div className="grid grid-cols-2 gap-3">
            <Field label="Title">
              <Input value={title} onChange={(e) => setTitle(e.target.value)} />
            </Field>
            <Field label="Category">
              <Input list="brief-categories" value={category} onChange={(e) => setCategory(e.target.value)} placeholder="e.g. Taxation" />
              <datalist id="brief-categories">
                {(categories.data ?? []).map((c) => (
                  <option key={c} value={c} />
                ))}
              </datalist>
            </Field>
          </div>
        ) : null}
        <Field label="Reason for change">
          <Textarea rows={3} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Why do you now hold this position?" />
        </Field>
        <ErrorNotice error={act.error} />
        {result ? (
          <Notice kind="success">
            Approved.{" "}
            <Link href={`/think/beliefs/${result.id}`} className="font-medium underline">
              Open “{result.title}”
            </Link>
          </Notice>
        ) : null}
      </div>
    </Dialog>
  );
}
