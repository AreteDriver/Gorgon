import { useEffect, useRef } from 'react';
import { ScrollArea } from '@/components/ui/scroll-area';
import { useChatStore } from '@/stores/chatStore';
import { Message } from './Message';
import { StreamingMessage } from './StreamingMessage';

export function MessageList() {
  const { messages, isStreaming, streamingContent, streamingAgent } = useChatStore();
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, streamingContent]);

  return (
    <ScrollArea className="flex-1 p-6" ref={scrollRef}>
      <div className="max-w-3xl mx-auto space-y-6">
        {messages.map((message) => (
          <Message key={message.id} message={message} />
        ))}

        {isStreaming && (
          <StreamingMessage content={streamingContent} agent={streamingAgent} />
        )}

        {messages.length === 0 && !isStreaming && (
          <div className="text-center py-12 text-muted-foreground">
            <p>Send a message to start the conversation</p>
          </div>
        )}
      </div>
    </ScrollArea>
  );
}
