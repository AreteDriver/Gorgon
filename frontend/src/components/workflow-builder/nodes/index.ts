import { AgentNode } from './AgentNode';
import { ShellNode } from './ShellNode';
import { CheckpointNode } from './CheckpointNode';
import { ParallelNode } from './ParallelNode';
import { FanOutNode } from './FanOutNode';
import { FanInNode } from './FanInNode';
import { MapReduceNode } from './MapReduceNode';
import { BranchNode } from './BranchNode';
import { LoopNode } from './LoopNode';

export const nodeTypes = {
  agent: AgentNode,
  shell: ShellNode,
  checkpoint: CheckpointNode,
  parallel: ParallelNode,
  fan_out: FanOutNode,
  fan_in: FanInNode,
  map_reduce: MapReduceNode,
  branch: BranchNode,
  loop: LoopNode,
};

export {
  AgentNode,
  ShellNode,
  CheckpointNode,
  ParallelNode,
  FanOutNode,
  FanInNode,
  MapReduceNode,
  BranchNode,
  LoopNode,
};
