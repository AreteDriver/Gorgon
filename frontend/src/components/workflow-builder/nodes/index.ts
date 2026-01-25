import { AgentNode } from './AgentNode';
import { ShellNode } from './ShellNode';
import { CheckpointNode } from './CheckpointNode';

export const nodeTypes = {
  agent: AgentNode,
  shell: ShellNode,
  checkpoint: CheckpointNode,
};

export { AgentNode, ShellNode, CheckpointNode };
