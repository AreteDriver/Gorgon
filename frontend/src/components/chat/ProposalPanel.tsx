import { useState } from 'react';
import { Check, X, FileText, ChevronDown, ChevronRight, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { cn } from '@/lib/utils';
import type { EditProposal } from '@/types/chat';

interface ProposalPanelProps {
  proposals: EditProposal[];
  onApprove: (proposalId: string) => Promise<void>;
  onReject: (proposalId: string) => Promise<void>;
  isLoading?: boolean;
}

export function ProposalPanel({ proposals, onApprove, onReject, isLoading }: ProposalPanelProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [processingId, setProcessingId] = useState<string | null>(null);

  const pendingProposals = proposals.filter((p) => p.status === 'pending');

  if (pendingProposals.length === 0) {
    return null;
  }

  const handleApprove = async (proposalId: string) => {
    setProcessingId(proposalId);
    try {
      await onApprove(proposalId);
    } finally {
      setProcessingId(null);
    }
  };

  const handleReject = async (proposalId: string) => {
    setProcessingId(proposalId);
    try {
      await onReject(proposalId);
    } finally {
      setProcessingId(null);
    }
  };

  return (
    <div className="border-t bg-muted/30">
      <div className="px-4 py-2 border-b flex items-center justify-between">
        <div className="flex items-center gap-2">
          <AlertCircle className="h-4 w-4 text-yellow-500" />
          <span className="text-sm font-medium">
            {pendingProposals.length} pending edit{pendingProposals.length !== 1 ? 's' : ''}
          </span>
        </div>
      </div>

      <ScrollArea className="max-h-64">
        <div className="p-2 space-y-2">
          {pendingProposals.map((proposal) => (
            <div
              key={proposal.id}
              className="border rounded-lg bg-background"
            >
              {/* Header */}
              <button
                className="w-full flex items-center gap-2 p-3 hover:bg-muted/50"
                onClick={() => setExpandedId(expandedId === proposal.id ? null : proposal.id)}
              >
                {expandedId === proposal.id ? (
                  <ChevronDown className="h-4 w-4" />
                ) : (
                  <ChevronRight className="h-4 w-4" />
                )}
                <FileText className="h-4 w-4 text-muted-foreground" />
                <span className="flex-1 text-left text-sm font-mono truncate">
                  {proposal.file_path}
                </span>
                <div className="flex gap-1">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 text-green-600 hover:text-green-700 hover:bg-green-100"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleApprove(proposal.id);
                    }}
                    disabled={processingId === proposal.id || isLoading}
                  >
                    <Check className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 text-red-600 hover:text-red-700 hover:bg-red-100"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleReject(proposal.id);
                    }}
                    disabled={processingId === proposal.id || isLoading}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              </button>

              {/* Expanded content */}
              {expandedId === proposal.id && (
                <div className="border-t p-3 space-y-3">
                  {proposal.description && (
                    <p className="text-sm text-muted-foreground">
                      {proposal.description}
                    </p>
                  )}

                  <div className="space-y-2">
                    <div className="text-xs font-medium text-muted-foreground uppercase">
                      Changes
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      {proposal.old_content && (
                        <div>
                          <div className="text-red-600 font-medium mb-1">Before</div>
                          <pre className="p-2 bg-red-50 dark:bg-red-950/20 rounded border overflow-auto max-h-40">
                            <code>{proposal.old_content.slice(0, 500)}
                              {proposal.old_content.length > 500 && '...'}
                            </code>
                          </pre>
                        </div>
                      )}
                      <div className={cn(!proposal.old_content && 'col-span-2')}>
                        <div className="text-green-600 font-medium mb-1">
                          {proposal.old_content ? 'After' : 'New File'}
                        </div>
                        <pre className="p-2 bg-green-50 dark:bg-green-950/20 rounded border overflow-auto max-h-40">
                          <code>{proposal.new_content.slice(0, 500)}
                            {proposal.new_content.length > 500 && '...'}
                          </code>
                        </pre>
                      </div>
                    </div>
                  </div>

                  <div className="flex gap-2 pt-2">
                    <Button
                      size="sm"
                      className="flex-1"
                      onClick={() => handleApprove(proposal.id)}
                      disabled={processingId === proposal.id || isLoading}
                    >
                      <Check className="h-4 w-4 mr-1" />
                      Approve & Apply
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      className="flex-1"
                      onClick={() => handleReject(proposal.id)}
                      disabled={processingId === proposal.id || isLoading}
                    >
                      <X className="h-4 w-4 mr-1" />
                      Reject
                    </Button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </ScrollArea>
    </div>
  );
}
