import { useCallback } from 'react';
import { X, Trash2, Terminal, PauseCircle } from 'lucide-react';
import { useWorkflowBuilderStore } from '@/stores';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Select } from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import {
  getAgentRoleInfo,
  isAgentNode,
  isShellNode,
  isCheckpointNode,
  AGENT_ROLES,
  type AgentNodeData,
  type ShellNodeData,
  type CheckpointNodeData,
  type WorkflowNodeData,
} from '@/types/workflow-builder';
import type { AgentRole } from '@/types';

// Agent Node Properties
function AgentProperties({
  data,
  onChange,
}: {
  data: AgentNodeData;
  onChange: (field: keyof AgentNodeData, value: unknown) => void;
}) {
  const roleInfo = getAgentRoleInfo(data.role);

  return (
    <>
      {/* Name */}
      <div className="space-y-2">
        <Label htmlFor="node-name">Name</Label>
        <Input
          id="node-name"
          value={data.name}
          onChange={(e) => onChange('name', e.target.value)}
          placeholder="Step name"
        />
      </div>

      {/* Role */}
      <div className="space-y-2">
        <Label htmlFor="node-role">Agent Role</Label>
        <Select
          id="node-role"
          value={data.role}
          onChange={(e) => onChange('role', e.target.value as AgentRole)}
        >
          {AGENT_ROLES.map((role) => (
            <option key={role.role} value={role.role}>
              {role.label}
            </option>
          ))}
        </Select>
        <p className="text-xs text-muted-foreground">{roleInfo.description}</p>
      </div>

      {/* Prompt */}
      <div className="space-y-2">
        <Label htmlFor="node-prompt">Prompt</Label>
        <Textarea
          id="node-prompt"
          value={data.prompt || ''}
          onChange={(e) => onChange('prompt', e.target.value)}
          placeholder="Instructions for this agent..."
          rows={4}
        />
      </div>

      {/* On Failure */}
      <div className="space-y-2">
        <Label htmlFor="node-onfailure">On Failure</Label>
        <Select
          id="node-onfailure"
          value={data.onFailure || 'stop'}
          onChange={(e) =>
            onChange('onFailure', e.target.value as 'stop' | 'continue' | 'retry')
          }
        >
          <option value="stop">Stop workflow</option>
          <option value="continue">Continue to next step</option>
          <option value="retry">Retry step</option>
        </Select>
      </div>

      {/* Max Retries */}
      {data.onFailure === 'retry' && (
        <div className="space-y-2">
          <Label htmlFor="node-retries">Max Retries</Label>
          <Input
            id="node-retries"
            type="number"
            min={1}
            max={10}
            value={data.maxRetries || 3}
            onChange={(e) => onChange('maxRetries', parseInt(e.target.value, 10))}
          />
        </div>
      )}

      {/* Outputs */}
      <div className="space-y-2">
        <Label htmlFor="node-outputs">Expected Outputs</Label>
        <Input
          id="node-outputs"
          value={data.outputs?.join(', ') || ''}
          onChange={(e) =>
            onChange(
              'outputs',
              e.target.value
                .split(',')
                .map((s) => s.trim())
                .filter(Boolean)
            )
          }
          placeholder="output1, output2, ..."
        />
        <p className="text-xs text-muted-foreground">
          Comma-separated list of output variable names
        </p>
      </div>
    </>
  );
}

// Shell Node Properties
function ShellProperties({
  data,
  onChange,
}: {
  data: ShellNodeData;
  onChange: (field: keyof ShellNodeData, value: unknown) => void;
}) {
  return (
    <>
      {/* Name */}
      <div className="space-y-2">
        <Label htmlFor="node-name">Name</Label>
        <Input
          id="node-name"
          value={data.name}
          onChange={(e) => onChange('name', e.target.value)}
          placeholder="Step name"
        />
      </div>

      {/* Command */}
      <div className="space-y-2">
        <Label htmlFor="node-command">Command</Label>
        <Textarea
          id="node-command"
          value={data.command || ''}
          onChange={(e) => onChange('command', e.target.value)}
          placeholder="echo 'Hello World'"
          rows={3}
          className="font-mono text-sm"
        />
        <p className="text-xs text-muted-foreground">
          Shell command to execute
        </p>
      </div>

      {/* Allow Failure */}
      <div className="space-y-2">
        <Label htmlFor="node-allowfailure">Allow Failure</Label>
        <Select
          id="node-allowfailure"
          value={data.allowFailure ? 'yes' : 'no'}
          onChange={(e) => onChange('allowFailure', e.target.value === 'yes')}
        >
          <option value="no">No - stop on failure</option>
          <option value="yes">Yes - continue on failure</option>
        </Select>
      </div>

      {/* Timeout */}
      <div className="space-y-2">
        <Label htmlFor="node-timeout">Timeout (seconds)</Label>
        <Input
          id="node-timeout"
          type="number"
          min={1}
          max={3600}
          value={data.timeout || 60}
          onChange={(e) => onChange('timeout', parseInt(e.target.value, 10))}
        />
        <p className="text-xs text-muted-foreground">
          Maximum execution time (1-3600 seconds)
        </p>
      </div>
    </>
  );
}

