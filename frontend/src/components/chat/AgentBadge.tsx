import { cn } from '@/lib/utils';
import { getAgentDisplay } from '@/types/chat';

interface AgentBadgeProps {
  agent: string;
  className?: string;
}

export function AgentBadge({ agent, className }: AgentBadgeProps) {
  const display = getAgentDisplay(agent);

  if (!display) return null;

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium',
        display.color,
        'text-white',
        className
      )}
    >
      <span>{display.icon}</span>
      <span>{display.name}</span>
    </span>
  );
}
