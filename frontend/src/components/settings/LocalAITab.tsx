"use client";

import * as React from "react";
import { api } from "@/lib/api";
import { useAction, useApi } from "@/lib/hooks";
import type { AllSettings, LocalModel, ModelTestResult } from "@/lib/types";
import { cn, fmtBytes, fmtNumber, relTime } from "@/lib/utils";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Field, Input, Select } from "../ui/input";
import { Switch } from "../ui/switch";
import { Table, TBody, TD, TH, THead, TR } from "../ui/table";
import { ListSkeleton } from "../ui/skeleton";
import { EmptyState, ErrorNotice, Notice } from "../ui/notice";
import { Panel, Section } from "../ui/section";

export function LocalAITab({ settings }: { settings: AllSettings | null }) {
  const ai = useApi(() => api.localAI(), []);
  const act = useAction();
  const [tests, setTests] = React.useState<Record<string, ModelTestResult | "running">>({});
  const [errors, setErrors] = React.useState<Record<string, string>>({});

  const patch = async (m: LocalModel, body: Parameters<typeof api.patchModel>[1]) => {
    try {
      const r = await api.patchModel(m.id, body);
      ai.setData((d) => (d ? { ...d, models: d.models.map((x) => (x.id === m.id ? r : x)) } : d));
      setErrors((e) => ({ ...e, [m.id]: "" }));
    } catch (e) {
      setErrors((er) => ({ ...er, [m.id]: e instanceof Error ? e.message : String(e) }));
    }
  };
  const test = async (m: LocalModel) => {
    setTests((t) => ({ ...t, [m.id]: "running" }));
    try {
      const r = await api.testModel(m.id);
      setTests((t) => ({ ...t, [m.id]: r }));
      ai.reload();
    } catch (e) {
      setTests((t) => ({ ...t, [m.id]: { ok: false, detail: e instanceof Error ? e.message : String(e) } }));
    }
  };
  const refresh = async () => {
    const r = await act.run(() => api.refreshLocalAI());
    if (r) ai.reload();
  };

  const d = ai.data;
  const rec = settings?.env.transcription_recommendation;
  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <p className="text-xs text-zinc-500">Last detection {d?.last_detection ? relTime(d.last_detection) : "never"}.</p>
        <Button variant="default" className="ml-auto" onClick={refresh} loading={act.busy}>
          Refresh local models
        </Button>
      </div>
      <ErrorNotice error={ai.error ?? act.error} className="mb-3" />
      {ai.loading ? <ListSkeleton /> : null}
      {d ? (
        <>
          <Section title="Runtimes">
            <div className="grid gap-2 md:grid-cols-2">
              {d.runtimes.length === 0 ? <EmptyState title="No runtimes detected.">Install Ollama or LM Studio, start it, then refresh.</EmptyState> : null}
              {d.runtimes.map((r) => (
                <div key={r.runtime} className="flex items-center gap-3 rounded-md border border-zinc-200 bg-white px-3 py-2 text-[13px]">
                  <span className={cn("h-2 w-2 rounded-full", r.running ? "bg-emerald-500" : "bg-zinc-300")} />
                  <span className="font-medium text-zinc-900">{r.runtime}</span>
                  <span className="font-mono text-xs text-zinc-500">{r.endpoint}</span>
                  <span className="ml-auto text-xs text-zinc-500">
                    {r.running ? `running${r.version ? ` · v${r.version}` : ""} · ${r.model_count} models` : "not running"}
                  </span>
                  {r.error ? <span className="text-xs text-red-700">{r.error}</span> : null}
                </div>
              ))}
            </div>
          </Section>

          <Section title="Models">
            {d.models.length === 0 ? <EmptyState title="No models registered.">Pull a model in your runtime and refresh, or add an endpoint manually below.</EmptyState> : null}
            {d.models.length ? (
              <Table>
                <THead>
                  <tr>
                    <TH>Model</TH>
                    <TH>Runtime</TH>
                    <TH className="text-right">Size</TH>
                    <TH className="text-right">Context</TH>
                    <TH>Tasks</TH>
                    <TH>On</TH>
                    <TH className="text-right">Priority</TH>
                    <TH>Health</TH>
                    <TH></TH>
                  </tr>
                </THead>
                <TBody>
                  {d.models.map((m) => {
                    const t = tests[m.id];
                    return (
                      <TR key={m.id}>
                        <TD>
                          <div className="font-medium text-zinc-900">{m.name}</div>
                          <div className="font-mono text-[11px] text-zinc-400">{m.endpoint}</div>
                          {m.locality !== "local" ? <Badge variant="warn">{m.locality}</Badge> : null}
                          {errors[m.id] ? <div className="text-xs text-red-700">{errors[m.id]}</div> : null}
                        </TD>
                        <TD className="text-xs">{m.runtime}</TD>
                        <TD className="text-right text-xs tabular-nums">{fmtBytes(m.size_bytes)}</TD>
                        <TD className="text-right text-xs tabular-nums">{m.context_window ? fmtNumber(m.context_window) : "—"}</TD>
                        <TD>
                          <div className="flex max-w-[16rem] flex-wrap gap-1">
                            {d.task_categories.map((tc) => {
                              const on = m.tasks.includes(tc);
                              return (
                                <button
                                  key={tc}
                                  type="button"
                                  onClick={() => patch(m, { tasks: on ? m.tasks.filter((x) => x !== tc) : [...m.tasks, tc] })}
                                  className={cn("rounded border px-1.5 text-[10px] font-medium", on ? "border-accent bg-accent-soft text-[#0f6f74]" : "border-zinc-200 bg-white text-zinc-400 hover:text-zinc-700")}
                                >
                                  {tc}
                                </button>
                              );
                            })}
                          </div>
                        </TD>
                        <TD>
                          <Switch checked={m.enabled} onChange={(v) => patch(m, { enabled: v })} />
                        </TD>
                        <TD className="text-right">
                          <Input type="number" defaultValue={m.priority} className="h-7 w-20 text-right text-xs" onBlur={(e) => Number(e.target.value) !== m.priority && patch(m, { priority: Number(e.target.value) })} />
                        </TD>
                        <TD className="text-xs">
                          {m.last_ok_at ? (
                            <div className="text-emerald-700">
                              ok {relTime(m.last_ok_at)}
                              {m.last_latency_ms != null ? ` · ${m.last_latency_ms.toFixed(0)} ms` : ""}
                            </div>
                          ) : (
                            <div className="text-zinc-400">untested</div>
                          )}
                          {m.last_error ? <div className="max-w-[12rem] truncate text-red-700" title={m.last_error}>{m.last_error}</div> : null}
                          {t && t !== "running" ? (
                            <div className={t.ok ? "text-emerald-700" : "text-red-700"}>
                              test: {t.ok ? "ok" : "failed"}
                              {t.latency_ms != null ? ` · ${Number(t.latency_ms).toFixed(0)} ms` : ""}
                              {t.detail ? ` · ${t.detail}` : ""}
                            </div>
                          ) : null}
                        </TD>
                        <TD className="whitespace-nowrap">
                          <Button size="sm" onClick={() => test(m)} loading={t === "running"}>
                            Test
                          </Button>
                          {!m.detected || m.runtime === "manual" || m.runtime === "openai_compat" ? (
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={async () => {
                                await act.run(() => api.deleteModel(m.id));
                                ai.reload();
                              }}
                            >
                              Remove
                            </Button>
                          ) : null}
                        </TD>
                      </TR>
                    );
                  })}
                </TBody>
              </Table>
            ) : null}
          </Section>

          <div className="grid gap-4 md:grid-cols-2">
            <Section title="Task assignment">
              <Panel>
                <dl className="grid grid-cols-[8rem_1fr] gap-y-1 text-[13px]">
                  {Object.entries(d.assignments).map(([task, model]) => (
                    <React.Fragment key={task}>
                      <dt className="font-mono text-xs text-zinc-500">{task}</dt>
                      <dd className={model ? "text-zinc-900" : "text-zinc-400"}>{model ?? "unassigned"}</dd>
                    </React.Fragment>
                  ))}
                </dl>
              </Panel>
            </Section>
            <Section title="Media tooling">
              <Panel>
                <dl className="space-y-2 text-[13px]">
                  <div>
                    <dt className="text-[11px] uppercase text-zinc-500">FFmpeg</dt>
                    <dd>
                      {d.ffmpeg.ok ? <Badge variant="success">available</Badge> : <Badge variant="danger">missing</Badge>}
                      <span className="ml-2 font-mono text-xs text-zinc-500">
                        {d.ffmpeg.ffmpeg ?? "—"} · {d.ffmpeg.ffprobe ?? "—"}
                      </span>
                    </dd>
                  </div>
                  <div>
                    <dt className="text-[11px] uppercase text-zinc-500">Image provider</dt>
                    <dd>
                      {d.image_provider.deterministic ? <Badge variant="success">deterministic renderers</Badge> : null}{" "}
                      {d.image_provider.configured ? <Badge variant={d.image_provider.available ? "success" : "warn"}>{d.image_provider.kind || "generative"} {d.image_provider.available ? "available" : "unavailable"}</Badge> : <Badge variant="neutral">generative: not configured</Badge>}
                    </dd>
                  </div>
                  {rec ? (
                    <div>
                      <dt className="text-[11px] uppercase text-zinc-500">Transcription recommendation</dt>
                      <dd>
                        <span className="font-medium">{rec.runtime}</span> (default model {rec.default_model}) — {rec.why}
                        <pre className="mt-1 rounded bg-zinc-50 p-2 font-mono text-[11px]">{rec.command}</pre>
                      </dd>
                    </div>
                  ) : null}
                </dl>
              </Panel>
            </Section>
          </div>

          <Section title="Add model / endpoint" description="Register a llama.cpp server, vLLM or any OpenAI-compatible endpoint on this machine.">
            <AddModelForm tasks={d.task_categories} onAdded={() => ai.reload()} />
          </Section>
          <Notice>All inference runs against these local endpoints. Cloud providers are only used when Privacy &amp; Network explicitly allows cloud AI.</Notice>
        </>
      ) : null}
    </div>
  );
}

