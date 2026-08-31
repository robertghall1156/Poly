"use client";

import * as React from "react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import type { StudioSourceIn } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Select, Textarea } from "./../ui/input";

export type SourceType = "story" | "position" | "belief" | "research" | "video" | "custom";

export interface SourceSelection {
  type: SourceType;
  id: string;
  idea: string;
}

export const SOURCE_LABEL: Record<SourceType, string> = {
  story: "Current story",
  position: "My position",
  belief: "What I believe",
  research: "Research",
  video: "My video",
  custom: "Custom idea",
};

/** Convert a UI selection into the studio API's source shape. */
export function toStudioSource(sel: SourceSelection): StudioSourceIn {
  switch (sel.type) {
    case "story":
      return { story_id: sel.id };
    case "position":
      return { brief_id: sel.id };
    case "belief":
      return { principle_id: sel.id };
    case "research":
      return { research_note_id: sel.id };
    case "video":
      return { video_id: sel.id };
    default:
      return { idea: sel.idea };
  }
}

export function sourceReady(sel: SourceSelection): boolean {
  return sel.type === "custom" ? sel.idea.trim().length > 0 : !!sel.id;
}

export function useSourceData(open = true) {
  const stories = useApi(() => (open ? api.stories({ days: 60, limit: 100 }) : Promise.resolve([])), [open]);
  const briefs = useApi(() => (open ? api.briefs() : Promise.resolve([])), [open]);
  const principles = useApi(() => (open ? api.principles() : Promise.resolve([])), [open]);
  const research = useApi(() => (open ? api.research() : Promise.resolve([])), [open]);
  return { stories: stories.data ?? [], briefs: briefs.data ?? [], principles: principles.data ?? [], research: research.data ?? [] };
}

export function SourcePicker({ value, onChange, showVideo }: { value: SourceSelection; onChange: (v: SourceSelection) => void; showVideo?: boolean }) {
  const data = useSourceData();
  const types: SourceType[] = ["custom", "story", "position", "belief", "research", ...(showVideo || value.type === "video" ? (["video"] as SourceType[]) : [])];

  const options: { id: string; title: string }[] =
    value.type === "story"
      ? data.stories.map((s) => ({ id: s.id, title: s.title }))
      : value.type === "position"
        ? data.briefs.map((b) => ({ id: b.id, title: b.issue }))
        : value.type === "belief"
          ? data.principles.map((p) => ({ id: p.id, title: p.title }))
          : value.type === "research"
            ? data.research.map((r) => ({ id: r.id, title: r.title }))
            : [];

  return (
    <div>
      <div className="flex flex-wrap gap-1.5">
        {types.map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => onChange({ type: t, id: "", idea: value.idea })}
            className={cn(
              "rounded-full border px-3 py-1 text-xs font-medium transition-colors",
              value.type === t ? "border-accent bg-accent-soft text-accent-strong" : "border-zinc-300 bg-white text-zinc-700 hover:bg-zinc-50",
            )}
          >
            {SOURCE_LABEL[t]}
          </button>
        ))}
      </div>
      <div className="mt-2">
        {value.type === "custom" ? (
          <Textarea rows={3} value={value.idea} onChange={(e) => onChange({ ...value, idea: e.target.value })} placeholder="Describe your idea in a sentence or two…" />
        ) : value.type === "video" ? (
          <p className="text-xs text-zinc-500">Using your selected video as the starting point.</p>
        ) : (
          <Select value={value.id} onChange={(e) => onChange({ ...value, id: e.target.value })} className="w-full">
            <option value="">Choose {SOURCE_LABEL[value.type].toLowerCase()}…</option>
            {options.map((o) => (
              <option key={o.id} value={o.id}>
                {o.title}
              </option>
            ))}
          </Select>
        )}
      </div>
    </div>
  );
}
