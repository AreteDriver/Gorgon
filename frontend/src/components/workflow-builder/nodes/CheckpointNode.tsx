import { memo } from 'react';
import { Handle, Position, type NodeProps, type Node } from '@xyflow/react';
import { PauseCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { CheckpointNodeData } from '@/types/workflow-builder';

type CheckpointNodeType = Node<CheckpointNodeData, 'checkpoint'>;

function CheckpointNodeComponent({ data, selected }: NodeProps<CheckpointNodeType>) {
  return (
    <div
      className={cn(
        'min-w-[180px] rounded-lg border-2 border-amber-500 bg-card shadow-md transition-all',
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
      <div className="flex items-center gap-2 rounded-t-md bg-amber-500 px-3 py-2">
        <PauseCircle className="h-4 w-4 text-white" />
        <span className="text-sm font-medium text-white">Checkpoint</span>
      </div>

      {/* Body */}
      <div className="px-3 py-2">
        <p className="text-sm font-medium text-foreground">{data.name}</p>
        {data.message && (
          <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">
            {data.message}
          </p>
        )}
        {!data.message && (
          <p className="mt-1 text-xs text-muted-foreground italic">
            Workflow will pause here
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

export const CheckpointNode = memo(CheckpointNodeComponent);
