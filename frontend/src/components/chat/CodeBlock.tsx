import { useState } from 'react';
import { Check, Copy, Play } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface CodeBlockProps {
  code: string;
  language: string;
  onApply?: (code: string) => void;
}

export function CodeBlock({ code, language, onApply }: CodeBlockProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="my-2 rounded-lg overflow-hidden border bg-zinc-950">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 bg-zinc-900 border-b border-zinc-800">
        <span className="text-xs text-zinc-400 font-mono">{language}</span>
        <div className="flex items-center gap-1">
          {onApply && (
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6 text-zinc-400 hover:text-white"
              onClick={() => onApply(code)}
              title="Apply code"
            >
              <Play className="h-3 w-3" />
            </Button>
          )}
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6 text-zinc-400 hover:text-white"
            onClick={handleCopy}
            title="Copy code"
          >
            {copied ? (
              <Check className="h-3 w-3 text-green-400" />
            ) : (
              <Copy className="h-3 w-3" />
            )}
          </Button>
        </div>
      </div>

      {/* Code */}
      <pre className="p-4 overflow-x-auto">
        <code className={cn('text-sm font-mono text-zinc-100', `language-${language}`)}>
          {code}
        </code>
      </pre>
    </div>
  );
}
