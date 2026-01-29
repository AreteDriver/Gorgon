import {
  Wallet,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  Plus,
  Settings,
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
  PieChart,
  Pie,
  Cell,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Skeleton } from '@/components/ui/skeleton';
import { useBudgetSummary, useBudgets, useDailyUsage } from '@/hooks/useApi';
import { formatCurrency, formatTokens, getAgentColor } from '@/lib/utils';

export function BudgetPage() {
  const { data: budgetSummary, isLoading: summaryLoading } = useBudgetSummary();
  const { data: budgets, isLoading: budgetsLoading } = useBudgets();
  const { data: dailyUsageData, isLoading: dailyLoading } = useDailyUsage(7);

  const isLoading = summaryLoading || budgetsLoading;

  // Calculate totals from budget summary or budgets
  const totalBudget = budgetSummary?.totalBudget ?? 0;
  const totalUsed = budgetSummary?.totalUsed ?? 0;
  const totalRemaining = budgetSummary?.totalRemaining ?? 0;
  const percentUsed = totalBudget > 0 ? (totalUsed / totalBudget) * 100 : 0;

  // Transform usage by agent into chart data
  const agentCosts = budgetSummary?.usageByAgent
    ? Object.entries(budgetSummary.usageByAgent).map(([name, cost]) => ({
        name: name.charAt(0).toUpperCase() + name.slice(1),
        cost: cost as number,
        color: getAgentColor(name.toLowerCase()),
      }))
    : [];

  // Calculate today's and this week's spend from daily usage
  const todaySpend = dailyUsageData?.[dailyUsageData.length - 1]?.cost ?? 0;
  const todayTokens = dailyUsageData?.[dailyUsageData.length - 1]?.tokens ?? 0;
  const weekSpend = dailyUsageData?.reduce((sum, d) => sum + d.cost, 0) ?? 0;

  // Generate budget alerts from budgets data
  const budgetAlerts = (budgets ?? [])
    .filter((b) => b.limit > 0 && (b.used / b.limit) * 100 >= 40)
    .map((b) => ({
      agent: b.name,
      usage: Math.round((b.used / b.limit) * 100),
      limit: b.limit,
      message: `At ${Math.round((b.used / b.limit) * 100)}% of ${b.period} limit`,
    }));

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Budget</h1>
          <p className="text-muted-foreground">Track spending and manage cost limits</p>
        </div>
        <Button>
          <Settings className="mr-2 h-4 w-4" />
          Configure Limits
        </Button>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Monthly Budget</CardTitle>
            <Wallet className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <>
                <Skeleton className="h-8 w-20 mb-2" />
                <Skeleton className="h-2 w-full mb-1" />
                <Skeleton className="h-3 w-24" />
              </>
            ) : totalBudget === 0 ? (
              <p className="text-sm text-muted-foreground py-2">No budget configured</p>
            ) : (
              <>
                <div className="text-2xl font-bold">{formatCurrency(totalBudget)}</div>
                <Progress value={percentUsed} className="mt-2 h-2" />
                <p className="mt-1 text-xs text-muted-foreground">
                  {formatCurrency(totalUsed)} used ({percentUsed.toFixed(1)}%)
                </p>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Today's Spend</CardTitle>
            <TrendingUp className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            {dailyLoading ? (
              <>
                <Skeleton className="h-8 w-16 mb-1" />
                <Skeleton className="h-3 w-20" />
              </>
            ) : (
              <>
                <div className="text-2xl font-bold">{formatCurrency(todaySpend)}</div>
                <p className="text-xs text-muted-foreground">
                  {formatTokens(todayTokens)} tokens
                </p>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">This Week</CardTitle>
            <TrendingDown className="h-4 w-4 text-blue-500" />
          </CardHeader>
          <CardContent>
            {dailyLoading ? (
              <>
                <Skeleton className="h-8 w-16 mb-1" />
                <Skeleton className="h-3 w-24" />
              </>
            ) : (
              <>
                <div className="text-2xl font-bold">{formatCurrency(weekSpend)}</div>
                <p className="text-xs text-muted-foreground">Past 7 days</p>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Remaining</CardTitle>
            <Wallet className="h-4 w-4 text-emerald-500" />
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <>
                <Skeleton className="h-8 w-16 mb-1" />
                <Skeleton className="h-3 w-20" />
              </>
            ) : totalBudget === 0 ? (
              <p className="text-sm text-muted-foreground py-2">--</p>
            ) : (
              <>
                <div className="text-2xl font-bold">{formatCurrency(totalRemaining)}</div>
                <p className="text-xs text-muted-foreground">This period</p>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Alerts */}
      {!isLoading && budgetAlerts.length > 0 && (
        <Card className="border-yellow-500/50 bg-yellow-500/5">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-yellow-600">
              <AlertTriangle className="h-5 w-5" />
              Budget Alerts
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {budgetAlerts.map((alert, idx) => (
                <div key={idx} className="flex items-center justify-between rounded-lg bg-background p-3">
                  <div>
                    <span className="font-medium">{alert.agent}</span>
                    <span className="text-muted-foreground"> - {alert.message}</span>
                  </div>
                  <span className="text-sm font-medium text-yellow-600">{alert.usage}% used</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Charts */}
      <div className="grid gap-4 md:grid-cols-2">
        {/* Spending Over Time */}
        <Card>
          <CardHeader>
            <CardTitle>Daily Spending</CardTitle>
            <CardDescription>Cost trend over the past week</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-[300px]">
              {dailyLoading ? (
                <div className="flex h-full items-center justify-center">
                  <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                </div>
              ) : !dailyUsageData || dailyUsageData.length === 0 ? (
                <div className="flex h-full items-center justify-center text-muted-foreground">
                  No spending data available
                </div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={dailyUsageData}>
                    <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                    <XAxis dataKey="date" className="text-xs" />
                    <YAxis className="text-xs" tickFormatter={(v) => `$${v}`} />
                    <Tooltip
                      formatter={(value: number, name: string) => [
                        name === 'cost' ? formatCurrency(value) : formatTokens(value),
                        name === 'cost' ? 'Cost' : 'Tokens',
                      ]}
                      contentStyle={{
                        backgroundColor: 'hsl(var(--card))',
                        border: '1px solid hsl(var(--border))',
                        borderRadius: '8px',
                      }}
                    />
                    <Line
                      type="monotone"
                      dataKey="cost"
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

        {/* Cost by Agent */}
        <Card>
          <CardHeader>
            <CardTitle>Cost by Agent</CardTitle>
            <CardDescription>Monthly spending distribution</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-[300px]">
              {summaryLoading ? (
                <div className="flex h-full items-center justify-center">
                  <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                </div>
              ) : agentCosts.length === 0 ? (
                <div className="flex h-full items-center justify-center text-muted-foreground">
                  No agent usage data available
                </div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={agentCosts}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={100}
                      paddingAngle={2}
                      dataKey="cost"
                    >
                      {agentCosts.map((entry, idx) => (
                        <Cell key={idx} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip
                      formatter={(value: number) => [formatCurrency(value), 'Cost']}
                      contentStyle={{
                        backgroundColor: 'hsl(var(--card))',
                        border: '1px solid hsl(var(--border))',
                        borderRadius: '8px',
                      }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              )}
            </div>
            {/* Legend */}
            {agentCosts.length > 0 && (
              <div className="mt-4 flex flex-wrap justify-center gap-4">
                {agentCosts.map((agent) => (
                  <div key={agent.name} className="flex items-center gap-2">
                    <div className="h-3 w-3 rounded-full" style={{ backgroundColor: agent.color }} />
                    <span className="text-sm">{agent.name}</span>
                    <span className="text-sm text-muted-foreground">{formatCurrency(agent.cost)}</span>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Per-Agent Budgets */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Agent Budgets</CardTitle>
              <CardDescription>Individual limits per agent role</CardDescription>
            </div>
            <Button variant="outline" size="sm">
              <Plus className="mr-2 h-4 w-4" />
              Add Limit
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {budgetsLoading ? (
            <div className="space-y-4">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Skeleton className="h-4 w-24" />
                    <Skeleton className="h-4 w-20" />
                  </div>
                  <Skeleton className="h-2 w-full" />
                </div>
              ))}
            </div>
          ) : !budgets || budgets.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">
              No agent budgets configured. Click "Add Limit" to create one.
            </p>
          ) : (
            <div className="space-y-4">
              {budgets.map((item) => (
                <div key={item.id} className="space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div
                        className="h-3 w-3 rounded-full"
                        style={{ backgroundColor: getAgentColor(item.name.toLowerCase()) }}
                      />
                      <span className="font-medium">{item.name}</span>
                      <span className="text-xs text-muted-foreground">({item.period})</span>
                    </div>
                    <div className="text-sm">
                      <span className="font-medium">{formatCurrency(item.used)}</span>
                      <span className="text-muted-foreground"> / {formatCurrency(item.limit)}</span>
                    </div>
                  </div>
                  <Progress value={item.limit > 0 ? (item.used / item.limit) * 100 : 0} className="h-2" />
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
