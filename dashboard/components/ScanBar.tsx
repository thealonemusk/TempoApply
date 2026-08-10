'use client';

import { RefreshCw, Plus, Trash2 } from 'lucide-react';
import clsx from 'clsx';
import { Button } from '@/components/ui/Button';

interface ScanBarProps {
  scanning: boolean;
  onScan: () => void;
  onAdd: () => void;
  onClear: () => void;
}

export function ScanBar({ scanning, onScan, onAdd, onClear }: ScanBarProps) {
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
      <Button size="sm" onClick={onScan} disabled={scanning}>
        <RefreshCw className={clsx('h-4 w-4', scanning && 'animate-spin')} />
        {scanning ? 'Scanning' : 'Scan'}
      </Button>
    </div>
  );
}
