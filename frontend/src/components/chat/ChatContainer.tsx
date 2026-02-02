import { useEffect, useRef } from 'react';
import { Plus, MessageSquare, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { cn } from '@/lib/utils';
import { useChatStore } from '@/stores/chatStore';
import { MessageList } from './MessageList';
import { MessageInput } from './MessageInput';

export function ChatContainer() {
  const {
    sessions,
    activeSessionId,
    activeSession,
    isLoading,
    fetchSessions,
    createSession,
    selectSession,
    deleteSession,
  } = useChatStore();

  const initialFetchRef = useRef(false);

  useEffect(() => {
    if (!initialFetchRef.current) {
      initialFetchRef.current = true;
      fetchSessions();
    }
  }, [fetchSessions]);

  const handleNewChat = async () => {
    await createSession();
  };

  const handleDeleteSession = async (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    if (confirm('Delete this conversation?')) {
      await deleteSession(sessionId);
    }
  };

  return (
    <div className="flex h-[calc(100vh-6rem)]">
      {/* Session Sidebar */}
      <div className="w-64 border-r bg-muted/30 flex flex-col">
        <div className="p-4 border-b">
          <Button onClick={handleNewChat} className="w-full" disabled={isLoading}>
            <Plus className="h-4 w-4 mr-2" />
            New Chat
          </Button>
        </div>

        <ScrollArea className="flex-1">
          <div className="p-2 space-y-1">
            {sessions.map((session) => (
              <button
                key={session.id}
                onClick={() => selectSession(session.id)}
                className={cn(
                  'w-full flex items-center justify-between p-3 rounded-lg text-sm',
                  'hover:bg-muted/50 transition-colors group',
                  activeSessionId === session.id && 'bg-muted'
                )}
              >
                <div className="flex items-center gap-2 overflow-hidden">
                  <MessageSquare className="h-4 w-4 shrink-0 text-muted-foreground" />
                  <span className="truncate">{session.title}</span>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6 opacity-0 group-hover:opacity-100"
                  onClick={(e) => handleDeleteSession(e, session.id)}
                >
                  <Trash2 className="h-3 w-3 text-muted-foreground" />
                </Button>
              </button>
            ))}

            {sessions.length === 0 && !isLoading && (
              <p className="text-sm text-muted-foreground text-center py-4">
                No conversations yet
              </p>
            )}
          </div>
        </ScrollArea>
      </div>

      {/* Chat Area */}
      <div className="flex-1 flex flex-col">
        {activeSession ? (
          <>
            {/* Header */}
            <div className="h-14 border-b px-6 flex items-center justify-between">
              <div>
                <h2 className="font-semibold">{activeSession.title}</h2>
                {activeSession.project_path && (
                  <p className="text-xs text-muted-foreground">
                    {activeSession.project_path}
                  </p>
                )}
              </div>
              {activeSession.mode === 'self_improve' && (
                <span className="text-xs bg-yellow-500/10 text-yellow-600 px-2 py-1 rounded">
                  Self-Improvement Mode
                </span>
              )}
            </div>

            {/* Messages */}
            <MessageList />

            {/* Input */}
            <MessageInput />
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-muted-foreground">
            <div className="text-center">
              <MessageSquare className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p className="text-lg font-medium">Welcome to Gorgon Chat</p>
              <p className="text-sm">Start a new conversation or select an existing one</p>
              <Button onClick={handleNewChat} className="mt-4">
                <Plus className="h-4 w-4 mr-2" />
                New Chat
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
