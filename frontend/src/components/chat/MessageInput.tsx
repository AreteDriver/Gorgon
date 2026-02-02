import { useState, useRef, useEffect, KeyboardEvent } from 'react';
import { Send, Square, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { useChatStore } from '@/stores/chatStore';

export function MessageInput() {
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const { sendMessage, cancelGeneration, isStreaming, error } = useChatStore();

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  }, [input]);

  const handleSubmit = async () => {
    if (!input.trim() || isStreaming) return;

    const message = input.trim();
    setInput('');
    await sendMessage(message);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    // Submit on Enter (without shift)
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="border-t p-4">
      {/* Error display */}
      {error && (
        <div className="mb-2 text-sm text-red-500 bg-red-500/10 px-3 py-2 rounded">
          {error}
        </div>
      )}

      {/* Input area */}
      <div className="max-w-3xl mx-auto flex gap-2">
        <div className="flex-1 relative">
          <Textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Send a message..."
            disabled={isStreaming}
            className="min-h-[52px] max-h-[200px] resize-none pr-12"
            rows={1}
          />

          {/* Character count for long messages */}
          {input.length > 1000 && (
            <span className="absolute bottom-2 right-14 text-xs text-muted-foreground">
              {input.length.toLocaleString()}
            </span>
          )}
        </div>

        {isStreaming ? (
          <Button onClick={cancelGeneration} variant="destructive" size="icon" className="h-[52px] w-[52px]">
            <Square className="h-5 w-5" />
          </Button>
        ) : (
          <Button
            onClick={handleSubmit}
            disabled={!input.trim()}
            size="icon"
            className="h-[52px] w-[52px]"
          >
            {isStreaming ? (
              <Loader2 className="h-5 w-5 animate-spin" />
            ) : (
              <Send className="h-5 w-5" />
            )}
          </Button>
        )}
      </div>

      <p className="text-xs text-muted-foreground text-center mt-2">
        Press Enter to send, Shift+Enter for new line
      </p>
    </div>
  );
}
