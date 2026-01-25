import { useState } from 'react';
import { Save, AlertTriangle, AlertCircle, CheckCircle, ChevronDown } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useWorkflowBuilderStore } from '@/stores';
import { useWorkflowValidation } from './hooks/useWorkflowValidation';
import { cn } from '@/lib/utils';

interface WorkflowToolbarProps {
  onSave: () => void;
  isSaving?: boolean;
}

export function WorkflowToolbar({ onSave, isSaving }: WorkflowToolbarProps) {
  const { isDirty, workflowName, setWorkflowName, validationErrors, selectNode } =
    useWorkflowBuilderStore();
  const { validate } = useWorkflowValidation();
  const [showErrors, setShowErrors] = useState(false);

  const errorCount = validationErrors.filter((e) => e.severity === 'error').length;
  const warningCount = validationErrors.filter((e) => e.severity === 'warning').length;

  const handleValidate = () => {
    validate();
    setShowErrors(true);
  };

  const handleSave = () => {
    const result = validate();
    if (result.isValid) {
      onSave();
      setShowErrors(false);
    } else {
      setShowErrors(true);
    }
  };

  const handleErrorClick = (nodeId?: string) => {
    if (nodeId) {
      selectNode(nodeId);
    }
  };

  return (
    <div className="relative">
      <div className="flex h-14 items-center justify-between border-b bg-card px-4">
        {/* Left section - Workflow name */}
        <div className="flex items-center gap-4">
          <input
            type="text"
            value={workflowName}
            onChange={(e) => setWorkflowName(e.target.value)}
            className="bg-transparent text-lg font-semibold text-foreground outline-none focus:ring-2 focus:ring-primary rounded px-2 py-1"
            placeholder="Workflow name..."
          />
          {isDirty && (
            <span className="text-xs text-muted-foreground">(unsaved changes)</span>
          )}
        </div>

        {/* Right section - Validation & Actions */}
        <div className="flex items-center gap-2">
          {/* Validation status */}
          {validationErrors.length > 0 && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowErrors(!showErrors)}
              className={cn(
                'gap-2',
                errorCount > 0 ? 'text-destructive' : 'text-yellow-600'
              )}
            >
              {errorCount > 0 ? (
                <AlertCircle className="h-4 w-4" />
              ) : (
                <AlertTriangle className="h-4 w-4" />
              )}
              {errorCount > 0 && <span>{errorCount} error{errorCount !== 1 ? 's' : ''}</span>}
              {warningCount > 0 && (
                <span className="text-yellow-600">
                  {errorCount > 0 && ', '}
                  {warningCount} warning{warningCount !== 1 ? 's' : ''}
                </span>
              )}
              <ChevronDown className={cn('h-3 w-3 transition-transform', showErrors && 'rotate-180')} />
            </Button>
          )}

          {validationErrors.length === 0 && (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleValidate}
              className="gap-2 text-muted-foreground"
            >
              <CheckCircle className="h-4 w-4" />
              Validate
            </Button>
          )}

          <Button
            variant="outline"
            size="sm"
            onClick={handleSave}
            disabled={isSaving}
            className="gap-2"
          >
            <Save className="h-4 w-4" />
            {isSaving ? 'Saving...' : 'Save'}
          </Button>
        </div>
      </div>

      {/* Validation errors dropdown */}
      {showErrors && validationErrors.length > 0 && (
        <div className="absolute right-4 top-14 z-50 w-96 rounded-lg border bg-card shadow-lg">
          <div className="max-h-64 overflow-y-auto p-2">
            {validationErrors.map((error, index) => (
              <button
                key={index}
                onClick={() => handleErrorClick(error.nodeId)}
                className={cn(
                  'w-full flex items-start gap-2 rounded-md px-3 py-2 text-left text-sm transition-colors',
                  'hover:bg-muted',
                  error.nodeId && 'cursor-pointer'
                )}
              >
                {error.severity === 'error' ? (
                  <AlertCircle className="h-4 w-4 mt-0.5 shrink-0 text-destructive" />
                ) : (
                  <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0 text-yellow-600" />
                )}
                <span className="text-foreground">{error.message}</span>
              </button>
            ))}
          </div>
          <div className="border-t p-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowErrors(false)}
              className="w-full"
            >
              Dismiss
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
