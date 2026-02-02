import { useState } from 'react';
import { FolderOpen, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import type { ChatMode } from '@/types/chat';

interface NewChatDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onCreateSession: (projectPath?: string, mode?: ChatMode, filesystemEnabled?: boolean) => Promise<void>;
}

export function NewChatDialog({ isOpen, onClose, onCreateSession }: NewChatDialogProps) {
  const [projectPath, setProjectPath] = useState('');
  const [filesystemEnabled, setFilesystemEnabled] = useState(true);
  const [mode, setMode] = useState<ChatMode>('assistant');
  const [isCreating, setIsCreating] = useState(false);

  if (!isOpen) return null;

  const handleCreate = async () => {
    setIsCreating(true);
    try {
      await onCreateSession(
        projectPath || undefined,
        mode,
        projectPath ? filesystemEnabled : false
      );
      onClose();
      setProjectPath('');
      setFilesystemEnabled(true);
      setMode('assistant');
    } finally {
      setIsCreating(false);
    }
  };

  const handleQuickCreate = async () => {
    setIsCreating(true);
    try {
      await onCreateSession();
      onClose();
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-background rounded-lg shadow-lg w-full max-w-md p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">New Chat</h2>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="space-y-4">
          {/* Quick start */}
          <Button
            variant="outline"
            className="w-full justify-start"
            onClick={handleQuickCreate}
            disabled={isCreating}
          >
            Start without project
          </Button>

          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-background px-2 text-muted-foreground">
                or with project
              </span>
            </div>
          </div>

          {/* Project path */}
          <div className="space-y-2">
            <Label htmlFor="project-path">Project Path</Label>
            <div className="flex gap-2">
              <div className="relative flex-1">
                <FolderOpen className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  id="project-path"
                  placeholder="/path/to/your/project"
                  value={projectPath}
                  onChange={(e) => setProjectPath(e.target.value)}
                  className="pl-9"
                />
              </div>
            </div>
            <p className="text-xs text-muted-foreground">
              The agent can read and search files in this directory
            </p>
          </div>

          {/* Filesystem enabled toggle */}
          {projectPath && (
            <div className="flex items-center justify-between">
              <div>
                <Label htmlFor="filesystem-enabled">Enable file access</Label>
                <p className="text-xs text-muted-foreground">
                  Allow agent to read and propose edits
                </p>
              </div>
              <Switch
                id="filesystem-enabled"
                checked={filesystemEnabled}
                onCheckedChange={setFilesystemEnabled}
              />
            </div>
          )}

          {/* Mode selector */}
          <div className="space-y-2">
            <Label>Mode</Label>
            <div className="flex gap-2">
              <Button
                type="button"
                variant={mode === 'assistant' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setMode('assistant')}
                className="flex-1"
              >
                Assistant
              </Button>
              <Button
                type="button"
                variant={mode === 'self_improve' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setMode('self_improve')}
                className="flex-1"
              >
                Self-Improve
              </Button>
            </div>
          </div>

          {/* Create button */}
          <Button
            className="w-full"
            onClick={handleCreate}
            disabled={isCreating}
          >
            {isCreating ? 'Creating...' : 'Create Chat'}
          </Button>
        </div>
      </div>
    </div>
  );
}
