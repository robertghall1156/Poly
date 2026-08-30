"use client";

import * as React from "react";
import Link from "next/link";
import { DndContext, DragOverlay, PointerSensor, useDraggable, useDroppable, useSensor, useSensors, type DragEndEvent, type DragStartEvent } from "@dnd-kit/core";
import { api, ApiError } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import type { Board, BoardCard } from "@/lib/types";
import { cn, fmtDate, labelFormat } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Field, Input } from "@/components/ui/input";
import { ListSkeleton } from "@/components/ui/skeleton";
import { ErrorNotice } from "@/components/ui/notice";
import { PageHeader, Section } from "@/components/ui/section";
import { FactCheckDot } from "@/components/badges";

const COLUMNS = ["IDEA", "RESEARCHING", "POSITION_DEVELOPED", "SCRIPTING", "RECORDED", "EDITING", "READY", "PUBLISHED"];

export default function CalendarPage() {
  const board = useApi(() => api.board(), []);
  const [active, setActive] = React.useState<BoardCard | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [gate, setGate] = React.useState<{ card: BoardCard; status: string; message: string } | null>(null);
  const [reason, setReason] = React.useState("");
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }));

  const move = async (card: BoardCard, status: string, override = "") => {
    const prev = board.data;
    // optimistic move
    board.setData((b) => {
      if (!b) return b;
      const next: Board = {};
      for (const k of Object.keys(b)) next[k] = b[k].filter((c) => c.id !== card.id);
      next[status] = [...(next[status] ?? []), card];
      return next;
    });
    try {
      await api.setContentStatus(card.id, status, override);
      setError(null);
      setGate(null);
      setReason("");
    } catch (e) {
      board.setData(() => prev);
      if (e instanceof ApiError && e.status === 409) setGate({ card, status, message: e.detail });
      else setError(e instanceof Error ? e.message : String(e));
    }
  };

  const onDragStart = (e: DragStartEvent) => setActive((e.active.data.current as { card: BoardCard }).card);
  const onDragEnd = (e: DragEndEvent) => {
    setActive(null);
    const card = (e.active.data.current as { card: BoardCard; status: string }).card;
    const from = (e.active.data.current as { status: string }).status;
    const to = e.over?.id as string | undefined;
    if (!to || to === from) return;
    void move(card, to);
  };

  const upcoming = React.useMemo(() => {
    const all = Object.entries(board.data ?? {}).flatMap(([status, cards]) => cards.map((c) => ({ ...c, status })));
    return all.filter((c) => c.publish_date).sort((a, b) => (a.publish_date ?? "").localeCompare(b.publish_date ?? ""));
  }, [board.data]);

  return (
    <div>
      <PageHeader title="Calendar" description="The content pipeline. Drag cards between columns; READY and PUBLISHED are gated by fact check." />
      <ErrorNotice error={board.error ?? error} className="mb-3" />
      {board.loading ? <ListSkeleton rows={2} /> : null}
      {board.data ? (
        <DndContext sensors={sensors} onDragStart={onDragStart} onDragEnd={onDragEnd}>
          <div className="overflow-x-auto pb-2">
            <div className="flex min-w-max gap-2 lg:min-w-0">
              {COLUMNS.map((col) => (
                <Column key={col} id={col} cards={board.data?.[col] ?? []} />
              ))}
            </div>
          </div>
          <DragOverlay>{active ? <CardView card={active} dragging /> : null}</DragOverlay>
        </DndContext>
      ) : null}

      <Section title="Upcoming by date" className="mt-6">
        {upcoming.length === 0 ? <p className="text-xs text-zinc-400">No items have a publish date. Set one on a content item.</p> : null}
        {upcoming.length ? (
          <div className="rounded-md border border-zinc-200 bg-white">
            {upcoming.map((c) => (
              <div key={c.id} className="flex items-center gap-3 border-b border-zinc-200 px-3 py-1.5 text-[13px] last:border-b-0">
                <span className="w-24 font-mono text-[11px] text-zinc-500">{fmtDate(c.publish_date)}</span>
                <Link href={`/content/${c.id}`} className="min-w-0 flex-1 truncate font-medium text-zinc-900 hover:text-accent-strong">
                  {c.title}
                </Link>
                <span className="text-[11px] text-zinc-500">{labelFormat(c.format)}</span>
                {c.platform ? <Badge variant="outline">{c.platform}</Badge> : null}
                <Badge>{c.status.replace(/_/g, " ")}</Badge>
              </div>
            ))}
          </div>
        ) : null}
      </Section>

      <Dialog
        open={!!gate}
        onClose={() => setGate(null)}
        title="Fact-check gate"
        footer={
          <>
            <Button variant="ghost" onClick={() => setGate(null)}>
              Cancel
            </Button>
            <Button variant="warn" disabled={!reason.trim()} onClick={() => gate && move(gate.card, gate.status, reason.trim())}>
              Override with reason
            </Button>
          </>
        }
      >
        {gate ? (
          <div className="space-y-3">
            <p className="text-[13px] text-zinc-800">
              “{gate.card.title}” cannot move to {gate.status.replace(/_/g, " ")}:
            </p>
            <p className="rounded border border-warn/50 bg-warn-soft p-2 text-xs text-[#9a3a1c]">{gate.message}</p>
            <Field label="Override reason" hint="recorded on the item">
              <Input value={reason} onChange={(e) => setReason(e.target.value)} autoFocus />
            </Field>
            <p className="text-xs text-zinc-500">
              Prefer resolving the claims on the{" "}
              <Link href={`/content/${gate.card.id}`} className="text-accent-strong hover:underline">
                item’s Fact check tab
              </Link>
              .
            </p>
          </div>
        ) : null}
      </Dialog>
    </div>
  );
}

