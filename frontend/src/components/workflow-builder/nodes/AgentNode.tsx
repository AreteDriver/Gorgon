import { memo } from 'react';
import { Handle, Position, type NodeProps, type Node } from '@xyflow/react';
import {
  ClipboardList,
  Hammer,
  FlaskConical,
  Search,
  Building2,
  FileText,
  BarChart2,
  PieChart,
  FileBarChart,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import type { AgentNodeData } from '@/types/workflow-builder';
import { getAgentRoleInfo } from '@/types/workflow-builder';

const iconMap: Record<string, React.ComponentType<{ className?: string }>> = {
  'clipboard-list': ClipboardList,
  'hammer': Hammer,
  'flask-conical': FlaskConical,
  'search': Search,
  'building-2': Building2,
  'file-text': FileText,
  'bar-chart-2': BarChart2,
  'pie-chart': PieChart,
  'file-bar-chart': FileBarChart,
};

type AgentNodeType = Node<AgentNodeData, 'agent'>;

function AgentNodeComponent({ data, selected }: NodeProps<AgentNodeType>) {
  const roleInfo = getAgentRoleInfo(data.role);
  const Icon = iconMap[roleInfo.icon] || ClipboardList;

  return (
    <div
      className={cn(
        'min-w-[180px] rounded-lg border-2 bg-card shadow-md transition-all',
        selected ? 'ring-2 ring-primary ring-offset-2' : ''
      )}
      style={{ borderColor: roleInfo.color }}
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
        style={{ backgroundColor: roleInfo.color }}
      >
        <Icon className="h-4 w-4 text-white" />
        <span className="text-sm font-medium text-white">{roleInfo.label}</span>
      </div>

      {/* Body */}
      <div className="px-3 py-2">
        <p className="text-sm font-medium text-foreground">{data.name}</p>
        {data.prompt && (
          <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">
            {data.prompt}
          </p>
        )}
        {data.onFailure && data.onFailure !== 'stop' && (
          <span className="mt-2 inline-block rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
            On fail: {data.onFailure}
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

export const AgentNode = memo(AgentNodeComponent);
