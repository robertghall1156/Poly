"use client";

import * as React from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { ArrowDown, ArrowUp, ChevronDown, Image as ImageIcon, Plus, Trash2, Undo2 } from "lucide-react";
import { api } from "@/lib/api";
import { useAction, useApi } from "@/lib/hooks";
import type { Job, SceneVisual, StudioProject, StudioScene } from "@/lib/types";
import { cn, fmtDuration } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/input";
import { ListSkeleton } from "@/components/ui/skeleton";
import { ErrorNotice } from "@/components/ui/notice";
import { JobStatus } from "@/components/JobStatus";

const VISUAL_TYPES = ["text", "title", "question", "chart", "comparison", "counter", "timeline", "list", "quote", "icon"];
const ANIMATIONS = ["fade", "slide_up", "pop", "typewriter", "none"];
const BACKGROUNDS = ["auto", "primary", "background", "accent", "gradient"];
const PLATFORMS = ["youtube_short", "tiktok", "instagram_reel", "facebook_reel", "x"];

const VARIATION_LABEL: Record<string, string> = {
  shorter: "Shorter",
  more_direct: "More direct",
  more_curious: "More curious",
  more_educational: "More educational",
  more_humorous: "More humorous",
  more_serious: "More serious",
  simpler: "Simpler",
  stronger_hook: "Stronger hook",
  change_visual_style: "Change visual style",
};

function blankScene(): StudioScene {
  return { duration: 3, narration: "", on_screen_text: "New scene", subtext: "", visual_type: "text", visual: {}, animation: "fade", transition: "cut", background: "auto", emphasis: [], source: "" };
}

