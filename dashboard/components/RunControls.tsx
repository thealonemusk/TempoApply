'use client';

import { useState } from 'react';
import { Play, RefreshCw, Send, Square } from 'lucide-react';
import clsx from 'clsx';
import { api, ApiError } from '@/lib/api';
import { useRunOptions } from '@/lib/hooks';
import type { RunSnapshot } from '@/lib/runs';
import type { ApplyOptions } from '@/lib/types';
import { Button } from '@/components/ui/Primitives';
import { useToast } from '@/components/ui/Toast';

interface Props {
  applyRun: RunSnapshot;
  scanRun: RunSnapshot;
  /** Number of auto-appliable jobs currently queued up, for the confirm copy. */
  applyOptions?: ApplyOptions;
  eligibleCount?: number;
  onStarted?: () => void;
  compact?: boolean;
}

/**
 * Scan / apply controls. Buttons reflect live run state from SSE, so they
 * disable correctly without the page having to track its own booleans.
 */
export function RunControls({
  applyRun,
  scanRun,
  applyOptions,
  eligibleCount,
  onStarted,
  compact = false,
}: Props) {
  const toast = useToast();
  const [runOptions] = useRunOptions();
  const [busy, setBusy] = useState<'scan' | 'apply' | 'stop' | null>(null);

  const scanning = scanRun.running;
  const applying = applyRun.running;
  const anyRunning = scanning || applying;

  const act = async (
    kind: 'scan' | 'apply' | 'stop',
    fn: () => Promise<unknown>,
    okMessage: string,
  ) => {
    setBusy(kind);
    try {
      await fn();
      toast.success(okMessage);
      onStarted?.();
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Request failed';
      toast.error(`Could not ${kind === 'stop' ? 'stop the run' : `start ${kind}`}`, message);
    } finally {
      setBusy(null);
    }
  };

  const startApply = () => {
    if (eligibleCount === 0) {
      toast.info(
        'Nothing to auto-apply to',
        'No queued job has a reachable application form. Open those postings and apply by hand.',
      );
      return;
    }
    void act(
      'apply',
      () => api.startApply({ ...runOptions, ...applyOptions }),
      eligibleCount
        ? `Applying to ${eligibleCount} job${eligibleCount === 1 ? '' : 's'}`
        : 'Apply run started',
    );
  };

  return (
    <>
      {anyRunning ? (
        <Button
          variant="danger"
          size={compact ? 'sm' : 'md'}
          loading={busy === 'stop'}
          onClick={() =>
            act(
              'stop',
              applying ? api.stopApply : api.stopScan,
              applying ? 'Stopping the apply run' : 'Stopping the scan',
            )
          }
        >
          <Square className="h-3.5 w-3.5 fill-current" />
          Stop
        </Button>
      ) : null}

      <Button
        variant="secondary"
        size={compact ? 'sm' : 'md'}
        disabled={anyRunning}
        loading={busy === 'scan'}
        onClick={() => act('scan', () => api.startScan(), 'Scan started')}
      >
        <RefreshCw className={clsx('h-3.5 w-3.5', scanning && 'animate-spin')} />
        {scanning ? 'Scanning' : 'Scan'}
      </Button>

      <Button
        size={compact ? 'sm' : 'md'}
        disabled={anyRunning}
        loading={busy === 'apply'}
        onClick={startApply}
      >
        {applying ? <Send className="h-3.5 w-3.5 anim-pulse" /> : <Play className="h-3.5 w-3.5" />}
        {applying
          ? 'Applying'
          : eligibleCount !== undefined
            ? `Auto-apply (${eligibleCount})`
            : 'Auto-apply'}
      </Button>
    </>
  );
}
