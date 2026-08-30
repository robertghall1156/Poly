"use client";

import * as React from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useAction, useApi } from "@/lib/hooks";
import { labelFormat, relTime } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Field, Input, Select } from "@/components/ui/input";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { ListSkeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorNotice } from "@/components/ui/notice";
import { PageHeader } from "@/components/ui/section";
import { FactCheckDot, FormatBadge, StatusBadge } from "@/components/badges";
import { GenerateContentDialog } from "@/components/GenerateContentDialog";

export default function ContentPage() {
  const [status, setStatus] = React.useState("");
  const [format, setFormat] = React.useState("");
  const [rootsOnly, setRootsOnly] = React.useState(false);
  const items = useApi(() => api.content({ status: status || undefined, format: format || undefined, roots_only: rootsOnly || undefined }), [status, format, rootsOnly]);
  const formats = useApi(() => api.contentFormats(), []);
  const [gen, setGen] = React.useState(false);
  const [manual, setManual] = React.useState(false);

  return (
    <div>
      <PageHeader
        title="Content"
        description="Every item by format and status, with fact-check state and lineage back to stories, briefs and principles."
        actions={
          <>
            <Select value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="">Any status</option>
              {(formats.data?.statuses ?? []).map((s) => (
                <option key={s} value={s}>
                  {s.replace(/_/g, " ")}
                </option>
              ))}
            </Select>
            <Select value={format} onChange={(e) => setFormat(e.target.value)}>
              <option value="">Any format</option>
              {(formats.data?.formats ?? []).map((f) => (
                <option key={f} value={f}>
                  {labelFormat(f)}
                </option>
              ))}
            </Select>
            <label className="flex items-center gap-1 text-xs text-zinc-600">
              <input type="checkbox" checked={rootsOnly} onChange={(e) => setRootsOnly(e.target.checked)} /> roots only
            </label>
            <Button onClick={() => setManual(true)}>New</Button>
            <Button variant="default" onClick={() => setGen(true)}>
              Generate
            </Button>
          </>
        }
      />
      <ErrorNotice error={items.error} className="mb-3" />
      {items.loading ? <ListSkeleton /> : null}
      {items.data && items.data.length === 0 ? <EmptyState title="No content items.">Generate a long-form package from a story or brief, or create a manual item.</EmptyState> : null}
      {items.data && items.data.length > 0 ? (
        <Table>
          <THead>
            <tr>
              <TH>Title</TH>
              <TH>Format</TH>
              <TH>Status</TH>
              <TH>Platform</TH>
              <TH>Fact check</TH>
              <TH className="text-right">Unresolved</TH>
              <TH className="text-right">Children</TH>
              <TH>Updated</TH>
            </tr>
          </THead>
          <TBody>
            {items.data.map((c) => (
              <TR key={c.id}>
                <TD className="max-w-md">
                  <Link href={`/content/${c.id}`} className="font-medium text-zinc-900 hover:text-accent-strong">
                    {c.parent_id ? <span className="mr-1 text-zinc-300">└</span> : null}
                    {c.title}
                  </Link>
                  {c.script_preview ? <div className="line-clamp-1 text-xs text-zinc-400">{c.script_preview}</div> : null}
                </TD>
                <TD>
                  <FormatBadge format={c.format} />
                </TD>
                <TD>
                  <StatusBadge status={c.status} />
                </TD>
                <TD className="text-xs text-zinc-600">{c.platform || "—"}</TD>
                <TD className="text-xs text-zinc-600">
                  <FactCheckDot status={c.fact_check_status} className="mr-1.5" />
                  {c.fact_check_status.replace(/_/g, " ")}
                </TD>
                <TD className="text-right tabular-nums">{c.unresolved_claims ? <span className="font-medium text-red-700">{c.unresolved_claims}</span> : <span className="text-zinc-400">0</span>}</TD>
                <TD className="text-right tabular-nums">{c.child_count || <span className="text-zinc-400">0</span>}</TD>
                <TD className="whitespace-nowrap text-xs text-zinc-500">{relTime(c.updated_at)}</TD>
              </TR>
            ))}
          </TBody>
        </Table>
      ) : null}
      <GenerateContentDialog open={gen} onClose={() => setGen(false)} onCreated={() => items.reload()} />
      <ManualDialog open={manual} onClose={() => setManual(false)} formats={formats.data?.formats ?? []} onCreated={() => items.reload()} />
    </div>
  );
}

function ManualDialog({ open, onClose, formats, onCreated }: { open: boolean; onClose: () => void; formats: string[]; onCreated: () => void }) {
  const [title, setTitle] = React.useState("");
  const [format, setFormat] = React.useState("youtube");
  const [platform, setPlatform] = React.useState("");
  const [storyId, setStoryId] = React.useState("");
  const stories = useApi(() => (open ? api.stories({ days: 365, limit: 300 }) : Promise.resolve([])), [open]);
  const act = useAction();
  const submit = async () => {
    const r = await act.run(() => api.createContent({ title, format, platform, story_id: storyId || null }));
    if (r) {
      onCreated();
      onClose();
      setTitle("");
    }
  };
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="New content item"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="default" onClick={submit} loading={act.busy} disabled={!title.trim()}>
            Create
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        <Field label="Title">
          <Input value={title} onChange={(e) => setTitle(e.target.value)} />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Format">
            <Select value={format} onChange={(e) => setFormat(e.target.value)} className="w-full">
              {(formats.length ? formats : ["youtube"]).map((f) => (
                <option key={f} value={f}>
                  {labelFormat(f)}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Platform">
            <Input value={platform} onChange={(e) => setPlatform(e.target.value)} placeholder="youtube, x, substack…" />
          </Field>
        </div>
        <Field label="Story" hint="(optional)">
          <Select value={storyId} onChange={(e) => setStoryId(e.target.value)} className="w-full">
            <option value="">None</option>
            {(stories.data ?? []).map((s) => (
              <option key={s.id} value={s.id}>
                {s.title}
              </option>
            ))}
          </Select>
        </Field>
        <ErrorNotice error={act.error} />
      </div>
    </Dialog>
  );
}
