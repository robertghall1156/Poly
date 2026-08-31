"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useAction } from "@/lib/hooks";
import type { StoryRowData } from "@/lib/types";
import { cn, relTime } from "@/lib/utils";
import { Button } from "./ui/button";
import { ErrorNotice } from "./ui/notice";
import { PrincipleChip } from "./PrincipleChip";
import { SaveToBookDialog } from "./SaveToBookDialog";

/** A story row with plain-language actions: Think this through · Create from this · Save for book · Ignore. */
export function StoryCard({ story, onChange, compact }: { story: StoryRowData; onChange?: (s: StoryRowData) => void; compact?: boolean }) {
  const router = useRouter();
  const act = useAction();
  const [book, setBook] = React.useState(false);

  const think = async () => {
    const sess = await act.run(() => api.startThink({ title: story.title, story_id: story.id, ask_first_question: true }));
    if (sess) router.push(`/think/${sess.id}`);
  };
  const ignore = async () => {
    const res = await act.run(() => api.storyAction(story.id, "ignored"));
    if (res) onChange?.({ ...story, dashboard_action: res.dashboard_action, status: res.status });
  };
  const saveForBook = () => {
    void act.run(() => api.storyAction(story.id, "save_for_book"));
    setBook(true);
  };

  return (
    <article className={cn("border-b border-zinc-200 py-3 last:border-b-0", story.dashboard_action === "ignored" && "opacity-50")}>
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
        <Link href={`/discover/stories/${story.id}`} className="text-[14px] font-semibold text-zinc-900 hover:text-accent-strong">
          {story.title}
        </Link>
        <span className="text-xs text-zinc-400">
          {story.article_count} article{story.article_count === 1 ? "" : "s"} · {relTime(story.last_updated)}
        </span>
      </div>
      {!compact && story.summary ? <p className="mt-1 text-[13px] text-zinc-700">{story.summary}</p> : null}
      {story.why_it_matters ? (
        <p className="mt-1 text-[13px] text-zinc-600">
          <span className="font-medium text-zinc-800">Why it matters: </span>
          {story.why_it_matters}
        </p>
      ) : null}
      {story.principles.length ? (
        <div className="mt-1.5 flex flex-wrap gap-1">
          {story.principles.slice(0, compact ? 2 : 5).map((p) => (
            <PrincipleChip key={p.id} p={p} />
          ))}
        </div>
      ) : null}
      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        <Button size="sm" variant="secondary" onClick={think} loading={act.busy}>
          Think this through
        </Button>
        <Button size="sm" variant="secondary" onClick={() => router.push(`/create?source=story&id=${story.id}`)}>
          Create from this
        </Button>
        <Button size="sm" variant="ghost" onClick={saveForBook}>
          Save for book
        </Button>
        <Button size="sm" variant="ghost" onClick={ignore}>
          Ignore
        </Button>
      </div>
      <ErrorNotice error={act.error} className="mt-2" />
      <SaveToBookDialog open={book} onClose={() => setBook(false)} defaults={{ title: story.title, body: story.why_it_matters || story.summary, story_id: story.id }} />
    </article>
  );
}
