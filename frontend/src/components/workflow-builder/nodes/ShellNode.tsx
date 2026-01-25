import { memo } from 'react';
import { Handle, Position, type NodeProps, type Node } from '@xyflow/react';
import { Terminal, AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ShellNodeData } from '@/types/workflow-builder';

type ShellNodeType = Node<ShellNodeData, 'shell'>;

function ShellNodeComponent({ data, selected }: NodeProps<ShellNodeType>) {
  return (
    <div
      className={cn(
        'min-w-[200px] rounded-lg border-2 border-zinc-700 bg-zinc-900 shadow-md transition-all',
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
      <div className="flex items-center gap-2 rounded-t-md bg-zinc-800 px-3 py-2">
        <Terminal className="h-4 w-4 text-green-400" />
        <span className="text-sm font-medium text-zinc-200">Shell Command</span>
        {data.allowFailure && (
          <span title="Allows failure">
            <AlertTriangle className="h-3 w-3 text-yellow-500 ml-auto" />
          </span>
        )}
      </div>

      {/* Body */}
      <div className="px-3 py-2">
        <p className="text-sm font-medium text-zinc-200">{data.name}</p>
        {data.command && (
          <code className="mt-1 block rounded bg-zinc-800 px-2 py-1 text-xs text-green-400 font-mono truncate max-w-[180px]">
            $ {data.command}
          </code>
        )}
        {!data.command && (
          <p className="mt-1 text-xs text-zinc-500 italic">No command defined</p>
        )}
        {data.timeout && (
          <span className="mt-2 inline-block rounded bg-zinc-800 px-1.5 py-0.5 text-xs text-zinc-400">
            Timeout: {data.timeout}s
          </span>
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

export const ShellNode = memo(ShellNodeComponent);
