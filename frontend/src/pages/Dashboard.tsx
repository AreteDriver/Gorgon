import {
  Activity,
  CheckCircle,
  XCircle,
  Coins,
  Zap,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  Loader2,
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
import { Skeleton } from '@/components/ui/skeleton';
import {
  useDashboardStats,
  useRecentExecutions,
  useDailyUsage,
  useAgentUsage,
  useDashboardBudget,
} from '@/hooks/useApi';
import { formatCurrency, formatTokens, getStatusColor } from '@/lib/utils';

// Default empty state values
const emptyStats = {
  totalWorkflows: 0,
  activeExecutions: 0,
  completedToday: 0,
  failedToday: 0,
  totalTokensToday: 0,
  totalCostToday: 0,
};

const emptyBudget = {
  totalBudget: 0,
  totalUsed: 0,
  percentUsed: 0,
  byAgent: [],
  alert: undefined,
};

export function DashboardPage() {
  const { data: stats, isLoading: statsLoading } = useDashboardStats();
  const { data: recentExecutions, isLoading: executionsLoading } = useRecentExecutions(5);
  const { data: dailyUsage, isLoading: dailyUsageLoading } = useDailyUsage(7);
  const { data: agentUsage, isLoading: agentUsageLoading } = useAgentUsage();
  const { data: budgetData, isLoading: budgetLoading } = useDashboardBudget();

  // Use API data with empty state fallback
  const displayStats = stats || emptyStats;
  const displayRecentExecutions = recentExecutions || [];
  const displayDailyUsage = dailyUsage || [];
  const displayAgentUsage = agentUsage || [];
  const displayBudget = budgetData || emptyBudget;

  // Calculate budget trend (positive = under budget)
  const budgetRemaining = displayBudget.totalBudget - displayBudget.totalUsed;
  const isUnderBudget = budgetRemaining >= 0;

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
            {statsLoading ? (
              <Skeleton className="h-8 w-16" />
            ) : (
              <>
                <div className="text-2xl font-bold">{displayStats.activeExecutions}</div>
                <p className="text-xs text-muted-foreground">
                  {displayStats.totalWorkflows} total workflows
                </p>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Completed Today</CardTitle>
            <CheckCircle className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            {statsLoading ? (
              <Skeleton className="h-8 w-16" />
            ) : (
              <>
                <div className="text-2xl font-bold">{displayStats.completedToday}</div>
                <div className="flex items-center gap-1 text-xs text-muted-foreground">
                  {displayStats.failedToday > 0 && (
                    <>
                      <XCircle className="h-3 w-3 text-red-500" />
                      <span>{displayStats.failedToday} failed</span>
                    </>
                  )}
                </div>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Tokens Today</CardTitle>
            <Zap className="h-4 w-4 text-yellow-500" />
          </CardHeader>
          <CardContent>
            {statsLoading ? (
              <Skeleton className="h-8 w-20" />
            ) : (
              <>
                <div className="text-2xl font-bold">
                  {formatTokens(displayStats.totalTokensToday)}
                </div>
                <p className="text-xs text-muted-foreground">
                  Across all agents
                </p>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Cost Today</CardTitle>
            <Coins className="h-4 w-4 text-emerald-500" />
          </CardHeader>
          <CardContent>
            {statsLoading || budgetLoading ? (
              <Skeleton className="h-8 w-16" />
            ) : (
              <>
                <div className="text-2xl font-bold">
                  {formatCurrency(displayStats.totalCostToday)}
                </div>
                <div className="flex items-center gap-1 text-xs">
                  {displayBudget.totalBudget > 0 ? (
                    isUnderBudget ? (
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
                    )
                  ) : (
                    <span className="text-muted-foreground">No budget set</span>
                  )}
                </div>
              </>
            )}
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
              {dailyUsageLoading ? (
                <div className="flex h-full items-center justify-center">
                  <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                </div>
              ) : displayDailyUsage.length === 0 ? (
                <div className="flex h-full items-center justify-center text-muted-foreground">
                  No usage data available
                </div>
              ) : (
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
              )}
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
              {agentUsageLoading ? (
                <div className="flex h-full items-center justify-center">
                  <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                </div>
              ) : displayAgentUsage.length === 0 ? (
                <div className="flex h-full items-center justify-center text-muted-foreground">
                  No agent usage data available
                </div>
              ) : (
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
              )}
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
              {executionsLoading ? (
                <div className="space-y-3">
                  {[1, 2, 3].map((i) => (
                    <div key={i} className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <Skeleton className="h-2 w-2 rounded-full" />
                        <div>
                          <Skeleton className="h-4 w-32 mb-1" />
                          <Skeleton className="h-3 w-16" />
                        </div>
                      </div>
                      <Skeleton className="h-5 w-20" />
                    </div>
                  ))}
                </div>
              ) : displayRecentExecutions.length === 0 ? (
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
            {budgetLoading ? (
              <div className="space-y-6">
                <div>
                  <Skeleton className="h-4 w-full mb-2" />
                  <Skeleton className="h-2 w-full" />
                </div>
                <div className="space-y-3">
                  <Skeleton className="h-4 w-24" />
                  {[1, 2, 3].map((i) => (
                    <div key={i} className="space-y-1">
                      <Skeleton className="h-3 w-full" />
                      <Skeleton className="h-1 w-full" />
                    </div>
                  ))}
                </div>
              </div>
            ) : displayBudget.totalBudget === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-4">
                No budget configured
              </p>
            ) : (
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
                {displayBudget.byAgent.length > 0 && (
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
                        <Progress value={item.limit > 0 ? (item.used / item.limit) * 100 : 0} className="h-1" />
                      </div>
                    ))}
                  </div>
                )}

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
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