export default function StudioEditorPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const router = useRouter();
  const project = useApi(() => api.studioProject(projectId), [projectId]);
  const formats = useApi(() => api.studioFormats(), []);
  const [scenes, setScenes] = React.useState<StudioScene[]>([]);
  const [selected, setSelected] = React.useState(0);
  const [dirty, setDirty] = React.useState(false);
  const [version, setVersion] = React.useState(1);
  const [title, setTitle] = React.useState("");
  const [renderJob, setRenderJob] = React.useState<string | null>(null);
  const [variationJob, setVariationJob] = React.useState<string | null>(null);
  const [imageryJob, setImageryJob] = React.useState<string | null>(null);
  const [varOpen, setVarOpen] = React.useState(false);
  const act = useAction();
  const saveAct = useAction();
  const savingRef = React.useRef(false);

  const p = project.data;

  React.useEffect(() => {
    if (project.data && !dirty && !savingRef.current) {
      setScenes(project.data.scenes ?? []);
      setTitle(project.data.title);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project.data]);

  const adoptProject = React.useCallback(
    (proj: StudioProject) => {
      project.setData(proj);
      setScenes(proj.scenes ?? []);
      setTitle(proj.title);
      setDirty(false);
      setVersion((v) => v + 1);
      setSelected((s) => Math.min(s, Math.max(0, (proj.scenes ?? []).length - 1)));
    },
    [project],
  );

  /** Persist the given scene list (defaults to current), returning the fresh project. */
  const saveScenes = React.useCallback(
    async (list?: StudioScene[]) => {
      const toSave = list ?? scenes;
      savingRef.current = true;
      try {
        const proj = await saveAct.run(() => api.patchStudioProject(projectId, { scenes: toSave.map((s, i) => ({ ...s, order: i })) }));
        if (proj) adoptProject(proj);
        return proj;
      } finally {
        savingRef.current = false;
      }
    },
    [scenes, projectId, adoptProject, saveAct],
  );

  const updateScene = (idx: number, patch: Partial<StudioScene>) => {
    setScenes((prev) => prev.map((s, i) => (i === idx ? { ...s, ...patch } : s)));
    setDirty(true);
  };

  const structural = async (fn: (prev: StudioScene[]) => StudioScene[], nextSelected?: number) => {
    const next = fn(scenes);
    setScenes(next);
    if (nextSelected != null) setSelected(nextSelected);
    await saveScenes(next);
  };

  const addScene = () => structural((prev) => [...prev, blankScene()], scenes.length);
  const deleteScene = (idx: number) =>
    structural(
      (prev) => prev.filter((_, i) => i !== idx),
      Math.max(0, Math.min(selected, scenes.length - 2)),
    );
  const moveScene = (idx: number, dir: -1 | 1) => {
    const j = idx + dir;
    if (j < 0 || j >= scenes.length) return;
    void structural(
      (prev) => {
        const next = [...prev];
        [next[idx], next[j]] = [next[j], next[idx]];
        return next;
      },
      selected === idx ? j : selected === j ? idx : selected,
    );
  };

  const saveTitle = async () => {
    if (!p || title.trim() === p.title) return;
    const r = await act.run(() => api.patchContent(p.content_item_id, { title: title.trim() }));
    if (r) project.setData({ ...p, title: r.title, content_item: { ...p.content_item, title: r.title } });
  };

  const runVariation = async (v: string) => {
    setVarOpen(false);
    if (dirty) await saveScenes();
    const j = await act.run(() => api.studioVariation(projectId, v));
    if (j) setVariationJob(j.id);
  };
  const onVariationDone = (job: Job) => {
    if (job.status === "succeeded") {
      setDirty(false);
      void project.reload();
      setVersion((x) => x + 1);
    }
  };
  const undo = async () => {
    const proj = await act.run(() => api.undoScenes(projectId));
    if (proj) adoptProject(proj);
  };

  const setVoice = async (mode: "none" | "tts") => {
    const proj = await act.run(() => api.patchStudioProject(projectId, { voice_mode: mode }));
    if (proj && p) project.setData({ ...proj, scenes: p.scenes });
  };

  // Pictures: licensed photos where a real subject exists, drawn marks where the point is an act.
  const addPictures = async () => {
    if (dirty) await saveScenes();
    const j = await act.run(() => api.addPictures(projectId));
    if (j) setImageryJob(j.id);
  };

  const render = async () => {
    if (dirty) await saveScenes();
    const j = await act.run(() => api.renderProject(projectId));
    if (j) setRenderJob(j.id);
  };
  const onRenderDone = (job: Job) => {
    if (job.status === "succeeded") {
      void project.reload();
      setVersion((x) => x + 1);
    }
  };

  const regenerate = async (idx: number, instruction: string) => {
    if (dirty) await saveScenes();
    const proj = await act.run(() => api.regenerateScene(projectId, idx, instruction));
    if (proj) adoptProject(proj);
  };

  if (project.loading) return <ListSkeleton rows={5} />;
  if (project.error || !p) return <ErrorNotice error={project.error ?? "Project not found"} />;

  const total = scenes.reduce((acc, s) => acc + (Number(s.duration) || 0), 0);
  const scene = scenes[selected] as StudioScene | undefined;
  const tts = formats.data?.tts;
  const isCarousel = p.kind === "carousel";

  return (
    <div>
      <div className="mb-1 text-xs text-zinc-500">
        <Link href="/create" className="hover:text-zinc-800">
          Create
        </Link>{" "}
        / {isCarousel ? "carousel" : "faceless video"} editor
      </div>

      {/* Top bar */}
      <div className="mb-4 flex flex-wrap items-center gap-2 rounded-md border border-zinc-200 bg-white px-3 py-2">
        <Input value={title} onChange={(e) => setTitle(e.target.value)} onBlur={saveTitle} className="h-8 max-w-md flex-1 font-medium" aria-label="Title" />
        <span className={cn("whitespace-nowrap font-mono text-xs", total > p.target_seconds * 1.25 ? "text-warn" : "text-zinc-500")}>
          {fmtDuration(total)} / target {fmtDuration(p.target_seconds)}
        </span>
        <div className="relative">
          <Button size="sm" onClick={() => setVarOpen((o) => !o)}>
            Variations <ChevronDown className="h-3 w-3" />
          </Button>
          {varOpen ? (
            <div className="absolute right-0 z-20 mt-1 w-48 rounded-md border border-zinc-200 bg-white py-1 shadow-lg">
              {(formats.data?.variations ?? Object.keys(VARIATION_LABEL)).map((v) => (
                <button key={v} type="button" onClick={() => runVariation(v)} className="block w-full px-3 py-1.5 text-left text-[13px] text-zinc-800 hover:bg-accent-soft">
                  {VARIATION_LABEL[v] ?? v.replace(/_/g, " ")}
                </button>
              ))}
              <div className="my-1 border-t border-zinc-100" />
              <button type="button" onClick={undo} className="flex w-full items-center gap-1.5 px-3 py-1.5 text-left text-[13px] text-zinc-800 hover:bg-accent-soft">
                <Undo2 className="h-3.5 w-3.5" /> Undo last change
              </button>
            </div>
          ) : null}
        </div>
        {!isCarousel ? (
          <div className="flex items-center overflow-hidden rounded-md border border-zinc-300">
            <button
              type="button"
              onClick={() => setVoice("none")}
              className={cn("px-2.5 py-1 text-xs", p.voice_mode !== "tts" ? "bg-brand text-white" : "bg-white text-zinc-600 hover:bg-zinc-50")}
            >
              No voice
            </button>
            <button
              type="button"
              onClick={() => setVoice("tts")}
              disabled={tts ? !tts.available : false}
              title={tts && !tts.available ? "No local text-to-speech voice is installed" : ""}
              className={cn("px-2.5 py-1 text-xs disabled:opacity-40", p.voice_mode === "tts" ? "bg-brand text-white" : "bg-white text-zinc-600 hover:bg-zinc-50")}
            >
              AI voice
            </button>
          </div>
        ) : null}
        {dirty ? (
          <Button size="sm" variant="secondary" onClick={() => saveScenes()} loading={saveAct.busy} data-testid="save-scenes">
            Save
          </Button>
        ) : (
          <span className="text-[11px] text-zinc-400">{saveAct.busy ? "Saving…" : "Saved"}</span>
        )}
        <Button size="sm" variant="secondary" onClick={addPictures} loading={act.busy} disabled={!!imageryJob} data-testid="add-pictures">
          <ImageIcon className="h-3.5 w-3.5" /> Add pictures
        </Button>
        <Button size="sm" variant="default" onClick={render} loading={act.busy} disabled={!!renderJob && p.render_status !== "done" && p.render_status !== "failed"} data-testid="render">
          Render
        </Button>
        <Button size="sm" variant="accent" onClick={() => router.push(`/create/review/${projectId}`)} data-testid="review">
          Review
        </Button>
      </div>
      <ErrorNotice error={act.error ?? saveAct.error} className="mb-3" />
      {variationJob ? <JobStatus jobId={variationJob} label="Applying variation" className="mb-3" onDone={onVariationDone} /> : null}
      {imageryJob ? (
        <JobStatus
          jobId={imageryJob}
          label="Finding pictures"
          className="mb-3"
          onDone={(j) => {
            setImageryJob(null);
            if (j.status === "succeeded") {
              void project.reload();
              setVersion((x) => x + 1);
            }
          }}
        />
      ) : null}
      {renderJob ? <JobStatus jobId={renderJob} label={isCarousel ? "Rendering slides" : "Rendering video"} className="mb-3" onDone={onRenderDone} /> : null}
      {p.render_status === "failed" && p.render_error ? <ErrorNotice error={`Render failed: ${p.render_error}`} className="mb-3" /> : null}

      <div className="grid gap-4 lg:grid-cols-[190px_minmax(0,1fr)_320px]">
        {/* Scene list */}
        <div className="space-y-2">
          {scenes.map((s, i) => (
            <div
              key={i}
              className={cn("group cursor-pointer rounded-md border bg-white p-1.5", i === selected ? "border-accent ring-1 ring-accent/40" : "border-zinc-200 hover:border-zinc-300")}
              onClick={() => setSelected(i)}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={api.scenePreviewUrl(projectId, i, 0.25, version)} alt={`Scene ${i + 1}`} className={cn("w-full rounded bg-zinc-100 object-cover", isCarousel ? "aspect-[4/5]" : "aspect-[9/16]")} loading="lazy" />
              <div className="mt-1 flex items-center gap-1">
                <span className="text-[11px] font-medium text-zinc-600">{i + 1}</span>
                <span className="rounded bg-zinc-100 px-1 font-mono text-[10px] text-zinc-500">{Number(s.duration).toFixed(1)}s</span>
                <span className="ml-auto hidden gap-0.5 group-hover:flex">
                  <button type="button" aria-label="Move up" onClick={(e) => { e.stopPropagation(); moveScene(i, -1); }} className="rounded p-0.5 text-zinc-500 hover:bg-zinc-100" disabled={i === 0}>
                    <ArrowUp className="h-3 w-3" />
                  </button>
                  <button type="button" aria-label="Move down" onClick={(e) => { e.stopPropagation(); moveScene(i, 1); }} className="rounded p-0.5 text-zinc-500 hover:bg-zinc-100" disabled={i === scenes.length - 1}>
                    <ArrowDown className="h-3 w-3" />
                  </button>
                  <button type="button" aria-label="Delete scene" onClick={(e) => { e.stopPropagation(); if (confirm("Delete this scene?")) void deleteScene(i); }} className="rounded p-0.5 text-danger hover:bg-danger-soft">
                    <Trash2 className="h-3 w-3" />
                  </button>
                </span>
              </div>
            </div>
          ))}
          <Button size="sm" variant="secondary" className="w-full" onClick={addScene} loading={saveAct.busy}>
            <Plus className="h-3.5 w-3.5" /> Add scene
          </Button>
        </div>

        {/* Preview */}
        <div className="min-w-0">
          {p.render_status === "done" ? (
            isCarousel ? (
              <CarouselPager projectId={projectId} count={scenes.length} version={version} />
            ) : (
              <video key={version} controls preload="metadata" src={api.projectFileUrl(p.id)} className="mx-auto max-h-[480px] rounded-md bg-black" />
            )
          ) : null}
          <div className={cn("mx-auto max-w-[300px]", p.render_status === "done" && "mt-4")}>
            <p className="mb-1 text-center text-[11px] uppercase tracking-wider text-zinc-400">Scene {selected + 1} preview</p>
            {scene ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={api.scenePreviewUrl(projectId, selected, 0.5, `${version}-${dirty ? "d" : "c"}`)} alt={`Scene ${selected + 1}`} className="w-full rounded-md border border-zinc-200 bg-zinc-100" />
            ) : (
              <p className="text-center text-xs text-zinc-400">No scenes yet — add one on the left.</p>
            )}
            {dirty ? <p className="mt-1 text-center text-[11px] text-zinc-400">Preview updates when changes save.</p> : null}
          </div>
        </div>

        {/* Properties */}
        <div className="space-y-3">
          {scene ? (
            <SceneProperties key={selected} scene={scene} onChange={(patch) => updateScene(selected, patch)} onRegenerate={(instruction) => regenerate(selected, instruction)} busy={act.busy} />
          ) : null}
          <details className="rounded-md border border-zinc-200 bg-white px-3 py-2">
            <summary className="cursor-pointer text-xs font-medium text-zinc-600 hover:text-zinc-900">Advanced</summary>
            <AdvancedPanel project={p} onSaved={(proj) => project.setData({ ...proj, scenes: p.scenes })} />
          </details>
        </div>
      </div>
    </div>
  );
}

