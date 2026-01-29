import { ReactNode } from 'react';
import { render, RenderOptions } from '@testing-library/react';
import { ReactFlowProvider } from '@xyflow/react';

// Wrapper that provides required context providers
function AllProviders({ children }: { children: ReactNode }) {
  return <ReactFlowProvider>{children}</ReactFlowProvider>;
}

// Custom render that wraps component with providers
function customRender(ui: React.ReactElement, options?: Omit<RenderOptions, 'wrapper'>) {
  return render(ui, { wrapper: AllProviders, ...options });
}

// Re-export everything from testing-library
export * from '@testing-library/react';
export { customRender as render };
