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

interface PaletteItemProps {
  roleInfo: AgentRoleInfo;
}

function PaletteItem({ roleInfo }: PaletteItemProps) {
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

export function NodePalette() {
  return (
    <div className="h-full w-64 border-r bg-card p-4 overflow-y-auto">
      <div className="mb-4">
        <h2 className="text-lg font-semibold text-foreground">Agents</h2>
        <p className="text-sm text-muted-foreground">Drag to add to canvas</p>
      </div>
      <div className="space-y-2">
        {AGENT_ROLES.map((roleInfo) => (
          <PaletteItem key={roleInfo.role} roleInfo={roleInfo} />
        ))}
      </div>
    </div>
  );
}