// Checkpoint Node Properties
function CheckpointProperties({
  data,
  onChange,
}: {
  data: CheckpointNodeData;
  onChange: (field: keyof CheckpointNodeData, value: unknown) => void;
}) {
  return (
    <>
      {/* Name */}
      <div className="space-y-2">
        <Label htmlFor="node-name">Name</Label>
        <Input
          id="node-name"
          value={data.name}
          onChange={(e) => onChange('name', e.target.value)}
          placeholder="Checkpoint name"
        />
      </div>

      {/* Message */}
      <div className="space-y-2">
        <Label htmlFor="node-message">Pause Message</Label>
        <Textarea
          id="node-message"
          value={data.message || ''}
          onChange={(e) => onChange('message', e.target.value)}
          placeholder="Workflow paused for review..."
          rows={3}
        />
        <p className="text-xs text-muted-foreground">
          Message shown when workflow pauses at this checkpoint
        </p>
      </div>
    </>
  );
}

export function PropertyPanel() {
  const { nodes, selectedNodeId, updateNodeData, deleteNode, selectNode } =
    useWorkflowBuilderStore();

  const selectedNode = nodes.find((n) => n.id === selectedNodeId);

  const handleClose = useCallback(() => {
    selectNode(null);
  }, [selectNode]);

  const handleDelete = useCallback(() => {
    if (selectedNodeId) {
      deleteNode(selectedNodeId);
    }
  }, [selectedNodeId, deleteNode]);

  // No selection
  if (!selectedNode) {
    return (
      <div className="h-full w-72 border-l bg-card p-4">
        <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
          Select a node to edit its properties
        </div>
      </div>
    );
  }

  const data = selectedNode.data;

  const handleChange = (field: string, value: unknown) => {
    updateNodeData(selectedNode.id, { [field]: value } as Partial<WorkflowNodeData>);
  };

  // Determine header style based on node type
  let headerBg = '#6b7280'; // default gray
  let headerTitle = 'Properties';

  if (isAgentNode(data)) {
    const roleInfo = getAgentRoleInfo(data.role);
    headerBg = roleInfo.color;
    headerTitle = `${roleInfo.label} Properties`;
  } else if (isShellNode(data)) {
    headerBg = '#27272a'; // zinc-800
    headerTitle = 'Shell Command';
  } else if (isCheckpointNode(data)) {
    headerBg = '#f59e0b'; // amber-500
    headerTitle = 'Checkpoint';
  }

  return (
    <div className="h-full w-72 border-l bg-card overflow-y-auto">
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-3 border-b"
        style={{ backgroundColor: headerBg }}
      >
        <div className="flex items-center gap-2">
          {isShellNode(data) && <Terminal className="h-4 w-4 text-green-400" />}
          {isCheckpointNode(data) && <PauseCircle className="h-4 w-4 text-white" />}
          <span className="text-sm font-medium text-white">{headerTitle}</span>
        </div>
        <Button
          variant="ghost"
          size="icon"
          onClick={handleClose}
          className="h-6 w-6 text-white hover:bg-white/20"
        >
          <X className="h-4 w-4" />
        </Button>
      </div>

      {/* Form */}
      <div className="p-4 space-y-4">
        {isAgentNode(data) && (
          <AgentProperties
            data={data}
            onChange={(field, value) => handleChange(field as string, value)}
          />
        )}
        {isShellNode(data) && (
          <ShellProperties
            data={data}
            onChange={(field, value) => handleChange(field as string, value)}
          />
        )}
        {isCheckpointNode(data) && (
          <CheckpointProperties
            data={data}
            onChange={(field, value) => handleChange(field as string, value)}
          />
        )}

        {/* Delete Button */}
        <div className="pt-4 border-t">
          <Button
            variant="destructive"
            size="sm"
            onClick={handleDelete}
            className="w-full gap-2"
          >
            <Trash2 className="h-4 w-4" />
            Delete Node
          </Button>
        </div>
      </div>
    </div>
  );
}
