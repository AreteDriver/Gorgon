import { useState } from 'react';
import {
  Lightbulb,
  Play,
  Loader2,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  AlertCircle,
  FileText,
  RotateCcw,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { useStartYAMLExecution } from '@/hooks/useApi';
import { cn } from '@/lib/utils';

// Result type from YAML workflow execution
interface YAMLWorkflowResult {
  id: string;
  workflow_id: string;
  workflow_name: string;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  total_duration_ms: number;
  total_tokens: number;
  outputs: Record<string, string>;
  steps: Array<{
    step_id: string;
    status: string;
    duration_ms: number;
    tokens_used: number;
  }>;
  error: string | null;
}

// Decision workflow ID
const DECISION_WORKFLOW_ID = 'decision-support';

interface DecisionInput {
  decision_question: string;
  context: string;
  stakeholders: 'executive' | 'technical' | 'team' | 'general';
  urgency: 'low' | 'normal' | 'high' | 'critical';
}

// Steps in the decision workflow
const DECISION_STEPS = [
  { id: 'analyze_situation', name: 'Analyze Situation', description: 'Understanding the decision context' },
  { id: 'generate_options', name: 'Generate Options', description: 'Creating alternative solutions' },
  { id: 'checkpoint_options_review', name: 'Review Options', description: 'Checkpoint for human review' },
  { id: 'generate_recommendation', name: 'Generate Recommendation', description: 'Synthesizing final recommendation' },
  { id: 'create_audit_trail', name: 'Create Audit Trail', description: 'Documenting decision process' },
];

export function DecisionsPage() {
  const [formData, setFormData] = useState<DecisionInput>({
    decision_question: '',
    context: '',
    stakeholders: 'technical',
    urgency: 'normal',
  });
  const [execution, setExecution] = useState<YAMLWorkflowResult | null>(null);
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    recommendation: true,
  });

  const startExecution = useStartYAMLExecution();

  const isRunning = startExecution.isPending;
  const isCompleted = execution?.status === 'completed';
  const isFailed = execution?.status === 'failed' || !!execution?.error;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.decision_question.trim()) return;

    try {
      const result = await startExecution.mutateAsync({
        workflowId: DECISION_WORKFLOW_ID,
        inputs: formData as unknown as Record<string, unknown>,
      });
      setExecution(result as unknown as YAMLWorkflowResult);
    } catch (error) {
      console.error('Failed to start decision workflow:', error);
    }
  };

  const handleReset = () => {
    setFormData({
      decision_question: '',
      context: '',
      stakeholders: 'technical',
      urgency: 'normal',
    });
    setExecution(null);
  };

  const toggleSection = (section: string) => {
    setExpandedSections((prev) => ({ ...prev, [section]: !prev[section] }));
  };

  // Calculate progress based on completed steps
  const getProgress = () => {
    if (!execution?.steps) return 0;
    const completedSteps = execution.steps.filter((step) =>
      step.status === 'completed' || step.status === 'success'
    ).length;
    return Math.min((completedSteps / DECISION_STEPS.length) * 100, 100);
  };

  const getStepStatus = (stepId: string) => {
    if (!execution?.steps) return null;
    return execution.steps.find((s) => s.step_id === stepId);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-2">
            <Lightbulb className="h-8 w-8 text-yellow-500" />
            Decision Support
          </h1>
          <p className="text-muted-foreground mt-1">
            Get structured recommendations for complex decisions
          </p>
        </div>
        {(isCompleted || isFailed) && (
          <Button variant="outline" onClick={handleReset}>
            <RotateCcw className="mr-2 h-4 w-4" />
            New Decision
          </Button>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Input Form */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle className="text-lg">Decision Details</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Question */}
              <div>
                <label className="block text-sm font-medium mb-1.5">
                  Decision Question <span className="text-destructive">*</span>
                </label>
                <textarea
                  value={formData.decision_question}
                  onChange={(e) => setFormData({ ...formData, decision_question: e.target.value })}
                  placeholder="What decision do you need help with?"
                  className="w-full rounded-lg border bg-background px-3 py-2 text-sm min-h-[100px] focus:outline-none focus:ring-2 focus:ring-primary"
                  disabled={isRunning}
                />
              </div>

              {/* Context */}
              <div>
                <label className="block text-sm font-medium mb-1.5">
                  Context & Constraints
                </label>
                <textarea
                  value={formData.context}
                  onChange={(e) => setFormData({ ...formData, context: e.target.value })}
                  placeholder="Relevant background, constraints, or considerations..."
                  className="w-full rounded-lg border bg-background px-3 py-2 text-sm min-h-[80px] focus:outline-none focus:ring-2 focus:ring-primary"
                  disabled={isRunning}
                />
              </div>

              {/* Stakeholders */}
              <div>
                <label className="block text-sm font-medium mb-1.5">
                  Target Audience
                </label>
                <select
                  value={formData.stakeholders}
                  onChange={(e) => setFormData({ ...formData, stakeholders: e.target.value as DecisionInput['stakeholders'] })}
                  className="w-full rounded-lg border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                  disabled={isRunning}
                >
                  <option value="executive">Executive (high-level)</option>
                  <option value="technical">Technical (detailed)</option>
                  <option value="team">Team (collaborative)</option>
                  <option value="general">General</option>
                </select>
              </div>

              {/* Urgency */}
              <div>
                <label className="block text-sm font-medium mb-1.5">
                  Urgency
                </label>
                <div className="flex gap-2">
                  {(['low', 'normal', 'high', 'critical'] as const).map((level) => (
                    <button
                      key={level}
                      type="button"
                      onClick={() => setFormData({ ...formData, urgency: level })}
                      disabled={isRunning}
                      className={cn(
                        'flex-1 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors',
                        formData.urgency === level
                          ? level === 'critical'
                            ? 'bg-destructive text-destructive-foreground border-destructive'
                            : level === 'high'
                            ? 'bg-orange-500 text-white border-orange-500'
                            : level === 'low'
                            ? 'bg-muted text-muted-foreground border-muted'
                            : 'bg-primary text-primary-foreground border-primary'
                          : 'hover:bg-accent'
                      )}
                    >
                      {level}
                    </button>
                  ))}
                </div>
              </div>

              {/* Submit */}
              <Button
                type="submit"
                className="w-full"
                disabled={!formData.decision_question.trim() || isRunning || startExecution.isPending}
              >
                {startExecution.isPending || isRunning ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Analyzing...
                  </>
                ) : (
                  <>
                    <Play className="mr-2 h-4 w-4" />
                    Get Recommendation
                  </>
                )}
              </Button>
            </form>
          </CardContent>
        </Card>

        {/* Results Panel */}
        <div className="lg:col-span-2 space-y-4">
          {/* Progress */}
          {(isRunning || isCompleted || isFailed) && (
            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-lg flex items-center gap-2">
                    {isRunning && <Loader2 className="h-5 w-5 animate-spin text-primary" />}
                    {isCompleted && <CheckCircle2 className="h-5 w-5 text-green-500" />}
                    {isFailed && <AlertCircle className="h-5 w-5 text-destructive" />}
                    {isRunning ? 'Analyzing Decision...' : isCompleted ? 'Analysis Complete' : 'Analysis Failed'}
                  </CardTitle>
                  {execution && (
                    <Badge variant={isRunning ? 'default' : isCompleted ? 'secondary' : 'destructive'}>
                      {execution.status}
                    </Badge>
                  )}
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <Progress value={isCompleted ? 100 : getProgress()} />

                {/* Steps */}
                <div className="space-y-2">
                  {DECISION_STEPS.map((step, index) => {
                    const stepResult = getStepStatus(step.id);
                    const isStepCompleted = stepResult?.status === 'completed' || stepResult?.status === 'success';

                    return (
                      <div
                        key={step.id}
                        className={cn(
                          'flex items-center gap-3 rounded-lg px-3 py-2 text-sm',
                          isStepCompleted && 'text-muted-foreground'
                        )}
                      >
                        <div className={cn(
                          'flex h-6 w-6 items-center justify-center rounded-full text-xs font-medium',
                          isStepCompleted
                            ? 'bg-green-500 text-white'
                            : 'bg-muted text-muted-foreground'
                        )}>
                          {isStepCompleted ? (
                            <CheckCircle2 className="h-4 w-4" />
                          ) : (
                            index + 1
                          )}
                        </div>
                        <div className="flex-1">
                          <p className="font-medium">
                            {step.name}
                          </p>
                          <p className="text-xs text-muted-foreground">{step.description}</p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Recommendation Output */}
          {isCompleted && execution && (
            <>
              {/* Metrics Summary */}
              <div className="grid gap-4 sm:grid-cols-2">
                <Card>
                  <CardContent className="pt-4">
                    <div className="text-2xl font-bold">{(execution.total_tokens || 0).toLocaleString()}</div>
                    <p className="text-xs text-muted-foreground">Tokens Used</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-4">
                    <div className="text-2xl font-bold">{Math.round((execution.total_duration_ms || 0) / 1000)}s</div>
                    <p className="text-xs text-muted-foreground">Duration</p>
                  </CardContent>
                </Card>
              </div>

              {/* Recommendation Content */}
              <Card>
                <CardHeader className="pb-3">
                  <button
                    onClick={() => toggleSection('recommendation')}
                    className="flex items-center justify-between w-full text-left"
                  >
                    <CardTitle className="text-lg flex items-center gap-2">
                      <FileText className="h-5 w-5" />
                      Recommendation
                    </CardTitle>
                    {expandedSections.recommendation ? (
                      <ChevronDown className="h-5 w-5 text-muted-foreground" />
                    ) : (
                      <ChevronRight className="h-5 w-5 text-muted-foreground" />
                    )}
                  </button>
                </CardHeader>
                {expandedSections.recommendation && (
                  <CardContent>
                    <div className="prose prose-sm dark:prose-invert max-w-none">
                      <div className="rounded-lg bg-muted/50 p-4 whitespace-pre-wrap text-sm">
                        {execution.outputs?.recommendation ||
                          'Recommendation content will appear here when the workflow completes.'}
                      </div>
                    </div>
                  </CardContent>
                )}
              </Card>

              {/* Situation Analysis */}
              {execution.outputs?.situation_analysis && (
                <Card>
                  <CardHeader className="pb-3">
                    <button
                      onClick={() => toggleSection('analysis')}
                      className="flex items-center justify-between w-full text-left"
                    >
                      <CardTitle className="text-lg">Situation Analysis</CardTitle>
                      {expandedSections.analysis ? (
                        <ChevronDown className="h-5 w-5 text-muted-foreground" />
                      ) : (
                        <ChevronRight className="h-5 w-5 text-muted-foreground" />
                      )}
                    </button>
                  </CardHeader>
                  {expandedSections.analysis && (
                    <CardContent>
                      <div className="rounded-lg bg-muted/50 p-4 whitespace-pre-wrap text-sm">
                        {execution.outputs.situation_analysis}
                      </div>
                    </CardContent>
                  )}
                </Card>
              )}

              {/* Options Matrix */}
              {execution.outputs?.options_matrix && (
                <Card>
                  <CardHeader className="pb-3">
                    <button
                      onClick={() => toggleSection('options')}
                      className="flex items-center justify-between w-full text-left"
                    >
                      <CardTitle className="text-lg">Options Considered</CardTitle>
                      {expandedSections.options ? (
                        <ChevronDown className="h-5 w-5 text-muted-foreground" />
                      ) : (
                        <ChevronRight className="h-5 w-5 text-muted-foreground" />
                      )}
                    </button>
                  </CardHeader>
                  {expandedSections.options && (
                    <CardContent>
                      <div className="rounded-lg bg-muted/50 p-4 whitespace-pre-wrap text-sm">
                        {execution.outputs.options_matrix}
                      </div>
                    </CardContent>
                  )}
                </Card>
              )}

              {/* Audit Trail */}
              {execution.outputs?.audit_trail && (
                <Card>
                  <CardHeader className="pb-3">
                    <button
                      onClick={() => toggleSection('audit')}
                      className="flex items-center justify-between w-full text-left"
                    >
                      <CardTitle className="text-lg">Audit Trail</CardTitle>
                      {expandedSections.audit ? (
                        <ChevronDown className="h-5 w-5 text-muted-foreground" />
                      ) : (
                        <ChevronRight className="h-5 w-5 text-muted-foreground" />
                      )}
                    </button>
                  </CardHeader>
                  {expandedSections.audit && (
                    <CardContent>
                      <div className="rounded-lg bg-muted/50 p-4 whitespace-pre-wrap text-sm font-mono text-xs">
                        {execution.outputs.audit_trail}
                      </div>
                    </CardContent>
                  )}
                </Card>
              )}
            </>
          )}

          {/* Empty State */}
          {!execution && !isRunning && (
            <Card className="lg:col-span-2">
              <CardContent className="flex flex-col items-center justify-center py-12 text-center">
                <div className="rounded-full bg-primary/10 p-4 mb-4">
                  <Lightbulb className="h-8 w-8 text-primary" />
                </div>
                <h3 className="text-lg font-semibold mb-2">Ready to Help You Decide</h3>
                <p className="text-muted-foreground max-w-md">
                  Enter your decision question on the left and get a structured recommendation
                  with pros/cons analysis, implementation steps, and an audit trail.
                </p>
                <div className="flex flex-wrap gap-2 mt-4 justify-center">
                  <Badge variant="outline">Technology Choices</Badge>
                  <Badge variant="outline">Build vs Buy</Badge>
                  <Badge variant="outline">Hiring Decisions</Badge>
                  <Badge variant="outline">Architecture</Badge>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
