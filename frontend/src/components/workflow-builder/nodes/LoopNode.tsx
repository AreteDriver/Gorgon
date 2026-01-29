import { memo } from 'react';
import { Handle, Position, type NodeProps, type Node } from '@xyflow/react';
import { RefreshCw } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { LoopNodeData } from '@/types/workflow-builder';

type LoopNodeType = Node<LoopNodeData, 'loop'>;

function LoopNodeComponent({ data, selected }: NodeProps<LoopNodeType>) {
  const operatorLabels: Record<string, string> = {
    equals: '=',
    not_equals: '!=',
    contains: 'contains',
    greater_than: '>',
    less_than: '<',
  };

  const loopTypeLabels: Record<string, string> = {
    while: 'while',
    for: 'for',
    until: 'until',
  };

  return (
    <div
      className={cn(
        'min-w-[200px] rounded-lg border-2 border-emerald-500 bg-card shadow-md transition-all',
        selected ? 'ring-2 ring-primary ring-offset-2' : ''
      )}
    >
      {/* Input Handle */}
      <Handle
        type="target"
        position={Position.Top}
        className="!h-3 !w-3 !border-2 !border-background !bg-muted-foreground"
      />

      {/* Loop Back Handle (left side) */}
      <Handle
        type="target"
        position={Position.Left}
        id="loop-back"
        className="!h-3 !w-3 !border-2 !border-background !bg-emerald-500"
      />

      {/* Header */}
      <div className="flex items-center gap-2 rounded-t-md bg-emerald-500 px-3 py-2">
        <RefreshCw className="h-4 w-4 text-white" />
        <span className="text-sm font-medium text-white">Loop</span>
        {data.loopType && (
          <span className="text-xs text-emerald-100">({loopTypeLabels[data.loopType] || data.loopType})</span>
        )}
      </div>

      {/* Body */}
      <div className="px-3 py-2">
        <p className="text-sm font-medium text-foreground">{data.name}</p>

        {data.condition && (
          <div className="mt-2 rounded bg-muted/50 px-2 py-1 font-mono text-xs">
            {loopTypeLabels[data.loopType || 'while']} {data.condition.field} {operatorLabels[data.condition.operator] || data.condition.operator} {String(data.condition.value)}
          </div>
        )}

        <div className="mt-2 flex items-center justify-between text-xs text-muted-foreground">
          {data.maxIterations && (
            <span>max: {data.maxIterations}</span>
          )}
          {data.iterationVariable && (
            <span className="font-mono">${'{' + data.iterationVariable + '}'}</span>
          )}
        </div>
      </div>

      {/* Loop Body Output (bottom) */}
      <Handle
        type="source"
        position={Position.Bottom}
        id="body"
        className="!h-3 !w-3 !border-2 !border-background !bg-emerald-500"
      />

      {/* Exit Output (right side) */}
      <Handle
        type="source"
        position={Position.Right}
        id="exit"
        className="!h-3 !w-3 !border-2 !border-background !bg-muted-foreground"
      />
    </div>
  );
}

export const LoopNode = memo(LoopNodeComponent);
