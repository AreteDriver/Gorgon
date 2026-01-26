import { memo } from 'react';
import { Handle, Position, type NodeProps, type Node } from '@xyflow/react';
import { Merge } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { FanInNodeData } from '@/types/workflow-builder';

type FanInNodeType = Node<FanInNodeData, 'fan_in'>;

function FanInNodeComponent({ data, selected }: NodeProps<FanInNodeType>) {
  const color = '#14b8a6'; // teal-500

  return (
    <div
      className={cn(
        'min-w-[180px] rounded-lg border-2 bg-card shadow-md transition-all',
        selected ? 'ring-2 ring-primary ring-offset-2' : ''
      )}
      style={{ borderColor: color }}
    >
      {/* Multiple Input Handles to indicate fan-in */}
      <Handle
        type="target"
        position={Position.Top}
        id="in-1"
        className="!h-3 !w-3 !border-2 !border-background !bg-muted-foreground"
        style={{ left: '30%' }}
      />
      <Handle
        type="target"
        position={Position.Top}
        id="in-2"
        className="!h-3 !w-3 !border-2 !border-background !bg-muted-foreground"
        style={{ left: '50%' }}
      />
      <Handle
        type="target"
        position={Position.Top}
        id="in-3"
        className="!h-3 !w-3 !border-2 !border-background !bg-muted-foreground"
        style={{ left: '70%' }}
      />

      {/* Header */}
      <div
        className="flex items-center gap-2 rounded-t-md px-3 py-2"
        style={{ backgroundColor: color }}
      >
        <Merge className="h-4 w-4 text-white" />
        <span className="text-sm font-medium text-white">Fan In</span>
      </div>

      {/* Body */}
      <div className="px-3 py-2">
        <p className="text-sm font-medium text-foreground">{data.name}</p>
        <div className="mt-1 flex flex-wrap gap-1">
          {data.inputVariable && (
            <span className="inline-block rounded bg-teal-100 dark:bg-teal-900/30 px-1.5 py-0.5 text-xs text-teal-700 dark:text-teal-300">
              ${'{'}${data.inputVariable}{'}'}
            </span>
          )}
          {data.aggregation && (
            <span className="inline-block rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
              {data.aggregation === 'claude_code' ? 'AI aggregate' : data.aggregation}
            </span>
          )}
        </div>
        {data.aggregatePrompt && (
          <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">
            {data.aggregatePrompt}
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

export const FanInNode = memo(FanInNodeComponent);
