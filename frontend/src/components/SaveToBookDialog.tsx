"use client";

import * as React from "react";
import { api } from "@/lib/api";
import { useAction } from "@/lib/hooks";
import { Button } from "./ui/button";
import { Dialog } from "./ui/dialog";
import { Field, Input, Select, Textarea } from "./ui/input";
import { ErrorNotice, Notice } from "./ui/notice";

export const BOOK_NOTE_KINDS = ["concept", "theme", "chapter_idea", "personal_story", "research", "excerpt", "note"];

export function SaveToBookDialog({ open, onClose, defaults }: { open: boolean; onClose: () => void; defaults: { title?: string; body?: string; story_id?: string | null; principle_id?: string | null; content_item_id?: string | null; video_id?: string | null } }) {
  const [title, setTitle] = React.useState(defaults.title ?? "");
  const [body, setBody] = React.useState(defaults.body ?? "");
  const [kind, setKind] = React.useState("note");
  const [saved, setSaved] = React.useState(false);
  const act = useAction();
  React.useEffect(() => {
    if (open) {
      setTitle(defaults.title ?? "");
      setBody(defaults.body ?? "");
      setKind("note");
      setSaved(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);
  const submit = async () => {
    const r = await act.run(() => api.addBookNote({ title, body, kind, story_id: defaults.story_id ?? null, principle_id: defaults.principle_id ?? null, content_item_id: defaults.content_item_id ?? null, video_id: defaults.video_id ?? null }));
    if (r) setSaved(true);
  };
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Save to Book"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Close
          </Button>
          <Button variant="default" onClick={submit} loading={act.busy} disabled={!title.trim() || saved}>
            Save note
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        <div className="grid grid-cols-3 gap-3">
          <Field label="Title" className="col-span-2">
            <Input value={title} onChange={(e) => setTitle(e.target.value)} />
          </Field>
          <Field label="Kind">
            <Select value={kind} onChange={(e) => setKind(e.target.value)} className="w-full">
              {BOOK_NOTE_KINDS.map((k) => (
                <option key={k} value={k}>
                  {k.replace(/_/g, " ")}
                </option>
              ))}
            </Select>
          </Field>
        </div>
        <Field label="Note">
          <Textarea rows={5} value={body} onChange={(e) => setBody(e.target.value)} />
        </Field>
        <ErrorNotice error={act.error} />
        {saved ? <Notice kind="success">Saved to the book workspace. Find it under Book.</Notice> : null}
      </div>
    </Dialog>
  );
}
