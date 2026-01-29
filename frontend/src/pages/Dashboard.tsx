import {
  Activity,
  CheckCircle,
  XCircle,
  Coins,
  Zap,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
} from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import {
  useDashboardStats,
  useRecentExecutions,
  useDailyUsage,
  useAgentUsage,
  useDashboardBudget,
} from '@/hooks/useApi';
import { formatCurrency, formatTokens, getStatusColor } from '@/lib/utils';

// Mock data fallbacks
const mockUsageData = [
  { date: 'Mon', tokens: 45000, cost: 1.23 },
  { date: 'Tue', tokens: 52000, cost: 1.45 },
  { date: 'Wed', tokens: 38000, cost: 1.02 },
  { date: 'Thu', tokens: 61000, cost: 1.78 },
  { date: 'Fri', tokens: 55000, cost: 1.56 },
  { date: 'Sat', tokens: 32000, cost: 0.89 },
  { date: 'Sun', tokens: 48000, cost: 1.34 },
];

const mockAgentUsage = [
  { agent: 'Planner', tokens: 15000 },
  { agent: 'Builder', tokens: 45000 },
  { agent: 'Tester', tokens: 25000 },
  { agent: 'Reviewer', tokens: 18000 },
  { agent: 'Documenter', tokens: 12000 },
];

const mockRecentExecutions = [
  { id: '1', name: 'Feature Analysis', status: 'completed', time: '2 min ago' },
  { id: '2', name: 'Code Review', status: 'running', time: '5 min ago' },
  { id: '3', name: 'Documentation', status: 'completed', time: '15 min ago' },
  { id: '4', name: 'Test Generation', status: 'failed', time: '1 hour ago' },
  { id: '5', name: 'Architecture Review', status: 'completed', time: '2 hours ago' },
];

const mockBudgetData = {
  totalBudget: 100,
  totalUsed: 42.5,
  percentUsed: 42.5,
  byAgent: [
    { agent: 'Builder', used: 18.5, limit: 40 },
    { agent: 'Planner', used: 8.2, limit: 20 },
    { agent: 'Reviewer', used: 12.3, limit: 25 },
    { agent: 'Tester', used: 3.5, limit: 15 },
  ],
  alert: 'Builder agent at 46% of monthly limit',
};

const mockStats = {
  totalWorkflows: 12,
  activeExecutions: 3,
  completedToday: 8,
  failedToday: 1,
  totalTokensToday: 156000,
  totalCostToday: 4.23,
};

