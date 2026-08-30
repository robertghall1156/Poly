"use client";

import * as React from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useAction, useApi } from "@/lib/hooks";
import { cn, fmtDateTime, humanize } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { ListSkeleton } from "@/components/ui/skeleton";
import { ErrorNotice, Notice } from "@/components/ui/notice";
import { PageHeader, Panel } from "@/components/ui/section";
import { Confidence, StatusBadge } from "@/components/badges";
import { usePrivacy } from "@/components/PrivacyContext";

export default function ThinkSessionPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { privacy } = usePrivacy();
  const session = useApi(() => api.thinkSession(id), [id]);
  const [answer, setAnswer] = React.useState("");
  const act = useAction();
  const briefAct = useAction();
  const endRef = React.useRef<HTMLDivElement>(null);

  const s = session.data;
  React.useEffect(() => {
    endRef.current?.scrollIntoView({ block: "nearest" });
  }, [s?.messages.length]);

  const submit = async () => {
    if (!answer.trim()) return;
    const r = await act.run(() => api.answerThink(id, answer.trim()));
    if (r) {
      session.setData(r);
      setAnswer("");
    }
  };
  const makeBrief = async () => {
    const b = await briefAct.run(() => api.briefFromThink(id));
    if (b) router.push(`/think/briefs/${b.id}`);
  };
  const abandon = async () => {
    const r = await act.run(() => api.abandonThink(id));
    if (r) session.reload();
  };

  if (session.loading) return <ListSkeleton rows={4} />;
  if (session.error || !s) return <ErrorNotice error={session.error ?? "Session not found"} />;

  const msgs = s.messages ?? [];
  const last = msgs[msgs.length - 1];
  const awaiting = s.status === "active" && last?.role === "assistant";
  const cloud = privacy?.cloud_ai_permitted;
  const userTurns = msgs.filter((m) => m.role === "user").length;

  return (
    <div>
      <div className="mb-1 text-xs text-zinc-500">
        <Link href="/think" className="hover:text-zinc-800">
          Think
        </Link>{" "}
        / session
      </div>
      <PageHeader
        title={s.title}
        description={
          <span className="flex flex-wrap items-center gap-2">
            <StatusBadge status={s.status} />
            <span>{userTurns} answers</span>
            {s.story_id ? (
              <Link href={`/stories/${s.story_id}`} className="text-accent-strong hover:underline">
                Open story
              </Link>
            ) : null}
            {s.model_used ? <span className="font-mono text-[11px] text-zinc-400">{s.model_used}</span> : null}
          </span>
        }
        actions={
          <>
            {s.status === "active" ? (
              <Button variant="ghost" onClick={abandon}>
                Abandon
              </Button>
            ) : null}
            <Button variant={cloud ? "warn" : "default"} onClick={makeBrief} loading={briefAct.busy} disabled={userTurns === 0}>
              Generate Position Brief
            </Button>
          </>
        }
      />
      <ErrorNotice error={briefAct.error} className="mb-3" />
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_280px]">
        <div className="min-w-0">
          {s.question ? (
            <Panel className="mb-3" title="Question">
              <p className="text-[13px] text-zinc-800">{s.question}</p>
            </Panel>
          ) : null}
          <div className="space-y-3">
            {msgs.map((m, i) => (
              <div key={i} className={cn("rounded-md border px-4 py-3", m.role === "assistant" ? "border-zinc-200 bg-white" : "ml-8 border-accent/30 bg-accent-soft/50")}>
                <div className="mb-1 flex items-center gap-2 text-[11px] uppercase tracking-wide text-zinc-500">
                  <span>{m.role === "assistant" ? "Interviewer" : "You"}</span>
                  {m.role === "assistant" && m.kind ? <Badge variant="outline">{humanize(m.kind)}</Badge> : null}
                  {m.created_at ? <span className="ml-auto normal-case tracking-normal text-zinc-400">{fmtDateTime(m.created_at)}</span> : null}
                </div>
                <p className={cn("whitespace-pre-wrap text-[14px] text-zinc-900", m.role === "assistant" && "font-medium")}>{m.content}</p>
                {m.role === "assistant" && m.note ? <p className="mt-1.5 border-l-2 border-zinc-200 pl-2 text-xs text-zinc-500">{m.note}</p> : null}
              </div>
            ))}
          </div>
          <div ref={endRef} />
          {awaiting ? (
            <div className="mt-3 rounded-md border border-zinc-300 bg-white p-3">
              <Textarea
                rows={5}
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                placeholder="Answer honestly. The next question depends on what you say here."
                onKeyDown={(e) => {
                  if ((e.metaKey || e.ctrlKey) && e.key === "Enter") submit();
                }}
              />
              <div className="mt-2 flex items-center gap-2">
                <Button variant={cloud ? "warn" : "default"} onClick={submit} loading={act.busy} disabled={!answer.trim()}>
                  {cloud ? "Answer (cloud AI may be used)" : "Answer"}
                </Button>
                <span className="text-xs text-zinc-400">⌘/Ctrl + Enter to submit</span>
              </div>
              <ErrorNotice error={act.error} className="mt-2" />
            </div>
          ) : null}
          {s.status === "active" && !awaiting ? <Notice className="mt-3">Waiting for the interviewer’s next question. If the local model failed, retry by re-answering or check Settings → Local AI.</Notice> : null}
          {s.status !== "active" ? <Notice className="mt-3">This session is {s.status}. Briefs generated from it are listed on the right.</Notice> : null}
        </div>
        <aside className="space-y-3">
          <Panel title="Briefs">
            {s.briefs.length === 0 ? <p className="text-xs text-zinc-400">No brief yet.</p> : null}
            <ul className="space-y-1.5">
              {s.briefs.map((b) => (
                <li key={b.id} className="text-[13px]">
                  <Link href={`/think/briefs/${b.id}`} className="font-medium text-zinc-900 hover:text-accent-strong">
                    {b.issue}
                  </Link>
                  <div className="flex items-center gap-2">
                    <StatusBadge status={b.status} />
                    <Confidence value={b.confidence} />
                  </div>
                </li>
              ))}
            </ul>
          </Panel>
          <Panel title="Principles considered">
            {s.principles_considered.length === 0 ? <p className="text-xs text-zinc-400">None yet.</p> : null}
            <ul className="space-y-1">
              {s.principles_considered.map((p) => (
                <li key={p.id} className="text-[13px]">
                  <Link href={`/principles/${p.id}`} className="text-zinc-900 hover:text-accent-strong">
                    {p.title}
                  </Link>
                  <span className="ml-1 text-[11px] text-zinc-400">{p.category}</span>
                </li>
              ))}
            </ul>
          </Panel>
        </aside>
      </div>
    </div>
  );
}