function AddModelForm({ tasks, onAdded }: { tasks: string[]; onAdded: () => void }) {
  const [f, setF] = React.useState({ name: "", runtime: "openai_compat", endpoint: "http://localhost:8080/v1", tasks: ["FAST"] as string[], priority: 100, context_window: "" });
  const act = useAction();
  const submit = async () => {
    const r = await act.run(() => api.addModel({ name: f.name, runtime: f.runtime, endpoint: f.endpoint, tasks: f.tasks, priority: Number(f.priority), context_window: f.context_window ? Number(f.context_window) : null, locality: "local" }));
    if (r) {
      setF({ ...f, name: "" });
      onAdded();
    }
  };
  return (
    <Panel>
      <div className="grid gap-2 md:grid-cols-5">
        <Field label="Model name">
          <Input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} placeholder="qwen2.5:14b" />
        </Field>
        <Field label="Runtime">
          <Select value={f.runtime} onChange={(e) => setF({ ...f, runtime: e.target.value })} className="w-full">
            {["openai_compat", "ollama", "lmstudio", "llamacpp", "vllm", "mlx"].map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Endpoint" className="md:col-span-2">
          <Input value={f.endpoint} onChange={(e) => setF({ ...f, endpoint: e.target.value })} />
        </Field>
        <Field label="Priority">
          <Input type="number" value={f.priority} onChange={(e) => setF({ ...f, priority: Number(e.target.value) })} />
        </Field>
        <Field label="Context window" hint="(optional)">
          <Input type="number" value={f.context_window} onChange={(e) => setF({ ...f, context_window: e.target.value })} />
        </Field>
        <Field label="Tasks" className="md:col-span-4">
          <div className="flex flex-wrap gap-1 pt-1.5">
            {tasks.map((t) => {
              const on = f.tasks.includes(t);
              return (
                <button key={t} type="button" onClick={() => setF({ ...f, tasks: on ? f.tasks.filter((x) => x !== t) : [...f.tasks, t] })} className={cn("rounded border px-1.5 text-[11px] font-medium", on ? "border-accent bg-accent-soft text-[#0f6f74]" : "border-zinc-200 bg-white text-zinc-400")}>
                  {t}
                </button>
              );
            })}
          </div>
        </Field>
      </div>
      <div className="mt-2 flex items-center gap-2">
        <Button variant="default" onClick={submit} loading={act.busy} disabled={!f.name.trim() || !f.endpoint.trim()}>
          Add model
        </Button>
        <ErrorNotice error={act.error} />
      </div>
    </Panel>
  );
}