export function DashboardPage() {
  const { data: stats } = useDashboardStats();
  const { data: recentExecutions } = useRecentExecutions(5);
  const { data: dailyUsage } = useDailyUsage(7);
  const { data: agentUsage } = useAgentUsage();
  const { data: budgetData } = useDashboardBudget();

  // Use API data with mock fallback
  const displayStats = stats || mockStats;
  const displayRecentExecutions = recentExecutions || mockRecentExecutions;
  const displayDailyUsage = dailyUsage || mockUsageData;
  const displayAgentUsage = agentUsage || mockAgentUsage;
  const displayBudget = budgetData || mockBudgetData;

  // Calculate budget trend (positive = under budget)
  const budgetRemaining = displayBudget.totalBudget - displayBudget.totalUsed;
  const isUnderBudget = budgetRemaining > 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold">Dashboard</h1>
        <p className="text-muted-foreground">
          Monitor your AI agent workflows and resource usage
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Active Executions</CardTitle>
            <Activity className="h-4 w-4 text-blue-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{displayStats.activeExecutions}</div>
            <p className="text-xs text-muted-foreground">
              {displayStats.totalWorkflows} total workflows
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Completed Today</CardTitle>
            <CheckCircle className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{displayStats.completedToday}</div>
            <div className="flex items-center gap-1 text-xs text-muted-foreground">
              {displayStats.failedToday > 0 && (
                <>
                  <XCircle className="h-3 w-3 text-red-500" />
                  <span>{displayStats.failedToday} failed</span>
                </>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Tokens Today</CardTitle>
            <Zap className="h-4 w-4 text-yellow-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {formatTokens(displayStats.totalTokensToday)}
            </div>
            <p className="text-xs text-muted-foreground">
              Across all agents
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Cost Today</CardTitle>
            <Coins className="h-4 w-4 text-emerald-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {formatCurrency(displayStats.totalCostToday)}
            </div>
            <div className="flex items-center gap-1 text-xs">
              {isUnderBudget ? (
                <>
                  <TrendingUp className="h-3 w-3 text-green-600" />
                  <span className="text-green-600">
                    {Math.round(100 - displayBudget.percentUsed)}% under budget
                  </span>
                </>
              ) : (
                <>
                  <TrendingDown className="h-3 w-3 text-red-600" />
                  <span className="text-red-600">Over budget</span>
                </>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Charts Row */}
      <div className="grid gap-4 md:grid-cols-2">
        {/* Token Usage Chart */}
        <Card>
          <CardHeader>
            <CardTitle>Token Usage</CardTitle>
            <CardDescription>Daily token consumption over the past week</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-[250px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={displayDailyUsage}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis dataKey="date" className="text-xs" />
                  <YAxis className="text-xs" tickFormatter={(v) => formatTokens(v)} />
                  <Tooltip
                    formatter={(value: number) => [formatTokens(value), 'Tokens']}
                    contentStyle={{
                      backgroundColor: 'hsl(var(--card))',
                      border: '1px solid hsl(var(--border))',
                      borderRadius: '8px',
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="tokens"
                    stroke="hsl(var(--primary))"
                    strokeWidth={2}
                    dot={{ fill: 'hsl(var(--primary))' }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Agent Usage Chart */}
        <Card>
          <CardHeader>
            <CardTitle>Usage by Agent</CardTitle>
            <CardDescription>Token distribution across agent roles</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-[250px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={displayAgentUsage} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis type="number" tickFormatter={(v) => formatTokens(v)} />
                  <YAxis dataKey="agent" type="category" width={80} />
                  <Tooltip
                    formatter={(value: number) => [formatTokens(value), 'Tokens']}
                    contentStyle={{
                      backgroundColor: 'hsl(var(--card))',
                      border: '1px solid hsl(var(--border))',
                      borderRadius: '8px',
                    }}
                  />
                  <Bar dataKey="tokens" fill="hsl(var(--primary))" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Recent Executions & Budget */}
      <div className="grid gap-4 md:grid-cols-2">
        {/* Recent Executions */}
        <Card>
          <CardHeader>
            <CardTitle>Recent Executions</CardTitle>
            <CardDescription>Latest workflow runs</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {displayRecentExecutions.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-4">
                  No recent executions
                </p>
              ) : (
                displayRecentExecutions.map((exec) => (
                  <div key={exec.id} className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div
                        className="h-2 w-2 rounded-full"
                        style={{ backgroundColor: getStatusColor(exec.status) }}
                      />
                      <div>
                        <p className="text-sm font-medium">{exec.name}</p>
                        <p className="text-xs text-muted-foreground">{exec.time}</p>
                      </div>
                    </div>
                    <Badge
                      variant={
                        exec.status === 'completed'
                          ? 'success'
                          : exec.status === 'failed'
                          ? 'destructive'
                          : 'secondary'
                      }
                    >
                      {exec.status}
                    </Badge>
                  </div>
                ))
              )}
            </div>
          </CardContent>
        </Card>

        {/* Budget Status */}
        <Card>
          <CardHeader>
            <CardTitle>Budget Status</CardTitle>
            <CardDescription>Monthly spending limits</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-6">
              {/* Overall Budget */}
              <div>
                <div className="mb-2 flex items-center justify-between text-sm">
                  <span>Monthly Budget</span>
                  <span className="font-medium">
                    {formatCurrency(displayBudget.totalUsed)} / {formatCurrency(displayBudget.totalBudget)}
                  </span>
                </div>
                <Progress value={displayBudget.percentUsed} className="h-2" />
              </div>

              {/* Per-Agent Budgets */}
              <div className="space-y-3">
                <p className="text-sm font-medium">By Agent</p>
                {displayBudget.byAgent.map((item) => (
                  <div key={item.agent} className="space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <span>{item.agent}</span>
                      <span className="text-muted-foreground">
                        {formatCurrency(item.used)} / {formatCurrency(item.limit)}
                      </span>
                    </div>
                    <Progress value={(item.used / item.limit) * 100} className="h-1" />
                  </div>
                ))}
              </div>

              {/* Alerts */}
              {displayBudget.alert && (
                <div className="rounded-lg bg-yellow-500/10 p-3">
                  <div className="flex items-center gap-2 text-sm text-yellow-600">
                    <AlertTriangle className="h-4 w-4" />
                    <span>{displayBudget.alert}</span>
                  </div>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
