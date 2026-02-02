import { Bot, Loader2 } from 'lucide-react';
import { AgentBadge } from './AgentBadge';
import { CodeBlock } from './CodeBlock';

interface StreamingMessageProps {
  content: string;
  agent: string | null;
}

export function StreamingMessage({ content, agent }: StreamingMessageProps) {
  // Parse content for code blocks (same logic as Message)
  const renderContent = (text: string) => {
    if (!text) {
      return (
        <div className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          <span>Thinking...</span>
        </div>
      );
    }

    // Split by code blocks
    const parts = text.split(/(```[\s\S]*?```)/g);

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

      // Regular text
      return (
        <span key={index} className="whitespace-pre-wrap">
          {part}
        </span>
      );
    });
  };

  return (
    <div className="flex gap-4">
      {/* Avatar */}
      <div className="w-8 h-8 rounded-full bg-muted flex items-center justify-center shrink-0">
        <Bot className="h-4 w-4" />
      </div>

      {/* Content */}
      <div className="flex-1 max-w-[80%]">
        {/* Agent badge */}
        {agent && (
          <div className="mb-1">
            <AgentBadge agent={agent} />
          </div>
        )}

        {/* Message bubble with streaming indicator */}
        <div className="inline-block rounded-2xl px-4 py-3 text-sm bg-muted">
          {renderContent(content)}
          <span className="animate-pulse">▋</span>
        </div>
      </div>
    </div>
  );
}