function CarouselPager({ projectId, count, version }: { projectId: string; count: number; version: number }) {
  const [idx, setIdx] = React.useState(0);
  return (
    <div className="mx-auto max-w-[340px]">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={`${api.slideFileUrl(projectId, idx)}?v=${version}`} alt={`Slide ${idx + 1}`} className="w-full rounded-md border border-zinc-200 bg-zinc-100" />
      <div className="mt-2 flex items-center justify-center gap-3">
        <Button size="sm" onClick={() => setIdx((i) => Math.max(0, i - 1))} disabled={idx === 0}>
          Previous
        </Button>
        <span className="font-mono text-xs text-zinc-500">
          {idx + 1} / {count}
        </span>
        <Button size="sm" onClick={() => setIdx((i) => Math.min(count - 1, i + 1))} disabled={idx >= count - 1}>
          Next
        </Button>
      </div>
    </div>
  );
}

function SceneProperties({ scene, onChange, onRegenerate, busy }: { scene: StudioScene; onChange: (patch: Partial<StudioScene>) => void; onRegenerate: (instruction: string) => void; busy: boolean }) {
  const [instruction, setInstruction] = React.useState("");
  const setVisual = (patch: Partial<SceneVisual>) => onChange({ visual: { ...scene.visual, ...patch } });

  return (
    <div className="rounded-md border border-zinc-200 bg-white p-3">
      <div className="space-y-2.5">
        <Field label="Big text">
          <Textarea rows={2} value={scene.on_screen_text} onChange={(e) => onChange({ on_screen_text: e.target.value })} data-testid="big-text" />
        </Field>
        <Field label="Small text" hint="(optional)">
          <Input value={scene.subtext} onChange={(e) => onChange({ subtext: e.target.value })} />
        </Field>
        <Field label="Narration" hint="what a voice would say">
          <Textarea rows={2} value={scene.narration} onChange={(e) => onChange({ narration: e.target.value })} />
        </Field>
        <Field label={`Duration ${Number(scene.duration).toFixed(1)}s`}>
          <input type="range" min={1.5} max={10} step={0.1} value={Number(scene.duration)} onChange={(e) => onChange({ duration: Number(e.target.value) })} className="w-full" />
        </Field>
        <div className="grid grid-cols-2 gap-2">
          <Field label="Visual">
            <Select value={scene.visual_type} onChange={(e) => onChange({ visual_type: e.target.value })} className="w-full">
              {[...new Set([...VISUAL_TYPES, scene.visual_type])].map((v) => (
                <option key={v} value={v}>
                  {v.replace(/_/g, " ")}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Animation">
            <Select value={scene.animation} onChange={(e) => onChange({ animation: e.target.value })} className="w-full">
              {[...new Set([...ANIMATIONS, scene.animation])].map((a) => (
                <option key={a} value={a}>
                  {a.replace(/_/g, " ")}
                </option>
              ))}
            </Select>
          </Field>
        </div>
        <VisualFields type={scene.visual_type} visual={scene.visual ?? {}} onChange={setVisual} />
        <div className="grid grid-cols-2 gap-2">
          <Field label="Background">
            <Select value={scene.background || "auto"} onChange={(e) => onChange({ background: e.target.value, surface_locked: e.target.value !== "auto" })} className="w-full">
              {[...new Set([...BACKGROUNDS, scene.background])].map((b) => (
                <option key={b} value={b}>
                  {b}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Emphasis words" hint="comma separated">
            <Input
              value={(scene.emphasis ?? []).join(", ")}
              onChange={(e) => onChange({ emphasis: e.target.value.split(",").map((w) => w.trim()).filter(Boolean) })}
            />
          </Field>
        </div>
        <Field label="Source" hint="where this fact comes from">
          <Input value={scene.source} onChange={(e) => onChange({ source: e.target.value })} placeholder="Publication or dataset" />
        </Field>
      </div>
      <div className="mt-3 border-t border-zinc-100 pt-2.5">
        <Field label="Rewrite this scene" hint="(optional instruction)">
          <Input value={instruction} onChange={(e) => setInstruction(e.target.value)} placeholder="e.g. make it punchier" />
        </Field>
        <Button size="sm" className="mt-1.5" onClick={() => onRegenerate(instruction)} loading={busy}>
          Regenerate scene
        </Button>
      </div>
    </div>
  );
}

function VisualFields({ type, visual, onChange }: { type: string; visual: SceneVisual; onChange: (patch: Partial<SceneVisual>) => void }) {
  if (type === "chart") {
    return (
      <div className="space-y-2 rounded border border-zinc-100 bg-zinc-50/60 p-2">
        <Field label="Chart labels" hint="comma separated">
          <Input value={(visual.labels ?? []).join(", ")} onChange={(e) => onChange({ labels: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })} />
        </Field>
        <Field label="Values" hint="comma separated numbers">
          <Input
            value={(visual.values ?? []).join(", ")}
            onChange={(e) => onChange({ values: e.target.value.split(",").map((s) => Number(s.trim())).filter((n) => !Number.isNaN(n)) })}
          />
        </Field>
        <div className="grid grid-cols-2 gap-2">
          <Field label="Unit">
            <Input value={visual.unit ?? ""} onChange={(e) => onChange({ unit: e.target.value })} />
          </Field>
          <Field label="Chart source">
            <Input value={visual.source ?? ""} onChange={(e) => onChange({ source: e.target.value })} />
          </Field>
        </div>
      </div>
    );
  }
  if (type === "counter") {
    return (
      <div className="grid grid-cols-2 gap-2 rounded border border-zinc-100 bg-zinc-50/60 p-2">
        <Field label="From">
          <Input type="number" value={visual.from ?? 0} onChange={(e) => onChange({ from: Number(e.target.value) })} />
        </Field>
        <Field label="To">
          <Input type="number" value={visual.to ?? 0} onChange={(e) => onChange({ to: Number(e.target.value) })} />
        </Field>
        <Field label="Prefix">
          <Input value={visual.prefix ?? ""} onChange={(e) => onChange({ prefix: e.target.value })} placeholder="$" />
        </Field>
        <Field label="Suffix">
          <Input value={visual.suffix ?? ""} onChange={(e) => onChange({ suffix: e.target.value })} placeholder="%" />
        </Field>
        <Field label="Label" className="col-span-2">
          <Input value={visual.label ?? ""} onChange={(e) => onChange({ label: e.target.value })} />
        </Field>
      </div>
    );
  }
  if (type === "comparison") {
    return (
      <div className="grid grid-cols-2 gap-2 rounded border border-zinc-100 bg-zinc-50/60 p-2">
        <Field label="Left label">
          <Input value={visual.left?.label ?? ""} onChange={(e) => onChange({ left: { ...visual.left, label: e.target.value } })} />
        </Field>
        <Field label="Left value">
          <Input value={visual.left?.value ?? ""} onChange={(e) => onChange({ left: { ...visual.left, value: e.target.value } })} />
        </Field>
        <Field label="Right label">
          <Input value={visual.right?.label ?? ""} onChange={(e) => onChange({ right: { ...visual.right, label: e.target.value } })} />
        </Field>
        <Field label="Right value">
          <Input value={visual.right?.value ?? ""} onChange={(e) => onChange({ right: { ...visual.right, value: e.target.value } })} />
        </Field>
      </div>
    );
  }
  if (type === "list") {
    return (
      <Field label="List items" hint="one per line">
        <Textarea rows={3} value={(visual.items ?? []).join("\n")} onChange={(e) => onChange({ items: e.target.value.split("\n").filter((s) => s.trim()) })} />
      </Field>
    );
  }
  if (type === "timeline") {
    return (
      <Field label="Timeline points" hint="one per line: label | text">
        <Textarea
          rows={3}
          value={(visual.points ?? []).map((pt) => `${pt.label ?? ""} | ${pt.text ?? ""}`).join("\n")}
          onChange={(e) =>
            onChange({
              points: e.target.value
                .split("\n")
                .filter((line) => line.trim())
                .map((line) => {
                  const [label, ...rest] = line.split("|");
                  return { label: label.trim(), text: rest.join("|").trim() };
                }),
            })
          }
        />
      </Field>
    );
  }
  return null;
}

function AdvancedPanel({ project, onSaved }: { project: StudioProject; onSaved: (p: StudioProject) => void }) {
  const [music, setMusic] = React.useState(project.music_path);
  const [platform, setPlatform] = React.useState(project.platform);
  const act = useAction();
  const save = async () => {
    const r = await act.run(() => api.patchStudioProject(project.id, { music_path: music, platform }));
    if (r) onSaved(r);
  };
  return (
    <div className="mt-2 space-y-2">
      <Field label="Platform">
        <Select value={platform} onChange={(e) => setPlatform(e.target.value)} className="w-full">
          {[...new Set([...PLATFORMS, platform])].map((pf) => (
            <option key={pf} value={pf}>
              {pf.replace(/_/g, " ")}
            </option>
          ))}
        </Select>
      </Field>
      <Field label="Background music file" hint="path on this machine">
        <Input value={music} onChange={(e) => setMusic(e.target.value)} placeholder={project.music_recommendation ? `Suggestion: ${project.music_recommendation}` : "/path/to/music.mp3"} />
      </Field>
      <Button size="sm" onClick={save} loading={act.busy}>
        Save advanced settings
      </Button>
      <ErrorNotice error={act.error} />
    </div>
  );
}
