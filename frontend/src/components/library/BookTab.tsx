"use client";

import * as React from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useAction, useApi } from "@/lib/hooks";
import type { BookChapter, BookDetail, BookNoteWithLinks } from "@/lib/types";
import { humanize, relTime } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/input";
import { ListSkeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorNotice, Notice } from "@/components/ui/notice";
import { PageHeader, Panel, Section } from "@/components/ui/section";
import { BOOK_NOTE_KINDS } from "@/components/SaveToBookDialog";

export function BookTab() {
  const books = useApi(() => api.books(), []);
  const bookId = books.data?.[0]?.id ?? null;
  const book = useApi(() => (bookId ? api.book(bookId) : Promise.resolve(null)), [bookId]);
  if (books.error) return <ErrorNotice error={books.error} />;
  if (!book.data) return <ListSkeleton rows={4} />;
  return <BookWorkspace book={book.data} reload={book.reload} />;
}

function BookWorkspace({ book, reload }: { book: BookDetail; reload: () => void }) {
  const [title, setTitle] = React.useState(book.title);
  const [premise, setPremise] = React.useState(book.premise);
  const [titles, setTitles] = React.useState(book.working_titles.join("\n"));
  const [dirty, setDirty] = React.useState(false);
  const [saved, setSaved] = React.useState(false);
  const act = useAction();
  React.useEffect(() => {
    setTitle(book.title);
    setPremise(book.premise);
    setTitles(book.working_titles.join("\n"));
    setDirty(false);
  }, [book]);
  const save = async () => {
    const r = await act.run(() => api.patchBook(book.id, { title, premise, working_titles: titles.split("\n").map((t) => t.trim()).filter(Boolean) }));
    if (r) {
      setSaved(true);
      reload();
    }
  };
  const grouped = React.useMemo(() => {
    const m = new Map<string, BookNoteWithLinks[]>();
    for (const n of book.notes) m.set(n.kind, [...(m.get(n.kind) ?? []), n]);
    const order = [...BOOK_NOTE_KINDS, ...[...m.keys()].filter((k) => !BOOK_NOTE_KINDS.includes(k))];
    return order.filter((k) => m.has(k)).map((k) => [k, m.get(k)!] as const);
  }, [book.notes]);

  return (
    <div>
      <PageHeader
        title="Book"
        description={`${book.chapters.length} chapters · ${book.notes.length} notes · status ${book.status}`}
        actions={
          <Button variant="default" onClick={save} loading={act.busy} disabled={!dirty}>
            Save project
          </Button>
        }
      />
      <ErrorNotice error={act.error} className="mb-3" />
      {saved ? <Notice kind="success" className="mb-3" onDismiss={() => setSaved(false)}>Project saved.</Notice> : null}
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="min-w-0">
          <Panel title="Project" className="mb-6">
            <div className="grid gap-3 md:grid-cols-2">
              <Field label="Title">
                <Input
                  value={title}
                  onChange={(e) => {
                    setTitle(e.target.value);
                    setDirty(true);
                  }}
                />
              </Field>
              <Field label="Working titles" hint="one per line">
                <Textarea
                  rows={2}
                  value={titles}
                  onChange={(e) => {
                    setTitles(e.target.value);
                    setDirty(true);
                  }}
                />
              </Field>
              <Field label="Premise" className="md:col-span-2">
                <Textarea
                  rows={3}
                  value={premise}
                  onChange={(e) => {
                    setPremise(e.target.value);
                    setDirty(true);
                  }}
                />
              </Field>
            </div>
          </Panel>

          <Section title="Chapters" description="Ordered by chapter number.">
            <Chapters book={book} reload={reload} />
          </Section>

          <Section title="Notes" description="Grouped by kind. Every note links back to where it came from.">
            {book.notes.length === 0 ? <EmptyState title="No notes yet.">Use “Save to Book” on any story, principle, content item or video, or add one on the right.</EmptyState> : null}
            {grouped.map(([kind, notes]) => (
              <div key={kind} className="mb-4">
                <h3 className="mb-1 text-xs font-semibold text-zinc-700">
                  {humanize(kind)} <span className="font-normal text-zinc-400">({notes.length})</span>
                </h3>
                <div className="rounded-md border border-zinc-200 bg-white">
                  {notes.map((n) => (
                    <NoteRow key={n.id} note={n} chapters={book.chapters} reload={reload} />
                  ))}
                </div>
              </div>
            ))}
          </Section>
        </div>
        <aside>
          <AddNote bookId={book.id} chapters={book.chapters} reload={reload} />
        </aside>
      </div>
    </div>
  );
}

