"use client";

import * as React from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useAction, useApi } from "@/lib/hooks";
import { relTime } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Field, Input, Select, Textarea } from "@/components/ui/input";
import { ListSkeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorNotice, Notice } from "@/components/ui/notice";
import { PageHeader } from "@/components/ui/section";
import { Confidence, StatusBadge } from "@/components/badges";

export default function PrinciplesPage() {
  const [category, setCategory] = React.useState("");
  const [status, setStatus] = React.useState("");
  const list = useApi(() => api.principles({ category: category || undefined, status: status || undefined }), [category, status]);
  const categories = useApi(() => api.principleCategories(), []);
  const [add, setAdd] = React.useState(false);
  const [exportOpen, setExportOpen] = React.useState(false);
  const [notice, setNotice] = React.useState<string | null>(null);
  const act = useAction();

  const listData = list.data;
  const grouped = React.useMemo(() => {
    const m = new Map<string, NonNullable<typeof listData>>();
    for (const p of listData ?? []) {
      const arr = m.get(p.category) ?? [];
      arr.push(p);
      m.set(p.category, arr);
    }
    return [...m.entries()].map(([cat, items]) => [cat, items.sort((a, b) => a.sort_order - b.sort_order || a.title.localeCompare(b.title))] as const);
  }, [listData]);

  const doImport = async () => {
    const r = await act.run(() => api.importPrinciples());
    if (r) {
      setNotice(`Imported from knowledge/political_operating_system.md: ${Object.entries(r).map(([k, v]) => `${k} ${v}`).join(", ")}`);
      list.reload();
      categories.reload();
    }
  };

  return (
    <div>
      <PageHeader
        title="Principles"
        description="The Political Operating System. Every position change is recorded with a reason."
        actions={
          <>
            <Select value={category} onChange={(e) => setCategory(e.target.value)}>
              <option value="">All categories</option>
              {(categories.data ?? []).map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </Select>
            <Select value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="">Any status</option>
              <option value="provisional">Provisional</option>
              <option value="established">Established</option>
              <option value="retired">Retired</option>
            </Select>
            <Button onClick={() => setExportOpen(true)}>Export markdown</Button>
            <Button onClick={doImport} loading={act.busy}>
              Import from file
            </Button>
            <Button variant="default" onClick={() => setAdd(true)}>
              Add principle
            </Button>
          </>
        }
      />
      <ErrorNotice error={act.error ?? list.error} className="mb-3" />
      {notice ? (
        <Notice kind="success" className="mb-3" onDismiss={() => setNotice(null)}>
          {notice}
        </Notice>
      ) : null}
      {list.loading ? <ListSkeleton /> : null}
      {list.data && list.data.length === 0 ? <EmptyState title="No principles match.">Add one, or import the markdown file from the knowledge folder.</EmptyState> : null}
      {grouped.map(([cat, items]) => (
        <section key={cat} className="mb-5">
          <h2 className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-zinc-500">
            {cat} <span className="font-normal text-zinc-400">({items.length})</span>
          </h2>
          <div className="rounded-md border border-zinc-200 bg-white">
            {items.map((p) => (
              <div key={p.id} className="flex items-start gap-3 border-b border-zinc-200 px-4 py-2.5 last:border-b-0">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <Link href={`/principles/${p.id}`} className="text-[13.5px] font-semibold text-zinc-900 hover:text-accent-strong">
                      {p.title}
                    </Link>
                    <StatusBadge status={p.status} />
                  </div>
                  <p className="mt-0.5 line-clamp-2 text-[13px] text-zinc-600">{p.current_position}</p>
                </div>
                <div className="flex shrink-0 flex-col items-end gap-1 text-[11px] text-zinc-500">
                  <Confidence value={p.confidence} />
                  <span>
                    {p.evidence_count} evidence · {p.counterargument_count} counter · {p.revision_count} rev · {p.story_count} stories
                  </span>
                  <span>updated {relTime(p.updated_at)}</span>
                </div>
              </div>
            ))}
          </div>
        </section>
      ))}
      <AddPrincipleDialog
        open={add}
        onClose={() => setAdd(false)}
        categories={categories.data ?? []}
        onCreated={() => {
          list.reload();
          categories.reload();
        }}
      />
      <ExportDialog open={exportOpen} onClose={() => setExportOpen(false)} />
    </div>
  );
}

function AddPrincipleDialog({ open, onClose, categories, onCreated }: { open: boolean; onClose: () => void; categories: string[]; onCreated: () => void }) {
  const [title, setTitle] = React.useState("");
  const [category, setCategory] = React.useState("");
  const [position, setPosition] = React.useState("");
  const [rationale, setRationale] = React.useState("");
  const [status, setStatus] = React.useState("provisional");
  const [confidence, setConfidence] = React.useState(0.6);
  const act = useAction();
  const submit = async () => {
    const r = await act.run(() => api.createPrinciple({ title, category, current_position: position, rationale, status, confidence }));
    if (r) {
      onCreated();
      onClose();
      setTitle("");
      setPosition("");
      setRationale("");
    }
  };
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Add principle"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="default" onClick={submit} loading={act.busy} disabled={!title.trim() || !category.trim() || !position.trim()}>
            Create
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <Field label="Title">
            <Input value={title} onChange={(e) => setTitle(e.target.value)} />
          </Field>
          <Field label="Category">
            <Input list="principle-categories" value={category} onChange={(e) => setCategory(e.target.value)} />
            <datalist id="principle-categories">
              {categories.map((c) => (
                <option key={c} value={c} />
              ))}
            </datalist>
          </Field>
        </div>
        <Field label="Current position">
          <Textarea rows={3} value={position} onChange={(e) => setPosition(e.target.value)} />
        </Field>
        <Field label="Rationale">
          <Textarea rows={3} value={rationale} onChange={(e) => setRationale(e.target.value)} />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Status">
            <Select value={status} onChange={(e) => setStatus(e.target.value)} className="w-full">
              <option value="provisional">Provisional</option>
              <option value="established">Established</option>
            </Select>
          </Field>
          <Field label={`Confidence ${Math.round(confidence * 100)}%`}>
            <input type="range" min={0} max={1} step={0.05} value={confidence} onChange={(e) => setConfidence(Number(e.target.value))} className="mt-2 w-full" />
          </Field>
        </div>
        <ErrorNotice error={act.error} />
      </div>
    </Dialog>
  );
}

function ExportDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const md = useApi(() => (open ? api.exportPrinciplesMarkdown() : Promise.resolve(null)), [open]);
  const [copied, setCopied] = React.useState(false);
  const [path, setPath] = React.useState<string | null>(null);
  const act = useAction();
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Principles as markdown"
      wide
      footer={
        <>
          <Button
            onClick={async () => {
              const r = await act.run(() => api.exportPrinciplesFile());
              if (r) setPath(r.path);
            }}
            loading={act.busy}
          >
            Write to knowledge file
          </Button>
          <Button
            variant="default"
            onClick={async () => {
              await navigator.clipboard?.writeText(md.data?.markdown ?? "");
              setCopied(true);
            }}
          >
            {copied ? "Copied" : "Copy"}
          </Button>
        </>
      }
    >
      <ErrorNotice error={md.error ?? act.error} />
      {path ? <Notice kind="success" className="mb-2">Written to {path}</Notice> : null}
      <pre className="max-h-[55vh] overflow-auto whitespace-pre-wrap rounded bg-zinc-50 p-3 font-mono text-[11px] leading-relaxed text-zinc-800">{md.data?.markdown ?? "Loading…"}</pre>
    </Dialog>
  );
}
