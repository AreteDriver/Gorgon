import { DragEvent } from 'react';
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
  Terminal,
  PauseCircle,
  Layers,
  Split,
  Merge,
  GitBranch,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { AGENT_ROLES, type AgentRoleInfo } from '@/types/workflow-builder';

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

interface AgentPaletteItemProps {
  roleInfo: AgentRoleInfo;
}

function AgentPaletteItem({ roleInfo }: AgentPaletteItemProps) {
  const Icon = iconMap[roleInfo.icon] || ClipboardList;

  const onDragStart = (event: DragEvent<HTMLDivElement>) => {
    event.dataTransfer.setData('application/reactflow', roleInfo.role);
    event.dataTransfer.setData('application/reactflow-type', 'agent');
    event.dataTransfer.effectAllowed = 'move';
  };

  return (
    <div
      draggable
      onDragStart={onDragStart}
      className={cn(
        'flex cursor-grab items-center gap-3 rounded-lg border-2 bg-card p-3 transition-all',
        'hover:shadow-md hover:scale-[1.02] active:cursor-grabbing'
      )}
      style={{ borderColor: roleInfo.color }}
    >
      <div
        className="flex h-8 w-8 items-center justify-center rounded-md"
        style={{ backgroundColor: roleInfo.color }}
      >
        <Icon className="h-4 w-4 text-white" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-foreground">{roleInfo.label}</p>
        <p className="text-xs text-muted-foreground truncate">{roleInfo.description}</p>
      </div>
    </div>
  );
}

interface UtilityNodeInfo {
  type: 'shell' | 'checkpoint';
  label: string;
  description: string;
  color: string;
  Icon: React.ComponentType<{ className?: string }>;
}

interface ParallelNodeInfo {
  type: 'parallel' | 'fan_out' | 'fan_in' | 'map_reduce';
  label: string;
  description: string;
  color: string;
  Icon: React.ComponentType<{ className?: string }>;
}

const UTILITY_NODES: UtilityNodeInfo[] = [
  {
    type: 'shell',
    label: 'Shell Command',
    description: 'Execute a shell command',
    color: '#27272a', // zinc-800
    Icon: Terminal,
  },
  {
    type: 'checkpoint',
    label: 'Checkpoint',
    description: 'Pause for review/resume',
    color: '#f59e0b', // amber-500
    Icon: PauseCircle,
  },
];

const PARALLEL_NODES: ParallelNodeInfo[] = [
  {
    type: 'parallel',
    label: 'Parallel Group',
    description: 'Run steps concurrently',
    color: '#8b5cf6', // violet-500
    Icon: Layers,
  },
  {
    type: 'fan_out',
    label: 'Fan Out',
    description: 'Scatter items to parallel tasks',
    color: '#06b6d4', // cyan-500
    Icon: Split,
  },
  {
    type: 'fan_in',
    label: 'Fan In',
    description: 'Gather and aggregate results',
    color: '#14b8a6', // teal-500
    Icon: Merge,
  },
  {
    type: 'map_reduce',
    label: 'Map-Reduce',
    description: 'Map over items, then reduce',
    color: '#f97316', // orange-500
    Icon: GitBranch,
  },
];

interface UtilityPaletteItemProps {
  node: UtilityNodeInfo;
}

function UtilityPaletteItem({ node }: UtilityPaletteItemProps) {
  const { type, label, description, color, Icon } = node;

  const onDragStart = (event: DragEvent<HTMLDivElement>) => {
    event.dataTransfer.setData('application/reactflow', type);
    event.dataTransfer.setData('application/reactflow-type', type);
    event.dataTransfer.effectAllowed = 'move';
  };

  return (
    <div
      draggable
      onDragStart={onDragStart}
      className={cn(
        'flex cursor-grab items-center gap-3 rounded-lg border-2 bg-card p-3 transition-all',
        'hover:shadow-md hover:scale-[1.02] active:cursor-grabbing'
      )}
      style={{ borderColor: color }}
    >
      <div
        className="flex h-8 w-8 items-center justify-center rounded-md"
        style={{ backgroundColor: color }}
      >
        <Icon className={cn('h-4 w-4', type === 'shell' ? 'text-green-400' : 'text-white')} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-foreground">{label}</p>
        <p className="text-xs text-muted-foreground truncate">{description}</p>
      </div>
    </div>
  );
}

interface ParallelPaletteItemProps {
  node: ParallelNodeInfo;
}

function ParallelPaletteItem({ node }: ParallelPaletteItemProps) {
  const { type, label, description, color, Icon } = node;

  const onDragStart = (event: DragEvent<HTMLDivElement>) => {
    event.dataTransfer.setData('application/reactflow', type);
    event.dataTransfer.setData('application/reactflow-type', type);
    event.dataTransfer.effectAllowed = 'move';
  };

  return (
    <div
      draggable
      onDragStart={onDragStart}
      className={cn(
        'flex cursor-grab items-center gap-3 rounded-lg border-2 bg-card p-3 transition-all',
        'hover:shadow-md hover:scale-[1.02] active:cursor-grabbing'
      )}
      style={{ borderColor: color }}
    >
      <div
        className="flex h-8 w-8 items-center justify-center rounded-md"
        style={{ backgroundColor: color }}
      >
        <Icon className="h-4 w-4 text-white" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-foreground">{label}</p>
        <p className="text-xs text-muted-foreground truncate">{description}</p>
      </div>
    </div>
  );
}

export function NodePalette() {
  return (
    <div className="h-full w-64 border-r bg-card p-4 overflow-y-auto">
      {/* Agents Section */}
      <div className="mb-4">
        <h2 className="text-lg font-semibold text-foreground">Agents</h2>
        <p className="text-sm text-muted-foreground">Drag to add to canvas</p>
      </div>
      <div className="space-y-2">
        {AGENT_ROLES.map((roleInfo) => (
          <AgentPaletteItem key={roleInfo.role} roleInfo={roleInfo} />
        ))}
      </div>

      {/* Parallel Section */}
      <div className="mt-6 mb-4">
        <h2 className="text-lg font-semibold text-foreground">Parallel</h2>
        <p className="text-sm text-muted-foreground">Concurrent execution</p>
      </div>
      <div className="space-y-2">
        {PARALLEL_NODES.map((node) => (
          <ParallelPaletteItem key={node.type} node={node} />
        ))}
      </div>

      {/* Utilities Section */}
      <div className="mt-6 mb-4">
        <h2 className="text-lg font-semibold text-foreground">Utilities</h2>
        <p className="text-sm text-muted-foreground">Commands & control flow</p>
      </div>
      <div className="space-y-2">
        {UTILITY_NODES.map((node) => (
          <UtilityPaletteItem key={node.type} node={node} />
        ))}
      </div>
    </div>
  );
}
