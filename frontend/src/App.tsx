import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from '@/components/ThemeProvider';
import { Layout } from '@/components/Layout';
import { DashboardPage } from '@/pages/Dashboard';
import { WorkflowsPage } from '@/pages/Workflows';
import { ExecutionsPage } from '@/pages/Executions';
import { BudgetPage } from '@/pages/Budget';
import { ConnectorsPage } from '@/pages/Connectors';

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
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<DashboardPage />} />
            <Route path="workflows" element={<WorkflowsPage />} />
            <Route path="executions" element={<ExecutionsPage />} />
            <Route path="budget" element={<BudgetPage />} />
            <Route path="connectors" element={<ConnectorsPage />} />
            {/* Placeholder routes */}
            <Route path="agents" element={<PlaceholderPage title="Agents" />} />
            <Route path="settings" element={<PlaceholderPage title="Settings" />} />
          </Route>
        </Routes>
      </BrowserRouter>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

function PlaceholderPage({ title }: { title: string }) {
  return (
    <div className="flex h-[50vh] items-center justify-center">
      <div className="text-center">
        <h1 className="text-2xl font-bold">{title}</h1>
        <p className="text-muted-foreground">Coming soon...</p>
      </div>
    </div>
  );
}

export default App;
