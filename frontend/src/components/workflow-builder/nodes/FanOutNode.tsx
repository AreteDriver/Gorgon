import { memo } from 'react';
import { Handle, Position, type NodeProps, type Node } from '@xyflow/react';
import { Split } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { FanOutNodeData } from '@/types/workflow-builder';

type FanOutNodeType = Node<FanOutNodeData, 'fan_out'>;

function FanOutNodeComponent({ data, selected }: NodeProps<FanOutNodeType>) {
  const color = '#06b6d4'; // cyan-500

  return (
    <div
      className={cn(
        'min-w-[180px] rounded-lg border-2 bg-card shadow-md transition-all',
        selected ? 'ring-2 ring-primary ring-offset-2' : ''
      )}
      style={{ borderColor: color }}
    >
      {/* Input Handle */}
      <Handle
        type="target"
        position={Position.Top}
        className="!h-3 !w-3 !border-2 !border-background !bg-muted-foreground"
      />

      {/* Header */}
      <div
        className="flex items-center gap-2 rounded-t-md px-3 py-2"
        style={{ backgroundColor: color }}
      >
        <Split className="h-4 w-4 text-white" />
        <span className="text-sm font-medium text-white">Fan Out</span>
      </div>

      {/* Body */}
      <div className="px-3 py-2">
        <p className="text-sm font-medium text-foreground">{data.name}</p>
        <div className="mt-1 flex flex-wrap gap-1">
          {data.itemsVariable && (
            <span className="inline-block rounded bg-cyan-100 dark:bg-cyan-900/30 px-1.5 py-0.5 text-xs text-cyan-700 dark:text-cyan-300">
              ${'{'}${data.itemsVariable}{'}'}
            </span>
          )}
          {data.maxConcurrent && (
            <span className="inline-block rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
              max {data.maxConcurrent}
            </span>
          )}
          {data.failFast && (
            <span className="inline-block rounded bg-destructive/20 px-1.5 py-0.5 text-xs text-destructive">
              fail-fast
            </span>
          )}
        </div>
      </div>

      {/* Multiple Output Handles to indicate fan-out */}
      <Handle
        type="source"
        position={Position.Bottom}
        id="out-1"
        className="!h-3 !w-3 !border-2 !border-background !bg-muted-foreground"
        style={{ left: '30%' }}
      />
      <Handle
        type="source"
        position={Position.Bottom}
        id="out-2"
        className="!h-3 !w-3 !border-2 !border-background !bg-muted-foreground"
        style={{ left: '50%' }}
      />
      <Handle
        type="source"
        position={Position.Bottom}
        id="out-3"
        className="!h-3 !w-3 !border-2 !border-background !bg-muted-foreground"
        style={{ left: '70%' }}
      />
    </div>
  );
}

export const FanOutNode = memo(FanOutNodeComponent);