function Chapters({ book, reload }: { book: BookDetail; reload: () => void }) {
  const [editing, setEditing] = React.useState<BookChapter | "new" | null>(null);
  const act = useAction();
  const chapters = [...book.chapters].sort((a, b) => a.order - b.order);
  return (
    <div className="space-y-2">
      {chapters.length === 0 ? <p className="text-xs text-zinc-400">No chapters yet.</p> : null}
      {chapters.map((c) =>
        editing !== "new" && editing?.id === c.id ? (
          <ChapterForm
            key={c.id}
            initial={c}
            busy={act.busy}
            onCancel={() => setEditing(null)}
            onSave={async (v) => {
              const r = await act.run(() => api.patchChapter(c.id, v));
              if (r) {
                setEditing(null);
                reload();
              }
            }}
          />
        ) : (
          <div key={c.id} className="flex items-start gap-3 rounded-md border border-zinc-200 bg-white px-3 py-2">
            <span className="w-6 shrink-0 text-right font-mono text-xs text-zinc-400">{c.order}</span>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="text-[13px] font-semibold text-zinc-900">{c.title}</span>
                <Badge variant="outline">{c.status}</Badge>
                <span className="text-[11px] text-zinc-400">{c.note_count ?? 0} notes</span>
              </div>
              {c.summary ? <p className="text-xs text-zinc-600">{c.summary}</p> : null}
            </div>
            <Button size="sm" variant="ghost" onClick={() => setEditing(c)}>
              Edit
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={async () => {
                if (!confirm("Delete chapter? Notes are kept.")) return;
                await act.run(() => api.deleteChapter(c.id));
                reload();
              }}
            >
              Delete
            </Button>
          </div>
        ),
      )}
      {editing === "new" ? (
        <ChapterForm
          busy={act.busy}
          nextOrder={(chapters[chapters.length - 1]?.order ?? 0) + 1}
          onCancel={() => setEditing(null)}
          onSave={async (v) => {
            const r = await act.run(() => api.addChapter(book.id, v));
            if (r) {
              setEditing(null);
              reload();
            }
          }}
        />
      ) : (
        <Button size="sm" onClick={() => setEditing("new")}>
          Add chapter
        </Button>
      )}
      <ErrorNotice error={act.error} />
    </div>
  );
}

