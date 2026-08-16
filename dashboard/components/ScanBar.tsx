'use client';

import { RefreshCw, Plus, Trash2, Send } from 'lucide-react';
import clsx from 'clsx';
import { Button } from '@/components/ui/Button';

interface ScanBarProps {
  scanning: boolean;
  applying?: boolean;
  onScan: () => void;
  onAdd: () => void;
  onClear: () => void;
  onApplyAll?: () => void;
}

export function ScanBar({ scanning, applying, onScan, onAdd, onClear, onApplyAll }: ScanBarProps) {
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
