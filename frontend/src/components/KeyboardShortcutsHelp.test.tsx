import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { KeyboardShortcutsHelp } from './KeyboardShortcutsHelp';

describe('KeyboardShortcutsHelp', () => {
  beforeEach(() => {
    // Reset any mocks between tests
    vi.clearAllMocks();
  });

  afterEach(() => {
    // Clean up event listeners
    vi.restoreAllMocks();
  });

  it('renders nothing visible initially', () => {
    render(<KeyboardShortcutsHelp />);

    // Dialog should not be visible initially
    expect(screen.queryByText('Keyboard Shortcuts')).not.toBeInTheDocument();
  });

  it('opens dialog when ? key is pressed', async () => {
    render(<KeyboardShortcutsHelp />);

    // Simulate pressing the ? key
    fireEvent.keyDown(document, { key: '?' });

    await waitFor(() => {
      expect(screen.getByText('Keyboard Shortcuts')).toBeInTheDocument();
    });
  });

  it('opens dialog when Ctrl+/ is pressed', async () => {
    render(<KeyboardShortcutsHelp />);

    fireEvent.keyDown(document, { key: '/', ctrlKey: true });

    await waitFor(() => {
      expect(screen.getByText('Keyboard Shortcuts')).toBeInTheDocument();
    });
  });

  it('opens dialog when Cmd+/ is pressed (Mac)', async () => {
    render(<KeyboardShortcutsHelp />);

    fireEvent.keyDown(document, { key: '/', metaKey: true });

    await waitFor(() => {
      expect(screen.getByText('Keyboard Shortcuts')).toBeInTheDocument();
    });
  });

  it('does not open when ? is pressed in an input', () => {
    render(
      <div>
        <input data-testid="test-input" />
        <KeyboardShortcutsHelp />
      </div>
    );

    const input = screen.getByTestId('test-input');
    input.focus();

    fireEvent.keyDown(input, { key: '?' });

    // Dialog should not appear
    expect(screen.queryByText('Keyboard Shortcuts')).not.toBeInTheDocument();
  });

  it('displays General shortcuts section', async () => {
    render(<KeyboardShortcutsHelp />);

    fireEvent.keyDown(document, { key: '?' });

    await waitFor(() => {
      // The text is "General" but displayed with CSS uppercase
      expect(screen.getByText('General')).toBeInTheDocument();
      // There are two "Show this help" entries (? and Ctrl+/)
      expect(screen.getAllByText('Show this help').length).toBeGreaterThanOrEqual(1);
    });
  });

  it('displays Editing shortcuts section', async () => {
    render(<KeyboardShortcutsHelp />);

    fireEvent.keyDown(document, { key: '?' });

    await waitFor(() => {
      // The text is "Editing" but displayed with CSS uppercase
      expect(screen.getByText('Editing')).toBeInTheDocument();
      expect(screen.getByText('Undo')).toBeInTheDocument();
      expect(screen.getByText('Redo')).toBeInTheDocument();
      expect(screen.getByText('Save')).toBeInTheDocument();
    });
  });

  it('displays Navigation shortcuts section', async () => {
    render(<KeyboardShortcutsHelp />);

    fireEvent.keyDown(document, { key: '?' });

    await waitFor(() => {
      // The text is "Navigation" but displayed with CSS uppercase
      expect(screen.getByText('Navigation')).toBeInTheDocument();
      expect(screen.getByText('Close dialog / Cancel')).toBeInTheDocument();
    });
  });

  it('displays keyboard key styling', async () => {
    render(<KeyboardShortcutsHelp />);

    fireEvent.keyDown(document, { key: '?' });

    await waitFor(() => {
      // Check for kbd elements
      const kbdElements = screen.getAllByText('Ctrl', { selector: 'kbd' });
      expect(kbdElements.length).toBeGreaterThan(0);
    });
  });

  it('displays description text', async () => {
    render(<KeyboardShortcutsHelp />);

    fireEvent.keyDown(document, { key: '?' });

    await waitFor(() => {
      expect(screen.getByText('Quick reference for available keyboard shortcuts')).toBeInTheDocument();
    });
  });

  it('displays footer with close instruction', async () => {
    render(<KeyboardShortcutsHelp />);

    fireEvent.keyDown(document, { key: '?' });

    await waitFor(() => {
      // The footer has text "Press <kbd>Esc</kbd> to close"
      // There are multiple Esc kbd elements (one in Navigation section, one in footer)
      const escElements = screen.getAllByText('Esc', { selector: 'kbd' });
      expect(escElements.length).toBeGreaterThanOrEqual(1);
    });
  });
});
