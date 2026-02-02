import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Suspense, lazy } from 'react';
import { ThemeProvider } from '@/components/ThemeProvider';
import { Layout } from '@/components/Layout';
import { LoadingSpinner } from '@/components/ui/loading-spinner';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import { Toaster } from '@/components/ui/toaster';

// Eager load primary pages
import { DashboardPage } from '@/pages/Dashboard';
import { WorkflowsPage } from '@/pages/Workflows';
import { ChatPage } from '@/pages/Chat';

// Lazy load heavy/secondary pages for code splitting
const WorkflowBuilderPage = lazy(() => import('@/pages/WorkflowBuilder').then(m => ({ default: m.WorkflowBuilderPage })));
const ExecutionsPage = lazy(() => import('@/pages/Executions').then(m => ({ default: m.ExecutionsPage })));
const DecisionsPage = lazy(() => import('@/pages/Decisions').then(m => ({ default: m.DecisionsPage })));
const BudgetPage = lazy(() => import('@/pages/Budget').then(m => ({ default: m.BudgetPage })));
const ConnectorsPage = lazy(() => import('@/pages/Connectors').then(m => ({ default: m.ConnectorsPage })));
const SettingsPage = lazy(() => import('@/pages/Settings').then(m => ({ default: m.SettingsPage })));
const AgentsPage = lazy(() => import('@/pages/Agents').then(m => ({ default: m.AgentsPage })));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60, // 1 minute
      retry: 1,
    },
  },
});

function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <ThemeProvider>
          <BrowserRouter>
            <Suspense fallback={<LoadingSpinner fullScreen />}>
              <Routes>
                <Route path="/" element={<Layout />}>
                  <Route index element={<DashboardPage />} />
                  <Route path="chat" element={<ChatPage />} />
                  <Route path="decisions" element={<DecisionsPage />} />
                  <Route path="workflows" element={<WorkflowsPage />} />
                  <Route path="workflows/new" element={<WorkflowBuilderPage />} />
                  <Route path="workflows/:id/edit" element={<WorkflowBuilderPage />} />
                  <Route path="executions" element={<ExecutionsPage />} />
                  <Route path="budget" element={<BudgetPage />} />
                  <Route path="connectors" element={<ConnectorsPage />} />
                  <Route path="settings" element={<SettingsPage />} />
                  <Route path="agents" element={<AgentsPage />} />
                </Route>
              </Routes>
            </Suspense>
            <Toaster />
          </BrowserRouter>
        </ThemeProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}

export default App;
