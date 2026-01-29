import { memo } from 'react';
import { Handle, Position, type NodeProps, type Node } from '@xyflow/react';
import { GitFork } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { BranchNodeData } from '@/types/workflow-builder';

type BranchNodeType = Node<BranchNodeData, 'branch'>;

function BranchNodeComponent({ data, selected }: NodeProps<BranchNodeType>) {
  const operatorLabels: Record<string, string> = {
    equals: '=',
    not_equals: '!=',
    contains: 'contains',
    greater_than: '>',
    less_than: '<',
  };

  return (
    <div
      className={cn(
        'min-w-[200px] rounded-lg border-2 border-violet-500 bg-card shadow-md transition-all',
        selected ? 'ring-2 ring-primary ring-offset-2' : ''
      )}
    >
      {/* Input Handle */}
      <Handle
        type="target"
        position={Position.Top}
        className="!h-3 !w-3 !border-2 !border-background !bg-muted-foreground"
      />

      {/* Header */}
      <div className="flex items-center gap-2 rounded-t-md bg-violet-500 px-3 py-2">
        <GitFork className="h-4 w-4 text-white" />
        <span className="text-sm font-medium text-white">Branch</span>
      </div>

      {/* Body */}
      <div className="px-3 py-2">
        <p className="text-sm font-medium text-foreground">{data.name}</p>
        {data.condition && (
          <div className="mt-2 rounded bg-muted/50 px-2 py-1 font-mono text-xs">
            {data.condition.field} {operatorLabels[data.condition.operator] || data.condition.operator} {String(data.condition.value)}
          </div>
        )}
      </div>

      {/* Branch labels and handles */}
      <div className="flex justify-between px-3 pb-2 text-xs">
        <div className="flex flex-col items-center">
          <span className="text-green-600 font-medium">{data.trueLabel || 'True'}</span>
        </div>
        <div className="flex flex-col items-center">
          <span className="text-red-500 font-medium">{data.falseLabel || 'False'}</span>
        </div>
      </div>

      {/* True Output Handle (left) */}
      <Handle
        type="source"
        position={Position.Bottom}
        id="true"
        className="!h-3 !w-3 !border-2 !border-background !bg-green-500 !left-[25%]"
      />

      {/* False Output Handle (right) */}
      <Handle
        type="source"
        position={Position.Bottom}
        id="false"
        className="!h-3 !w-3 !border-2 !border-background !bg-red-500 !left-[75%]"
      />
    </div>
  );
}

export const BranchNode = memo(BranchNodeComponent);
