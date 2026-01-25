import { Save } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useWorkflowBuilderStore } from '@/stores';

interface WorkflowToolbarProps {
  onSave: () => void;
  isSaving?: boolean;
}

export function WorkflowToolbar({ onSave, isSaving }: WorkflowToolbarProps) {
  const { isDirty, workflowName, setWorkflowName } = useWorkflowBuilderStore();

  return (
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

      {/* Right section - Actions */}
      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={onSave}
          disabled={isSaving}
          className="gap-2"
        >
          <Save className="h-4 w-4" />
          {isSaving ? 'Saving...' : 'Save'}
        </Button>
      </div>
    </div>
  );
}
