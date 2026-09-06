'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError, api } from './api';
import { emptySnapshot, reduceFrame, type RunFrame, type RunKind, type RunSnapshot } from './runs';
import type { Job } from './types';

/**
 * Live run state over SSE, hydrated from the stream's first snapshot frame.
 *
 * Replaces the old poll-everything-every-3s loop: the backend pushes only
 * what changed, and `connected` lets the UI say so when the backend is down
 * instead of silently rendering an empty page.
 */
export function useRun(kind: RunKind) {
  const [snapshot, setSnapshot] = useState<RunSnapshot>(() => emptySnapshot(kind));
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    let source: EventSource | null = null;
    let retry: ReturnType<typeof setTimeout> | null = null;
    let closed = false;
    let backoff = 1000;

    const connect = () => {
      if (closed) return;
      source = new EventSource(api.streamUrl(kind));

      source.onopen = () => {
        setConnected(true);
        backoff = 1000;
      };

      source.onmessage = (event) => {
        // Keepalives are SSE comments and never reach onmessage.
        let frame: RunFrame;
        try {
          frame = JSON.parse(event.data) as RunFrame;
        } catch {
          return;
        }
        setSnapshot((prev) => reduceFrame(prev, frame));
      };

      source.onerror = () => {
        setConnected(false);
        source?.close();
        source = null;
        if (closed) return;
        // EventSource retries on its own, but not after an outright refusal.
        retry = setTimeout(connect, backoff);
        backoff = Math.min(backoff * 2, 15000);
      };
    };

    connect();
    return () => {
      closed = true;
      if (retry) clearTimeout(retry);
      source?.close();
    };
  }, [kind]);

  return { run: snapshot, connected };
}

export interface JobsState {
  jobs: Job[];
  loading: boolean;
  error: string | null;
  reload: (quiet?: boolean) => Promise<void>;
  patch: (id: string, changes: Partial<Job>) => void;
}

/**
 * The job list. Refetches when `refreshKey` changes — the Runs/Jobs pages pass
 * the live run's `done` count so the table follows an apply run without a timer.
 */
export function useJobs(refreshKey: unknown = null): JobsState {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const first = useRef(true);

  const reload = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true);
    try {
      setJobs(await api.getJobs());
      setError(null);
    } catch (err) {
      // A background refresh must not blank out a table the user is reading.
      if (!quiet) {
        setError(err instanceof ApiError ? err.message : 'Could not load jobs');
        setJobs([]);
      }
    } finally {
      if (!quiet) setLoading(false);
    }
  }, []);

  useEffect(() => {
    reload(!first.current);
    first.current = false;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reload, refreshKey]);

  const patch = useCallback((id: string, changes: Partial<Job>) => {
    setJobs((prev) => prev.map((j) => (j.id === id ? { ...j, ...changes } : j)));
  }, []);

  return { jobs, loading, error, reload, patch };
}

/** One-shot fetch with loading/error state, for settings and analytics. */
export function useFetch<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(async () => {
    setLoading(true);
    try {
      setData(await fn());
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Request failed');
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    run();
  }, [run]);

  return { data, loading, error, reload: run, setData };
}

/** Persist a small preference per viewer. Storage can throw, so it is guarded. */
export function useLocalState<T>(key: string, initial: T) {
  const [value, setValue] = useState<T>(initial);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(key);
      if (raw !== null) setValue(JSON.parse(raw) as T);
    } catch {
      // ignore unavailable storage
    }
  }, [key]);

  const update = useCallback(
    (next: T) => {
      setValue(next);
      try {
        window.localStorage.setItem(key, JSON.stringify(next));
      } catch {
        // ignore unavailable storage
      }
    },
    [key],
  );

  return [value, update] as const;
}

export interface RunOptions {
  concurrency: number;
  job_timeout_sec: number;
  skip_unsupported: boolean;
  headless: boolean;
  auto_submit: boolean;
}

export const RUN_OPTIONS_KEY = 'ta.run.options';

export const DEFAULT_RUN_OPTIONS: RunOptions = {
  concurrency: 2,
  job_timeout_sec: 240,
  skip_unsupported: true,
  headless: false,
  auto_submit: true,
};

/** Apply-run tuning, shared between the Settings tab and the run controls. */
export function useRunOptions() {
  return useLocalState<RunOptions>(RUN_OPTIONS_KEY, DEFAULT_RUN_OPTIONS);
}
