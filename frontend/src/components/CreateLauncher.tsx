"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Clapperboard, FileText, Images, Laugh, MessageSquareText, Mic, MonitorPlay, Search, Tv, Upload } from "lucide-react";
import { api } from "@/lib/api";
import { useAction } from "@/lib/hooks";
import { Button } from "./ui/button";
import { Dialog } from "./ui/dialog";
import { Field, Input, Textarea } from "./ui/input";
import { ErrorNotice } from "./ui/notice";

const OPTIONS: { label: string; hint: string; icon: typeof FileText; href?: string; action?: "think" | "research" }[] = [
  { label: "Make a Short", hint: "15–60s vertical video", icon: MonitorPlay, href: "/create?format=short" },
  { label: "Make a Faceless Video", hint: "Animated text video", icon: Clapperboard, href: "/create?format=faceless" },
  { label: "Make a Meme", hint: "Three concepts to pick from", icon: Laugh, href: "/create?format=meme" },
  { label: "Make a Social Post", hint: "Short written post", icon: MessageSquareText, href: "/create?format=post" },
  { label: "Make a Carousel", hint: "Swipeable slide set", icon: Images, href: "/create?format=carousel" },
  { label: "Make a YouTube Video", hint: "Full script and outline", icon: Tv, href: "/create?format=youtube" },
  { label: "Make a Podcast", hint: "Episode outline and notes", icon: Mic, href: "/create?format=podcast" },
  { label: "Upload a Video", hint: "Add your own footage", icon: Upload, href: "/library?tab=videos" },
  { label: "Think Through an Issue", hint: "Work out where you stand", icon: MessageSquareText, action: "think" },
  { label: "Research Something", hint: "Save a research note", icon: Search, action: "research" },
];

export function CreateLauncher({ open, onClose }: { open: boolean; onClose: () => void }) {
  const router = useRouter();
  const [mode, setMode] = React.useState<"menu" | "think" | "research">("menu");
  React.useEffect(() => {
    if (open) setMode("menu");
  }, [open]);

  const pick = (o: (typeof OPTIONS)[number]) => {
    if (o.href) {
      onClose();
      router.push(o.href);
    } else if (o.action) {
      setMode(o.action);
    }
  };

  if (mode === "think") return <NewThinkDialog open={open} onClose={onClose} />;
  if (mode === "research") return <NewResearchDialog open={open} onClose={onClose} />;

  return (
    <Dialog open={open} onClose={onClose} title="What do you want to make?" wide>
      <div className="grid gap-2 sm:grid-cols-2">
        {OPTIONS.map((o) => {
          const Icon = o.icon;
          return (
            <button
              key={o.label}
              type="button"
              onClick={() => pick(o)}
              className="flex items-center gap-3 rounded-md border border-zinc-200 bg-white px-3 py-2.5 text-left transition-colors hover:border-accent hover:bg-accent-soft"
            >
              <Icon className="h-4 w-4 shrink-0 text-accent-strong" />
              <span className="min-w-0">
                <span className="block text-[13px] font-medium text-zinc-900">{o.label}</span>
                <span className="block truncate text-xs text-zinc-500">{o.hint}</span>
              </span>
            </button>
          );
        })}
      </div>
    </Dialog>
  );
}

export function NewThinkDialog({ open, onClose, defaults }: { open: boolean; onClose: () => void; defaults?: { title?: string; story_id?: string | null } }) {
  const router = useRouter();
  const [title, setTitle] = React.useState(defaults?.title ?? "");
  const [question, setQuestion] = React.useState("");
  const act = useAction();
  React.useEffect(() => {
    if (open) {
      setTitle(defaults?.title ?? "");
      setQuestion("");
      act.setError(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);
  const submit = async () => {
    const s = await act.run(() => api.startThink({ title: title.trim(), question, story_id: defaults?.story_id ?? null, ask_first_question: true }));
    if (s) {
      onClose();
      router.push(`/think/${s.id}`);
    }
  };
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Think through an issue"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="default" onClick={submit} loading={act.busy} disabled={!title.trim()}>
            Start thinking
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        <Field label="What's the issue?">
          <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Should political ads be limited?" autoFocus />
        </Field>
        <Field label="Your starting question" hint="(optional)">
          <Textarea rows={2} value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="Frame it in your own words" />
        </Field>
        <ErrorNotice error={act.error} />
        <p className="text-xs text-zinc-500">You&apos;ll be asked one question at a time, including the strongest case against your view, before you settle on a position.</p>
      </div>
    </Dialog>
  );
}

export function NewResearchDialog({ open, onClose, defaults }: { open: boolean; onClose: () => void; defaults?: { story_id?: string | null; principle_id?: string | null } }) {
  const router = useRouter();
  const [title, setTitle] = React.useState("");
  const [body, setBody] = React.useState("");
  const act = useAction();
  React.useEffect(() => {
    if (open) {
      setTitle("");
      setBody("");
      act.setError(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);
  const submit = async () => {
    const r = await act.run(() => api.createResearch({ title: title.trim(), body, story_id: defaults?.story_id ?? null, principle_id: defaults?.principle_id ?? null }));
    if (r) {
      onClose();
      router.push("/discover?tab=research");
    }
  };
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Research something"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="default" onClick={submit} loading={act.busy} disabled={!title.trim()}>
            Save note
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        <Field label="What are you researching?">
          <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Topic or question" autoFocus />
        </Field>
        <Field label="Notes" hint="(optional)">
          <Textarea rows={4} value={body} onChange={(e) => setBody(e.target.value)} placeholder="What you know or want to find out" />
        </Field>
        <ErrorNotice error={act.error} />
      </div>
    </Dialog>
  );
}
