"use client";

import * as React from "react";
import { api } from "@/lib/api";
import { useAction } from "@/lib/hooks";
import type { ResearchNote } from "@/lib/types";
import { relTime } from "@/lib/utils";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Input, Select, Textarea } from "./ui/input";
import { ErrorNotice } from "./ui/notice";

export function NotesBlock({ storyId, principleId, notes, onChange }: { storyId?: string; principleId?: string; notes: ResearchNote[]; onChange: () => void }) {
  const [title, setTitle] = React.useState("");
  const [body, setBody] = React.useState("");
  const [kind, setKind] = React.useState("note");
  const act = useAction();
  const submit = async () => {
    const r = await act.run(() => api.createResearch({ title, body, kind, story_id: storyId ?? null, principle_id: principleId ?? null }));
    if (r) {
      setTitle("");
      setBody("");
      onChange();
    }
  };
  const remove = async (id: string) => {
    await act.run(() => api.deleteResearch(id));
    onChange();
  };
  return (
    <div className="space-y-3">
      {notes.length === 0 ? <p className="text-xs text-zinc-400">No research notes yet.</p> : null}
      {notes.map((n) => (
        <div key={n.id} className="rounded-md border border-zinc-200 bg-white px-3 py-2">
          <div className="flex items-center gap-2">
            <span className="text-[13px] font-medium text-zinc-900">{n.title}</span>
            <Badge variant="outline">{n.kind}</Badge>
            <span className="text-[11px] text-zinc-400">{relTime(n.updated_at)}</span>
            <Button size="sm" variant="ghost" className="ml-auto" onClick={() => remove(n.id)}>
              Delete
            </Button>
          </div>
          {n.body ? <p className="mt-1 whitespace-pre-wrap text-[13px] text-zinc-700">{n.body}</p> : null}
        </div>
      ))}
      <div className="rounded-md border border-dashed border-zinc-300 bg-white p-3">
        <div className="grid grid-cols-[1fr_auto] gap-2">
          <Input placeholder="Note title" value={title} onChange={(e) => setTitle(e.target.value)} />
          <Select value={kind} onChange={(e) => setKind(e.target.value)}>
            {["note", "brief", "source", "quote", "question"].map((k) => (
              <option key={k} value={k}>
                {k}
              </option>
            ))}
          </Select>
        </div>
        <Textarea className="mt-2" rows={3} placeholder="Body" value={body} onChange={(e) => setBody(e.target.value)} />
        <div className="mt-2 flex items-center gap-2">
          <Button size="sm" variant="default" onClick={submit} loading={act.busy} disabled={!title.trim()}>
            Add note
          </Button>
          <ErrorNotice error={act.error} />
        </div>
      </div>
    </div>
  );
}

