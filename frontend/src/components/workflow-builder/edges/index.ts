import { VariableEdge } from './VariableEdge';
import { LabeledEdge } from './LabeledEdge';

export const edgeTypes = {
  variable: LabeledEdge,  // Use LabeledEdge as default - it handles both labels and variables
  labeled: LabeledEdge,
};

export { VariableEdge, LabeledEdge };
