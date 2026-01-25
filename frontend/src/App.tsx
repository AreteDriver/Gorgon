import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from '@/components/ThemeProvider';
import { Layout } from '@/components/Layout';
import { DashboardPage } from '@/pages/Dashboard';
import { WorkflowsPage } from '@/pages/Workflows';
import { WorkflowBuilderPage } from '@/pages/WorkflowBuilder';
import { ExecutionsPage } from '@/pages/Executions';
import { DecisionsPage } from '@/pages/Decisions';
import { BudgetPage } from '@/pages/Budget';
import { ConnectorsPage } from '@/pages/Connectors';
import { SettingsPage } from '@/pages/Settings';
import { AgentsPage } from '@/pages/Agents';

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
      </BrowserRouter>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

export default App;
