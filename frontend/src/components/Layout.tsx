import { Outlet } from 'react-router-dom';
import { Sidebar } from '@/components/Sidebar';
import { KeyboardShortcutsHelp } from '@/components/KeyboardShortcutsHelp';
import { useUIStore } from '@/stores';
import { cn } from '@/lib/utils';

export function Layout() {
  const { sidebarOpen } = useUIStore();

  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <main
        className={cn(
          'min-h-screen transition-all duration-300',
          sidebarOpen ? 'ml-64' : 'ml-16'
        )}
      >
        <div className="container py-6">
          <Outlet />
        </div>
      </main>
      <KeyboardShortcutsHelp />
    </div>
  );
}
