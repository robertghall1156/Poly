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
    <article className={cn("border-t border-divider py-4 first:border-t-0", story.dashboard_action === "ignored" && "opacity-50")}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
        <Link href={`/discover/stories/${story.id}`} className="min-w-0 font-heading text-[17px] leading-snug text-ink [text-wrap:pretty] hover:text-accent-strong">
          {story.title}
        </Link>
        <span className="meta shrink-0">
          {story.topics[0] ? `${story.topics[0]} · ` : ""}
          {story.article_count} source{story.article_count === 1 ? "" : "s"} · {relTime(story.last_updated)}
        </span>
      </div>
      {!compact && story.summary ? <p className="mt-1 text-[13.5px] text-zinc-600">{story.summary}</p> : null}
      {story.why_it_matters ? (
        <p className="mt-1 text-[13.5px] text-zinc-700">
          <span className="font-heading text-ink">Why it matters — </span>
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
