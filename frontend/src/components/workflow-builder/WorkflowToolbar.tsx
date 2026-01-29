import { useState, useRef, useEffect } from 'react';
import { Save, AlertTriangle, AlertCircle, CheckCircle, ChevronDown, Download, Upload, Undo2, Redo2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useWorkflowBuilderStore } from '@/stores';
import { useWorkflowValidation } from './hooks/useWorkflowValidation';
import { cn } from '@/lib/utils';

interface WorkflowToolbarProps {
  onSave: () => void;
  onExportYaml?: () => void;
  onImportYaml?: (yamlString: string) => void;
  isSaving?: boolean;
}

export function WorkflowToolbar({ onSave, onExportYaml, onImportYaml, isSaving }: WorkflowToolbarProps) {
  const { isDirty, workflowName, setWorkflowName, validationErrors, selectNode, undo, redo, canUndo, canRedo } =
    useWorkflowBuilderStore();
  const { validate } = useWorkflowValidation();
  const [showErrors, setShowErrors] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Keyboard shortcuts for undo/redo
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Check for Ctrl/Cmd + Z (undo) and Ctrl/Cmd + Shift + Z or Ctrl/Cmd + Y (redo)
      if ((e.ctrlKey || e.metaKey) && !e.altKey) {
        if (e.key === 'z' && !e.shiftKey) {
          e.preventDefault();
          if (canUndo()) undo();
        } else if ((e.key === 'z' && e.shiftKey) || e.key === 'y') {
          e.preventDefault();
          if (canRedo()) redo();
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [undo, redo, canUndo, canRedo]);

  const handleImportClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file && onImportYaml) {
      const reader = new FileReader();
      reader.onload = (e) => {
        const content = e.target?.result as string;
        onImportYaml(content);
      };
      reader.readAsText(file);
    }
    // Reset input so the same file can be selected again
    event.target.value = '';
  };

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
          {/* Undo/Redo buttons */}
          <div className="flex items-center border-r pr-2 mr-2">
            <Button
              variant="ghost"
              size="icon"
              onClick={undo}
              disabled={!canUndo()}
              title="Undo (Ctrl+Z)"
              className="h-8 w-8"
            >
              <Undo2 className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={redo}
              disabled={!canRedo()}
              title="Redo (Ctrl+Shift+Z)"
              className="h-8 w-8"
            >
              <Redo2 className="h-4 w-4" />
            </Button>
          </div>

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

          {/* YAML Export/Import */}
          {onExportYaml && (
            <Button
              variant="outline"
              size="sm"
              onClick={onExportYaml}
              className="gap-2"
              title="Export as YAML"
            >
              <Download className="h-4 w-4" />
              Export
            </Button>
          )}

          {onImportYaml && (
            <>
              <input
                ref={fileInputRef}
                type="file"
                accept=".yaml,.yml"
                onChange={handleFileChange}
                className="hidden"
              />
              <Button
                variant="outline"
                size="sm"
                onClick={handleImportClick}
                className="gap-2"
                title="Import from YAML"
              >
                <Upload className="h-4 w-4" />
                Import
              </Button>
            </>
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