function Column({ id, cards }: { id: string; cards: BoardCard[] }) {
  const { setNodeRef, isOver } = useDroppable({ id });
  const gated = id === "READY" || id === "PUBLISHED";
  return (
    <div ref={setNodeRef} className={cn("flex w-52 shrink-0 flex-col rounded-md border bg-zinc-50 lg:w-auto lg:min-w-0 lg:flex-1", isOver ? "border-accent bg-accent-soft/40" : "border-zinc-200")}>
      <div className="flex items-center gap-1.5 border-b border-zinc-200 px-2.5 py-1.5">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-zinc-600">{id.replace(/_/g, " ")}</span>
        <span className="text-[11px] text-zinc-400">{cards.length}</span>
        {gated ? <span className="ml-auto text-[10px] uppercase text-[#b3401f]">gated</span> : null}
      </div>
      <div className="flex min-h-[8rem] flex-1 flex-col gap-1.5 p-1.5">
        {cards.map((c) => (
          <DraggableCard key={c.id} card={c} status={id} />
        ))}
      </div>
    </div>
  );
}

function DraggableCard({ card, status }: { card: BoardCard; status: string }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({ id: card.id, data: { card, status } });
  return (
    <div ref={setNodeRef} {...attributes} {...listeners} className={cn(isDragging && "opacity-40")}>
      <CardView card={card} />
    </div>
  );
}

function CardView({ card, dragging }: { card: BoardCard; dragging?: boolean }) {
  return (
    <div className={cn("cursor-grab rounded border border-zinc-200 bg-white px-2 py-1.5 shadow-sm", dragging && "rotate-1 shadow-lg")}>
      <div className="flex items-start gap-1.5">
        <FactCheckDot status={card.fact_check_status} className="mt-1.5 shrink-0" />
        <Link href={`/content/${card.id}`} onClick={(e) => e.stopPropagation()} className="line-clamp-2 text-[12.5px] font-medium leading-snug text-zinc-900 hover:text-accent-strong">
          {card.title}
        </Link>
      </div>
      <div className="mt-1 flex flex-wrap items-center gap-1 text-[10.5px] text-zinc-500">
        <span>{labelFormat(card.format)}</span>
        {card.platform ? <Badge variant="outline" className="text-[10px]">{card.platform}</Badge> : null}
        {card.publish_date ? <span className="ml-auto font-mono">{fmtDate(card.publish_date, { month: "short", day: "numeric" })}</span> : null}
      </div>
    </div>
  );
}
