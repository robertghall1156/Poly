"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useAction } from "@/lib/hooks";
import type { StoryRowData } from "@/lib/types";
import { cn, labelFormat, relTime } from "@/lib/utils";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { ErrorNotice } from "./ui/notice";
import { Relevance, StatusBadge } from "./badges";
import { PrincipleChip } from "./PrincipleChip";
import { GenerateContentDialog } from "./GenerateContentDialog";
import { SaveToBookDialog } from "./SaveToBookDialog";

export function StoryRow({ story, onChange, compact }: { story: StoryRowData; onChange?: (s: StoryRowData) => void; compact?: boolean }) {
  const router = useRouter();
  const act = useAction();
  const [gen, setGen] = React.useState(false);
  const [book, setBook] = React.useState(false);
  const [expanded, setExpanded] = React.useState(!compact);

  const doAction = async (action: string) => {
    const res = await act.run(() => api.storyAction(story.id, action));
    if (res) onChange?.({ ...story, dashboard_action: res.dashboard_action, status: res.status });
    if (action === "develop_position" && res) router.push(`/think?story=${story.id}`);
  };

  const forArgs = story.arguments.filter((a) => a.side === "for" || a.side === "pro");
  const againstArgs = story.arguments.filter((a) => !(a.side === "for" || a.side === "pro"));
  const opp = story.content_potential[0];

  return (
    <article className={cn("border-b border-zinc-200 py-3 last:border-b-0", story.dashboard_action === "ignored" && "opacity-60")}>
      <div className="flex items-start gap-3">
        <div className="w-8 shrink-0 pt-0.5 text-right">
          <Relevance value={story.relevance_score} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
            <Link href={`/stories/${story.id}`} className="text-[14px] font-semibold text-zinc-900 hover:text-accent-strong">
              {story.title}
            </Link>
            <StatusBadge status={story.status} />
            {story.dashboard_action && story.dashboard_action !== "none" ? <Badge variant="outline">{story.dashboard_action.replace(/_/g, " ")}</Badge> : null}
            <span className="text-xs text-zinc-400">
              {story.article_count} article{story.article_count === 1 ? "" : "s"} · {relTime(story.last_updated)}
            </span>
          </div>
          {story.summary ? <p className="mt-1 text-[13px] text-zinc-700">{story.summary}</p> : null}
          {story.why_it_matters ? (
            <p className="mt-1 text-[13px] text-zinc-600">
              <span className="font-medium text-zinc-800">Why it matters: </span>
              {story.why_it_matters}
            </p>
          ) : null}
          {story.principles.length ? (
            <div className="mt-1.5 flex flex-wrap gap-1">
              {story.principles.map((p) => (
                <PrincipleChip key={p.id} p={p} />
              ))}
            </div>
          ) : null}
          {compact ? (
            <button type="button" onClick={() => setExpanded((e) => !e)} className="mt-1 text-xs text-accent-strong hover:underline">
              {expanded ? "Hide details" : "Show arguments, sources and opportunity"}
            </button>
          ) : null}
          {expanded ? (
            <div className="mt-2 grid gap-3 text-[13px] md:grid-cols-3">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-wide text-zinc-500">Strongest arguments</p>
                {story.arguments.length === 0 ? <p className="text-xs text-zinc-400">Not analysed yet.</p> : null}
                {forArgs.length ? (
                  <ul className="mt-0.5 space-y-0.5">
                    {forArgs.map((a, i) => (
                      <li key={`f${i}`} className="text-zinc-700">
                        <span className="mr-1 rounded bg-emerald-50 px-1 text-[10px] font-medium uppercase text-emerald-800">for</span>
                        {a.argument}
                      </li>
                    ))}
                  </ul>
                ) : null}
                {againstArgs.length ? (
                  <ul className="mt-0.5 space-y-0.5">
                    {againstArgs.map((a, i) => (
                      <li key={`a${i}`} className="text-zinc-700">
                        <span className="mr-1 rounded bg-warn-soft px-1 text-[10px] font-medium uppercase text-[#9a3a1c]">{a.side || "against"}</span>
                        {a.argument}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-wide text-zinc-500">Primary sources</p>
                {story.primary_sources.length === 0 ? <p className="text-xs text-zinc-400">None identified.</p> : null}
                <ul className="mt-0.5 space-y-0.5">
                  {story.primary_sources.map((s, i) => (
                    <li key={i} className="truncate">
                      {s.url ? (
                        <a href={s.url} target="_blank" rel="noreferrer" className="text-accent-strong hover:underline">
                          {s.title || s.publication || s.url}
                        </a>
                      ) : (
                        <span>{s.title || s.publication || JSON.stringify(s)}</span>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-wide text-zinc-500">Content opportunity</p>
                {opp ? (
                  <p className="mt-0.5 text-zinc-700">
                    {opp.angle}
                    {opp.score != null ? <span className="ml-1 font-mono text-[11px] text-zinc-400">{Math.round(opp.score * 100)}</span> : null}
                  </p>
                ) : (
                  <p className="text-xs text-zinc-400">No opportunity scored.</p>
                )}
                {story.recommended_format ? (
                  <p className="mt-0.5 text-xs text-zinc-500">
                    Recommended format: <span className="font-medium text-zinc-700">{labelFormat(story.recommended_format)}</span>
                  </p>
                ) : null}
              </div>
            </div>
          ) : null}
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            <Button size="sm" variant="ghost" onClick={() => doAction("ignored")} loading={act.busy}>
              Ignore
            </Button>
            <Button size="sm" variant="secondary" onClick={() => doAction("research")}>
              Research
            </Button>
            <Button size="sm" variant="secondary" onClick={() => doAction("develop_position")}>
              Develop Position
            </Button>
            <Button size="sm" variant="secondary" onClick={() => setGen(true)}>
              Create Content
            </Button>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => {
                void doAction("save_for_book");
                setBook(true);
              }}
            >
              Save for Book
            </Button>
          </div>
          <ErrorNotice error={act.error} className="mt-2" />
        </div>
      </div>
      <GenerateContentDialog open={gen} onClose={() => setGen(false)} defaults={{ story_id: story.id, format: story.recommended_format || "youtube", principle_ids: story.principles.slice(0, 3).map((p) => p.id) }} />
      <SaveToBookDialog open={book} onClose={() => setBook(false)} defaults={{ title: story.title, body: story.why_it_matters || story.summary, story_id: story.id }} />
    </article>
  );
}
