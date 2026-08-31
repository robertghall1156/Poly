"use client";

import * as React from "react";
import { Search } from "lucide-react";
import { api } from "@/lib/api";
import type { ImageCandidate, SceneVisual } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/input";
import { ErrorNotice } from "@/components/ui/notice";

/**
 * Search openly-licensed pictures and put one on this scene.
 *
 * The resolver guesses a subject from the story, and it is right often enough to be useful and
 * wrong often enough to be infuriating — so choosing by eye has to be two clicks, not a
 * regeneration. Everything listed here may be republished; the licence rides along with it.
 */
export function PicturePicker({
  projectId,
  sceneIndex,
  visual,
  onAttached,
  onChange,
}: {
  projectId: string;
  sceneIndex: number;
  visual: SceneVisual;
  onAttached: () => void;
  onChange: (patch: Partial<SceneVisual>) => void;
}) {
  const [q, setQ] = React.useState("");
  const [results, setResults] = React.useState<ImageCandidate[] | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const attached = typeof visual.path === "string" && visual.path.length > 0;

  const run = async () => {
    if (!q.trim()) return;
    setBusy(true);
    setError(null);
    try {
      setResults((await api.searchImages(q.trim(), 12)).results);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setResults(null);
    } finally {
      setBusy(false);
    }
  };

  const attach = async (c: ImageCandidate) => {
    setBusy(true);
    setError(null);
    try {
      await api.attachSceneImage(projectId, sceneIndex, c, String(visual.treatment || "band"));
      setResults(null);
      onAttached();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-2 border-t border-zinc-200 pt-3">
      <div className="flex items-center justify-between">
        <p className="kicker text-zinc-500">Picture</p>
        {attached ? (
          <Select
            value={String(visual.treatment || "band")}
            onChange={(e) => onChange({ treatment: e.target.value })}
            className="h-7 w-auto text-[11px]"
          >
            <option value="band">In the layout</option>
            <option value="full_bleed">Full bleed</option>
            <option value="portrait">Portrait</option>
          </Select>
        ) : null}
      </div>

      {attached ? (
        <p className="text-[11px] text-zinc-500">
          {visual.generated ? "AI-generated illustration" : String(visual.credit || "attached")}
          <button type="button" className="ml-2 text-accent hover:underline" onClick={() => onChange({ path: "", credit: "", image_id: "" })}>
            remove
          </button>
        </p>
      ) : null}

      <div className="flex gap-1.5">
        <Input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && void run()}
          placeholder="Trump arch, Lake Ontario…"
          className="h-8 text-[12px]"
        />
        <Button size="sm" variant="secondary" onClick={run} loading={busy} aria-label="Search pictures">
          <Search className="h-3.5 w-3.5" />
        </Button>
      </div>

      <ErrorNotice error={error} />

      {results && results.length === 0 ? (
        <p className="text-[11px] text-zinc-500">
          Nothing openly-licensed for that. Try the plain name of a person, place or building.
        </p>
      ) : null}

      {results && results.length > 0 ? (
        <div className="grid grid-cols-3 gap-1.5">
          {results.map((c) => (
            <button
              key={c.url}
              type="button"
              onClick={() => attach(c)}
              disabled={busy}
              title={`${c.title || "untitled"} — ${c.credit || c.license}`}
              className="group overflow-hidden border border-zinc-200 hover:border-accent disabled:opacity-50"
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={c.thumb_url || c.url} alt={c.title || ""} className="aspect-square w-full bg-zinc-100 object-cover" loading="lazy" />
              <span className="block truncate px-1 py-0.5 text-left text-[9px] text-zinc-500">{c.license}</span>
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
