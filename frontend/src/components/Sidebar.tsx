import { Link, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  GitBranch,
  Play,
  Users,
  Wallet,
  Settings,
  ChevronLeft,
  ChevronRight,
  Zap,
  Plug,
  Lightbulb,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { ThemeToggle } from '@/components/ThemeToggle';
import { useUIStore } from '@/stores';

interface NavItem {
  title: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
}

const navItems: NavItem[] = [
  { title: 'Dashboard', href: '/', icon: LayoutDashboard },
  { title: 'Decisions', href: '/decisions', icon: Lightbulb },
  { title: 'Workflows', href: '/workflows', icon: GitBranch },
  { title: 'Executions', href: '/executions', icon: Play },
  { title: 'Connectors', href: '/connectors', icon: Plug },
  { title: 'Agents', href: '/agents', icon: Users },
  { title: 'Budget', href: '/budget', icon: Wallet },
  { title: 'Settings', href: '/settings', icon: Settings },
];

export function Sidebar() {
  const location = useLocation();
  const { sidebarOpen, toggleSidebar } = useUIStore();

  return (
    <aside
      className={cn(
        'fixed left-0 top-0 z-40 h-screen border-r bg-background transition-all duration-300',
        sidebarOpen ? 'w-64' : 'w-16'
      )}
    >
      {/* Logo */}
      <div className="flex h-16 items-center justify-between border-b px-4">
        <Link to="/" className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
            <Zap className="h-5 w-5 text-primary-foreground" />
          </div>
          {sidebarOpen && (
            <span className="text-lg font-bold">Gorgon</span>
          )}
        </Link>
        <Button
          variant="ghost"
          size="icon"
          onClick={toggleSidebar}
          className="h-8 w-8"
        >
          {sidebarOpen ? (
            <ChevronLeft className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
        </Button>
      </div>

      {/* Navigation */}
      <nav className="flex flex-col gap-1 p-2">
        {navItems.map((item) => {
          const isActive = location.pathname === item.href;
          return (
            <Link
              key={item.href}
              to={item.href}
              className={cn(
                'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground',
                !sidebarOpen && 'justify-center px-2'
              )}
            >
              <item.icon className="h-5 w-5 shrink-0" />
              {sidebarOpen && <span>{item.title}</span>}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className={cn('absolute bottom-4 left-2 right-2', !sidebarOpen && 'left-2 right-2')}>
        <ThemeToggle collapsed={!sidebarOpen} />
        {sidebarOpen && (
          <div className="mt-2 rounded-lg bg-muted p-3 text-xs text-muted-foreground">
            <p className="font-medium">Gorgon v0.1.0</p>
            <p>Multi-Agent Orchestration</p>
          </div>
        )}
      </div>
    </aside>
  );
}
