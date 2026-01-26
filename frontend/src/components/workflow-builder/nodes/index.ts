import { AgentNode } from './AgentNode';
import { ShellNode } from './ShellNode';
import { CheckpointNode } from './CheckpointNode';
import { ParallelNode } from './ParallelNode';
import { FanOutNode } from './FanOutNode';
import { FanInNode } from './FanInNode';
import { MapReduceNode } from './MapReduceNode';

export const nodeTypes = {
  agent: AgentNode,
  shell: ShellNode,
  checkpoint: CheckpointNode,
  parallel: ParallelNode,
  fan_out: FanOutNode,
  fan_in: FanInNode,
  map_reduce: MapReduceNode,
};

export {
  AgentNode,
  ShellNode,
  CheckpointNode,
  ParallelNode,
  FanOutNode,
  FanInNode,
  MapReduceNode,
};
