"use client";

import * as React from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useAction, useApi } from "@/lib/hooks";
import type { Job, PositionBrief, PrincipleListItem, Story } from "@/lib/types";
import { labelFormat } from "@/lib/utils";
import { Button } from "./ui/button";
import { Dialog } from "./ui/dialog";
import { Field, Input, Select, Textarea } from "./ui/input";
import { ErrorNotice } from "./ui/notice";
import { JobStatus } from "./JobStatus";
import { usePrivacy } from "./PrivacyContext";

export interface GenerateDefaults {
  format?: string;
  story_id?: string | null;
  brief_id?: string | null;
  principle_ids?: string[];
  parent_id?: string | null;
  title?: string;
}

export function GenerateContentDialog({ open, onClose, defaults, onCreated }: { open: boolean; onClose: () => void; defaults?: GenerateDefaults; onCreated?: (itemId: string) => void }) {
  const { privacy } = usePrivacy();
  const formats = useApi(() => api.contentFormats(), []);
  const stories = useApi(() => (open ? api.stories({ days: 60, limit: 200 }) : Promise.resolve([] as Story[])), [open]);
  const briefs = useApi(() => (open ? api.briefs() : Promise.resolve([] as PositionBrief[])), [open]);
  const principles = useApi(() => (open ? api.principles() : Promise.resolve([] as PrincipleListItem[])), [open]);
  const [format, setFormat] = React.useState(defaults?.format ?? "youtube");
  const [storyId, setStoryId] = React.useState(defaults?.story_id ?? "");
  const [briefId, setBriefId] = React.useState(defaults?.brief_id ?? "");
  const [pids, setPids] = React.useState<string[]>(defaults?.principle_ids ?? []);
  const [title, setTitle] = React.useState(defaults?.title ?? "");
  const [extra, setExtra] = React.useState("");
  const [jobId, setJobId] = React.useState<string | null>(null);
  const [itemId, setItemId] = React.useState<string | null>(null);
  const act = useAction();

  React.useEffect(() => {
    if (open) {
      setFormat(defaults?.format ?? "youtube");
      setStoryId(defaults?.story_id ?? "");
      setBriefId(defaults?.brief_id ?? "");
      setPids(defaults?.principle_ids ?? []);
      setTitle(defaults?.title ?? "");
      setExtra("");
      setJobId(null);
      setItemId(null);
      act.setError(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const submit = async () => {
    const res = await act.run(() =>
      api.generateContent({ format, story_id: storyId || null, brief_id: briefId || null, principle_ids: pids, parent_id: defaults?.parent_id ?? null, title: title || null, extra_instructions: extra, background: true }),
    );
    if (res?.job) setJobId(res.job.id);
    else if (res?.item) {
      setItemId(res.item.id);
      onCreated?.(res.item.id);
    }
  };

  const onDone = (job: Job) => {
    const id = (job.result?.content_item_id ?? job.result?.item_id ?? job.result?.id) as string | undefined;
    if (job.status === "succeeded" && id) {
      setItemId(id);
      onCreated?.(id);
    }
  };

  const cloud = privacy?.cloud_ai_permitted;
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Generate content"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Close
          </Button>
          <Button variant={cloud ? "warn" : "default"} onClick={submit} loading={act.busy} disabled={!!jobId && !itemId}>
            {cloud ? "Generate (cloud AI may be used)" : "Generate locally"}
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        {cloud ? <p className="rounded border border-warn/50 bg-warn-soft px-2 py-1 text-xs text-[#9a3a1c]">Cloud AI is enabled. Story text, brief and principles may be sent to an external provider.</p> : null}
        <div className="grid grid-cols-2 gap-3">
          <Field label="Format">
            <Select value={format} onChange={(e) => setFormat(e.target.value)} className="w-full">
              {(formats.data?.formats ?? [format]).map((f) => (
                <option key={f} value={f}>
                  {labelFormat(f)}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Title" hint="(optional)">
            <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Leave blank to let the generator propose one" />
          </Field>
        </div>
        <Field label="Story">
          <Select value={storyId} onChange={(e) => setStoryId(e.target.value)} className="w-full">
            <option value="">None</option>
            {(stories.data ?? []).map((s) => (
              <option key={s.id} value={s.id}>
                {s.title}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Position brief">
          <Select value={briefId} onChange={(e) => setBriefId(e.target.value)} className="w-full">
            <option value="">None</option>
            {(briefs.data ?? []).map((b) => (
              <option key={b.id} value={b.id}>
                {b.issue} ({b.status})
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Principles" hint={`${pids.length} selected`}>
          <div className="max-h-36 overflow-y-auto rounded-md border border-zinc-200 p-1.5">
            {(principles.data ?? []).map((p) => (
              <label key={p.id} className="flex cursor-pointer items-center gap-2 rounded px-1 py-0.5 text-xs hover:bg-zinc-50">
                <input type="checkbox" checked={pids.includes(p.id)} onChange={(e) => setPids((prev) => (e.target.checked ? [...prev, p.id] : prev.filter((x) => x !== p.id)))} />
                <span className="truncate">{p.title}</span>
                <span className="ml-auto text-[10px] text-zinc-400">{p.category}</span>
              </label>
            ))}
            {principles.data && principles.data.length === 0 ? <p className="p-1 text-xs text-zinc-400">No principles yet.</p> : null}
          </div>
        </Field>
        <Field label="Extra instructions">
          <Textarea rows={3} value={extra} onChange={(e) => setExtra(e.target.value)} placeholder="Angle, tone, audience, things to avoid…" />
        </Field>
        <ErrorNotice error={act.error} />
        {jobId ? <JobStatus jobId={jobId} label="Generating content" onDone={onDone} /> : null}
        {itemId ? (
          <p className="text-[13px]">
            Created.{" "}
            <Link href={`/content/${itemId}`} className="font-medium text-accent-strong underline-offset-2 hover:underline">
              Open the content item
            </Link>
          </p>
        ) : null}
      </div>
    </Dialog>
  );
}