function ChapterForm({ initial, nextOrder, busy, onSave, onCancel }: { initial?: BookChapter; nextOrder?: number; busy: boolean; onSave: (v: { title: string; summary: string; order: number; body: string; status: string }) => void; onCancel: () => void }) {
  const [title, setTitle] = React.useState(initial?.title ?? "");
  const [summary, setSummary] = React.useState(initial?.summary ?? "");
  const [order, setOrder] = React.useState(initial?.order ?? nextOrder ?? 1);
  const [body, setBody] = React.useState(initial?.body ?? "");
  const [status, setStatus] = React.useState(initial?.status ?? "idea");
  return (
    <div className="rounded-md border border-dashed border-zinc-300 bg-white p-3">
      <div className="grid gap-2 md:grid-cols-[5rem_1fr_8rem]">
        <Input type="number" value={order} onChange={(e) => setOrder(Number(e.target.value))} />
        <Input placeholder="Chapter title" value={title} onChange={(e) => setTitle(e.target.value)} />
        <Select value={status} onChange={(e) => setStatus(e.target.value)}>
          {["idea", "outlined", "drafting", "drafted", "revised", "final"].map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </Select>
      </div>
      <Input className="mt-2" placeholder="Summary" value={summary} onChange={(e) => setSummary(e.target.value)} />
      <Textarea className="mt-2" rows={4} placeholder="Body / draft" value={body} onChange={(e) => setBody(e.target.value)} />
      <div className="mt-2 flex gap-2">
        <Button size="sm" variant="default" loading={busy} disabled={!title.trim()} onClick={() => onSave({ title, summary, order, body, status })}>
          Save
        </Button>
        <Button size="sm" variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </div>
  );
}

function NoteRow({ note, chapters, reload }: { note: BookNoteWithLinks; chapters: BookChapter[]; reload: () => void }) {
  const act = useAction();
  const assign = async (chapter_id: string) => {
    await act.run(() => api.patchBookNote(note.id, { title: note.title, chapter_id: chapter_id || null }));
    reload();
  };
  return (
    <div className="border-b border-zinc-200 px-3 py-2 last:border-b-0">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[13px] font-medium text-zinc-900">{note.title}</span>
        <span className="text-[11px] text-zinc-400">{relTime(note.created_at)}</span>
        <div className="ml-auto flex items-center gap-1">
          <Select value={note.chapter_id ?? ""} onChange={(e) => assign(e.target.value)} className="h-7 text-xs">
            <option value="">Unassigned</option>
            {[...chapters]
              .sort((a, b) => a.order - b.order)
              .map((c) => (
                <option key={c.id} value={c.id}>
                  {c.order}. {c.title}
                </option>
              ))}
          </Select>
          <Button
            size="sm"
            variant="ghost"
            onClick={async () => {
              await act.run(() => api.deleteBookNote(note.id));
              reload();
            }}
          >
            Delete
          </Button>
        </div>
      </div>
      {note.body ? <p className="mt-1 whitespace-pre-wrap text-[13px] text-zinc-700">{note.body}</p> : null}
      <div className="mt-1 flex flex-wrap gap-3 text-xs text-zinc-500">
        {note.links.story ? (
          <Link href={`/discover/stories/${note.links.story.id}`} className="hover:text-accent-strong">
            Story: {note.links.story.title}
          </Link>
        ) : null}
        {note.links.principle ? (
          <Link href={`/think/beliefs/${note.links.principle.id}`} className="hover:text-accent-strong">
            Principle: {note.links.principle.title}
          </Link>
        ) : null}
        {note.links.content ? (
          <Link href={`/library/content/${note.links.content.id}`} className="hover:text-accent-strong">
            Content: {note.links.content.title}
          </Link>
        ) : null}
        {note.links.video ? (
          <Link href={`/library/videos/${note.links.video.id}`} className="hover:text-accent-strong">
            Video: {note.links.video.filename}
          </Link>
        ) : null}
      </div>
      <ErrorNotice error={act.error} className="mt-1" />
    </div>
  );
}

function AddNote({ bookId, chapters, reload }: { bookId: string; chapters: BookChapter[]; reload: () => void }) {
  const [title, setTitle] = React.useState("");
  const [body, setBody] = React.useState("");
  const [kind, setKind] = React.useState("note");
  const [chapterId, setChapterId] = React.useState("");
  const act = useAction();
  const submit = async () => {
    const r = await act.run(() => api.addBookNote({ title, body, kind, book_id: bookId, chapter_id: chapterId || null }));
    if (r) {
      setTitle("");
      setBody("");
      reload();
    }
  };
  return (
    <Panel title="Add note">
      <div className="space-y-2">
        <Input placeholder="Title" value={title} onChange={(e) => setTitle(e.target.value)} />
        <div className="grid grid-cols-2 gap-2">
          <Select value={kind} onChange={(e) => setKind(e.target.value)}>
            {BOOK_NOTE_KINDS.map((k) => (
              <option key={k} value={k}>
                {humanize(k)}
              </option>
            ))}
          </Select>
          <Select value={chapterId} onChange={(e) => setChapterId(e.target.value)}>
            <option value="">No chapter</option>
            {[...chapters]
              .sort((a, b) => a.order - b.order)
              .map((c) => (
                <option key={c.id} value={c.id}>
                  {c.order}. {c.title}
                </option>
              ))}
          </Select>
        </div>
        <Textarea rows={5} placeholder="Concept, theme, personal story, excerpt…" value={body} onChange={(e) => setBody(e.target.value)} />
        <Button variant="default" onClick={submit} loading={act.busy} disabled={!title.trim()}>
          Add note
        </Button>
        <ErrorNotice error={act.error} />
      </div>
    </Panel>
  );
}
