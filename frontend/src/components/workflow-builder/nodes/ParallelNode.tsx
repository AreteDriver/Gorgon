import { memo } from 'react';
import { Handle, Position, type NodeProps, type Node } from '@xyflow/react';
import { Layers } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ParallelNodeData } from '@/types/workflow-builder';

type ParallelNodeType = Node<ParallelNodeData, 'parallel'>;

function ParallelNodeComponent({ data, selected }: NodeProps<ParallelNodeType>) {
  const color = '#8b5cf6'; // violet-500

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
        <Layers className="h-4 w-4 text-white" />
        <span className="text-sm font-medium text-white">Parallel</span>
      </div>

      {/* Body */}
      <div className="px-3 py-2">
        <p className="text-sm font-medium text-foreground">{data.name}</p>
        <div className="mt-1 flex flex-wrap gap-1">
          {data.strategy && (
            <span className="inline-block rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
              {data.strategy}
            </span>
          )}
          {data.maxWorkers && (
            <span className="inline-block rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
              {data.maxWorkers} workers
            </span>
          )}
          {data.failFast && (
            <span className="inline-block rounded bg-destructive/20 px-1.5 py-0.5 text-xs text-destructive">
              fail-fast
            </span>
          )}
        </div>
      </div>

      {/* Output Handle */}
      <Handle
        type="source"
        position={Position.Bottom}
        className="!h-3 !w-3 !border-2 !border-background !bg-muted-foreground"
      />
    </div>
  );
}

export const ParallelNode = memo(ParallelNodeComponent);
