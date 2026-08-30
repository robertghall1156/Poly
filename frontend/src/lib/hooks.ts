"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, errorMessage } from "./api";
import type { Job } from "./types";

export interface ApiState<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  reload: () => Promise<void>;
  setData: (updater: T | ((prev: T | null) => T | null)) => void;
}

/** Fetch on mount (and whenever `deps` change). `fetcher` should be stable or captured by deps. */
export function useApi<T>(fetcher: () => Promise<T>, deps: unknown[] = []): ApiState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;
  const seq = useRef(0);

  const reload = useCallback(async () => {
    const id = ++seq.current;
    try {
      const d = await fetcherRef.current();
      if (id === seq.current) {
        setData(d);
        setError(null);
      }
    } catch (e) {
      if (id === seq.current) setError(errorMessage(e));
    } finally {
      if (id === seq.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    void reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  const set = useCallback((updater: T | ((prev: T | null) => T | null)) => {
    setData((prev) => (typeof updater === "function" ? (updater as (p: T | null) => T | null)(prev) : updater));
  }, []);

  return { data, error, loading, reload, setData: set };
}

export const TERMINAL_JOB = new Set(["succeeded", "failed", "cancelled"]);

/** Poll a job until it reaches a terminal status. Pass null to disable. */
export function useJob(jobId: string | null, onDone?: (job: Job) => void, interval = 1500) {
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const onDoneRef = useRef(onDone);
  onDoneRef.current = onDone;

  useEffect(() => {
    if (!jobId) {
      setJob(null);
      setError(null);
      return;
    }
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | null = null;
    const tick = async () => {
      try {
        const j = await api.job(jobId);
        if (stopped) return;
        setJob(j);
        setError(null);
        if (TERMINAL_JOB.has(j.status)) {
          onDoneRef.current?.(j);
          return;
        }
      } catch (e) {
        if (stopped) return;
        setError(errorMessage(e));
      }
      timer = setTimeout(tick, interval);
    };
    void tick();
    return () => {
      stopped = true;
      if (timer) clearTimeout(timer);
    };
  }, [jobId, interval]);

  const retry = useCallback(async () => {
    if (!jobId) return;
    try {
      const j = await api.retryJob(jobId);
      setJob(j);
      setError(null);
      // restart polling by re-fetching on the next tick
      const poll = async () => {
        const cur = await api.job(jobId);
        setJob(cur);
        if (!TERMINAL_JOB.has(cur.status)) setTimeout(poll, interval);
        else onDoneRef.current?.(cur);
      };
      setTimeout(poll, interval);
    } catch (e) {
      setError(errorMessage(e));
    }
  }, [jobId, interval]);

  return { job, error, retry };
}

/** Small helper for async button actions: tracks busy + error. */
export function useAction() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const run = useCallback(async <T,>(fn: () => Promise<T>): Promise<T | undefined> => {
    setBusy(true);
    setError(null);
    try {
      return await fn();
    } catch (e) {
      setError(errorMessage(e));
      return undefined;
    } finally {
      setBusy(false);
    }
  }, []);
  return { busy, error, run, setError };
}
