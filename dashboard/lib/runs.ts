/**
 * Mirror of backend/runtime/events.py — the run-progress contract.
 * Keep these shapes in sync with RunState / JobProgress / Step.
 */

export type RunKind = 'apply' | 'scan';

export type RunStatus = 'idle' | 'running' | 'stopping' | 'stopped' | 'done' | 'error';

export type JobRunState =
  | 'queued'
  | 'running'
  | 'applied'
  | 'needs_review'
  | 'failed'
  | 'skipped';

export const TERMINAL_JOB_STATES: JobRunState[] = [
  'applied',
  'needs_review',
  'failed',
  'skipped',
];

export type StepKind =
  | 'navigate'
  | 'detect'
  | 'signin'
  | 'upload'
  | 'fill'
  | 'next'
  | 'submit'
  | 'confirm'
  | 'error'
  | 'info';

export interface RunStep {
  ts: string;
  kind: StepKind | string;
  detail: string;
  ok: boolean | null;
}

export interface JobProgress {
  job_id: string;
  title: string;
  company: string;
  url: string;
  ats: string;
  state: JobRunState;
  message: string;
  screenshot: string;
  final_url: string;
  started_at: string | null;
  finished_at: string | null;
  steps: RunStep[];
}

export interface RunTotals {
  total: number;
  done: number;
  queued: number;
  running: number;
  applied: number;
  needs_review: number;
  failed: number;
  skipped: number;
}

export interface RunHeader {
  run_id: string;
  kind: RunKind;
  status: RunStatus;
  concurrency: number;
  started_at: string | null;
  finished_at: string | null;
  message: string;
  error: string;
  meta: Record<string, unknown>;
  totals: RunTotals;
  running: boolean;
}

export interface RunSnapshot extends RunHeader {
  jobs: JobProgress[];
}

/**
 * Frames emitted on /api/{kind}/stream.
 * `snapshot` is sent once on connect so a client can hydrate mid-run.
 */
export type RunFrame =
  | { type: 'snapshot'; data: RunSnapshot }
  | { type: 'run'; data: RunHeader }
  | { type: 'job'; data: JobProgress }
  | { type: 'step'; data: { job_id: string; step: RunStep } }
  | { type: 'end'; data: RunSnapshot };

export const EMPTY_TOTALS: RunTotals = {
  total: 0,
  done: 0,
  queued: 0,
  running: 0,
  applied: 0,
  needs_review: 0,
  failed: 0,
  skipped: 0,
};

export function emptySnapshot(kind: RunKind): RunSnapshot {
  return {
    run_id: '',
    kind,
    status: 'idle',
    concurrency: 1,
    started_at: null,
    finished_at: null,
    message: '',
    error: '',
    meta: {},
    totals: { ...EMPTY_TOTALS },
    running: false,
    jobs: [],
  };
}

/** Apply a single stream frame to a snapshot, returning a new snapshot. */
export function reduceFrame(prev: RunSnapshot, frame: RunFrame): RunSnapshot {
  switch (frame.type) {
    // Hydration and completion both carry an authoritative full snapshot.
    case 'snapshot':
      return { ...prev, ...frame.data };
    case 'run': {
      // A new run_id means a fresh run — drop stale jobs.
      const sameRun = !prev.run_id || prev.run_id === frame.data.run_id;
      return { ...prev, ...frame.data, jobs: sameRun ? prev.jobs : [] };
    }
    case 'job': {
      const next = [...prev.jobs];
      const i = next.findIndex((j) => j.job_id === frame.data.job_id);
      // Preserve locally accumulated steps: job frames carry the authoritative list,
      // but a step frame may have arrived first.
      if (i === -1) next.push(frame.data);
      else next[i] = { ...frame.data, steps: frame.data.steps.length ? frame.data.steps : next[i].steps };
      return { ...prev, jobs: next };
    }
    case 'step': {
      const next = [...prev.jobs];
      const i = next.findIndex((j) => j.job_id === frame.data.job_id);
      if (i === -1) return prev;
      next[i] = { ...next[i], steps: [...next[i].steps, frame.data.step] };
      return { ...prev, jobs: next };
    }
    case 'end':
      return { ...prev, ...frame.data };
    default:
      return prev;
  }
}

export const JOB_STATE_LABELS: Record<JobRunState, string> = {
  queued: 'Queued',
  running: 'Applying',
  applied: 'Applied',
  needs_review: 'Needs review',
  failed: 'Failed',
  skipped: 'Skipped',
};

export const STEP_LABELS: Record<string, string> = {
  navigate: 'Opened',
  detect: 'Detected',
  signin: 'Sign-in',
  upload: 'Resume',
  fill: 'Filled',
  next: 'Next step',
  submit: 'Submit',
  confirm: 'Confirmation',
  error: 'Error',
  info: 'Note',
};
