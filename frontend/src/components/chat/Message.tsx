import { User, Bot } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ChatMessage } from '@/types/chat';
import { getAgentDisplay } from '@/types/chat';
import { AgentBadge } from './AgentBadge';
import { CodeBlock } from './CodeBlock';

interface MessageProps {
  message: ChatMessage;
}

export function Message({ message }: MessageProps) {
  const isUser = message.role === 'user';
  const isSystem = message.role === 'system';
  const agentDisplay = getAgentDisplay(message.agent);

  // Parse content for code blocks
  const renderContent = (content: string) => {
    // Split by code blocks
    const parts = content.split(/(```[\s\S]*?```)/g);

    return parts.map((part, index) => {
      if (part.startsWith('```')) {
        // Extract language and code
        const match = part.match(/```(\w+)?\n?([\s\S]*?)```/);
        if (match) {
          const language = match[1] || 'text';
          const code = match[2].trim();
          return <CodeBlock key={index} code={code} language={language} />;
        }
      }

      // Regular text - render with line breaks preserved
      return (
        <div key={index} className="whitespace-pre-wrap">
          {part}
        </div>
      );
    });
  };

  if (isSystem) {
    return (
      <div className="flex justify-center">
        <div className="text-sm text-muted-foreground bg-muted/50 px-4 py-2 rounded-lg">
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div
      className={cn(
        'flex gap-4',
        isUser && 'flex-row-reverse'
      )}
    >
      {/* Avatar */}
      <div
        className={cn(
          'w-8 h-8 rounded-full flex items-center justify-center shrink-0',
          isUser ? 'bg-primary text-primary-foreground' : 'bg-muted'
        )}
      >
        {isUser ? (
          <User className="h-4 w-4" />
        ) : (
          <Bot className="h-4 w-4" />
        )}
      </div>

      {/* Content */}
      <div
        className={cn(
          'flex-1 max-w-[80%]',
          isUser && 'text-right'
        )}
      >
        {/* Agent badge */}
        {agentDisplay && !isUser && (
          <div className="mb-1">
            <AgentBadge agent={message.agent!} />
          </div>
        )}

        {/* Message bubble */}
        <div
          className={cn(
            'inline-block rounded-2xl px-4 py-3 text-sm',
            isUser
              ? 'bg-primary text-primary-foreground'
              : 'bg-muted'
          )}
        >
          {renderContent(message.content)}
        </div>

        {/* Timestamp */}
        <div className={cn('text-xs text-muted-foreground mt-1', isUser && 'text-right')}>
          {new Date(message.created_at).toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
          })}
        </div>
      </div>
    </div>
  );
}
