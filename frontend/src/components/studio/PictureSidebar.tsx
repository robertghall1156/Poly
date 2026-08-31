"use client";

import * as React from "react";
import { Search } from "lucide-react";
import { api } from "@/lib/api";
import type { ImageCandidate, ImageRecord, StudioScene } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ErrorNotice } from "@/components/ui/notice";

type Tab = "search" | "library" | "deck";

/**
 * The picture panel: search, everything already downloaded, and what this deck is using.
 *
 * Automatic subject detection gets it right often and wrong often, and when it is wrong the
 * fix has to be a click — not a regeneration, and not a conversation. So the panel sits open
 * beside the slides: click a picture, it goes on the selected slide and is pinned so nothing
 * later overwrites it.
 */
export function PictureSidebar({
  projectId,
  scenes,
  selected,
  onSelectScene,
  onChanged,
}: {
  projectId: string;
  scenes: StudioScene[];
  selected: number;
  onSelectScene: (i: number) => void;
  onChanged: () => void;
}) {
  const [tab, setTab] = React.useState<Tab>("search");
  const [q, setQ] = React.useState("");
  const [results, setResults] = React.useState<ImageCandidate[] | null>(null);
  const [library, setLibrary] = React.useState<ImageRecord[] | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const loadLibrary = React.useCallback(async () => {
    try {
      setLibrary(await api.images());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  React.useEffect(() => {
    if (tab === "library" && library === null) void loadLibrary();
  }, [tab, library, loadLibrary]);

  // Seed the box with what this slide is about, so the common case is one keystroke: Enter.
  React.useEffect(() => {
    const s = scenes[selected];
    if (!s || q) return;
    const guess = String((s.visual as { query?: string } | undefined)?.query || "");
    if (guess) setQ(guess);
  }, [selected, scenes, q]);

  const runSearch = async () => {
    if (!q.trim()) return;
    setBusy(true);
    setError(null);
    try {
      setResults((await api.searchImages(q.trim(), 18)).results);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setResults([]);
    } finally {
      setBusy(false);
    }
  };

  const apply = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
      await loadLibrary();
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const used = scenes
    .map((s, i) => ({ i, path: String((s.visual as { path?: string } | undefined)?.path || "") }))
    .filter((x) => x.path);

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-1 border-b border-zinc-200 pb-1.5">
        {(["search", "library", "deck"] as Tab[]).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={cn(
              "px-1.5 pb-1 text-[11px] font-heading uppercase tracking-wider",
              tab === t ? "border-b-2 border-accent text-ink" : "text-zinc-400 hover:text-zinc-600",
            )}
          >
            {t === "search" ? "Find" : t === "library" ? "Saved" : `In deck (${used.length})`}
          </button>
        ))}
      </div>

      <p className="text-[11px] text-zinc-500">
        Goes on slide <span className="font-medium text-ink">{selected + 1}</span>
      </p>

      {tab === "search" ? (
        <>
          <div className="flex gap-1.5">
            <Input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && void runSearch()}
              placeholder="Trump arch, Lake Ontario…"
              className="h-8 text-[12px]"
              aria-label="Search pictures"
            />
            <Button size="sm" variant="secondary" onClick={runSearch} loading={busy} aria-label="Search">
              <Search className="h-3.5 w-3.5" />
            </Button>
          </div>
          {results && results.length === 0 ? (
            <p className="text-[11px] text-zinc-500">
              Nothing openly-licensed for that. Try a plain name — a person, a place, a building.
            </p>
          ) : null}
          <Grid>
            {(results ?? []).map((c) => (
              <Thumb
                key={c.url}
                src={c.thumb_url || c.url}
                caption={c.license}
                title={`${c.title || "untitled"} — ${c.credit || c.license}`}
                disabled={busy}
                onClick={() => apply(() => api.attachSceneImage(projectId, selected, c, "band"))}
              />
            ))}
          </Grid>
        </>
      ) : null}

      {tab === "library" ? (
        <Grid>
          {(library ?? []).map((im) => (
            <Thumb
              key={im.id}
              src={api.imageFileUrl(im.id)}
              caption={im.is_generated ? "AI" : im.label}
              title={im.title}
              disabled={busy}
              onClick={() => apply(() => api.attachLibraryImage(projectId, selected, im.id, "band"))}
            />
          ))}
          {library && library.length === 0 ? (
            <p className="col-span-2 text-[11px] text-zinc-500">Nothing saved yet — anything you use gets kept here.</p>
          ) : null}
        </Grid>
      ) : null}

      {tab === "deck" ? (
        <Grid>
          {used.map((x) => (
            <Thumb
              key={x.i}
              src={api.scenePreviewUrl(projectId, x.i, 0.25)}
              caption={`Slide ${x.i + 1}`}
              title={`Slide ${x.i + 1}`}
              disabled={false}
              onClick={() => onSelectScene(x.i)}
            />
          ))}
          {used.length === 0 ? (
            <p className="col-span-2 text-[11px] text-zinc-500">No slide has a picture yet.</p>
          ) : null}
        </Grid>
      ) : null}

      <ErrorNotice error={error} />
    </div>
  );
}

function Grid({ children }: { children: React.ReactNode }) {
  // An explicit height, not flex-fill: the panel's parent has no resolved height, so a
  // flex-1 child collapsed to zero and every result rendered into nothing.
  return <div className="grid max-h-[300px] auto-rows-min grid-cols-3 gap-1.5 overflow-y-auto pr-0.5">{children}</div>;
}

function Thumb({ src, caption, title, disabled, onClick }: { src: string; caption: string; title: string; disabled: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={title}
      className="overflow-hidden border border-zinc-200 text-left hover:border-accent disabled:opacity-50"
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={src} alt={title} className="aspect-square w-full bg-zinc-100 object-cover" loading="lazy" />
      <span className="block truncate px-1 py-0.5 text-[9px] text-zinc-500">{caption}</span>
    </button>
  );
}
