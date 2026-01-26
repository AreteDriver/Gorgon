import { memo } from 'react';
import { Handle, Position, type NodeProps, type Node } from '@xyflow/react';
import { GitBranch } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { MapReduceNodeData } from '@/types/workflow-builder';

type MapReduceNodeType = Node<MapReduceNodeData, 'map_reduce'>;

function MapReduceNodeComponent({ data, selected }: NodeProps<MapReduceNodeType>) {
  const color = '#f97316'; // orange-500

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
        <GitBranch className="h-4 w-4 text-white" />
        <span className="text-sm font-medium text-white">Map-Reduce</span>
      </div>

      {/* Body */}
      <div className="px-3 py-2">
        <p className="text-sm font-medium text-foreground">{data.name}</p>
        <div className="mt-1 flex flex-wrap gap-1">
          {data.itemsVariable && (
            <span className="inline-block rounded bg-orange-100 dark:bg-orange-900/30 px-1.5 py-0.5 text-xs text-orange-700 dark:text-orange-300">
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
        {data.mapPrompt && (
          <p className="mt-1 line-clamp-1 text-xs text-muted-foreground">
            Map: {data.mapPrompt}
          </p>
        )}
        {data.reducePrompt && (
          <p className="line-clamp-1 text-xs text-muted-foreground">
            Reduce: {data.reducePrompt}
          </p>
        )}
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

export const MapReduceNode = memo(MapReduceNodeComponent);
