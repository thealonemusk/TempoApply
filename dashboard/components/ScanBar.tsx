'use client';

import { RefreshCw, Plus, Trash2, Send, Square } from 'lucide-react';
import clsx from 'clsx';
import { Button } from '@/components/ui/Button';

interface ScanBarProps {
  scanning: boolean;
  applying?: boolean;
  onScan: () => void;
  onAdd: () => void;
  onClear: () => void;
  onApplyAll?: () => void;
  onStopApply?: () => void;
  onStopScan?: () => void;
}

export function ScanBar({
  scanning,
  applying,
  onScan,
  onAdd,
  onClear,
  onApplyAll,
  onStopApply,
  onStopScan,
}: ScanBarProps) {
  return (
    <div className="flex items-center gap-2">
      <Button variant="secondary" size="sm" onClick={onClear}>
        <Trash2 className="h-4 w-4" />
        Clear
      </Button>
      <Button variant="secondary" size="sm" onClick={onAdd}>
        <Plus className="h-4 w-4" />
        Add
      </Button>
      {scanning && onStopScan && (
        <Button variant="danger" size="sm" onClick={onStopScan}>
          <Square className="h-3.5 w-3.5 fill-current" />
          Stop
        </Button>
      )}
      {onApplyAll && applying && onStopApply && (
        <Button variant="danger" size="sm" onClick={onStopApply}>
          <Square className="h-3.5 w-3.5 fill-current" />
          Stop
        </Button>
      )}
      {onApplyAll && (
        <Button variant="secondary" size="sm" onClick={onApplyAll} disabled={scanning || applying}>
          <Send className={clsx('h-4 w-4', applying && 'animate-pulse')} />
          {applying ? 'Applying' : 'Apply all'}
        </Button>
      )}
      <Button size="sm" onClick={onScan} disabled={scanning || applying}>
        <RefreshCw className={clsx('h-4 w-4', scanning && 'animate-spin')} />
        {scanning ? 'Scanning' : 'Scan'}
      </Button>
    </div>
  );
}
