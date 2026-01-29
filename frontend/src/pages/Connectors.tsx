import { useState } from 'react';
import { Plus, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { MCPServerCard } from '@/components/mcp/MCPServerCard';
import { AddServerModal } from '@/components/mcp/AddServerModal';
import { ConfigureServerModal } from '@/components/mcp/ConfigureServerModal';
import { ToolsDrawer } from '@/components/mcp/ToolsDrawer';
import { useMCPServers, useDeleteMCPServer, useTestMCPConnection } from '@/hooks/useMCP';
import type { MCPServer } from '@/types/mcp';

export function ConnectorsPage() {
  const { data: serversData, isLoading, refetch } = useMCPServers();
  const deleteServer = useDeleteMCPServer();
  const testConnection = useTestMCPConnection();

  const [showAddModal, setShowAddModal] = useState(false);
  const [configureServer, setConfigureServer] = useState<MCPServer | null>(null);
  const [viewToolsServer, setViewToolsServer] = useState<MCPServer | null>(null);
  const [testingId, setTestingId] = useState<string | null>(null);

  // Use real API data
  const servers = serversData || [];

  const handleTest = async (server: MCPServer) => {
    setTestingId(server.id);
    try {
      await testConnection.mutateAsync(server.id);
      refetch();
    } catch {
      // Error handled by mutation
    } finally {
      setTestingId(null);
    }
  };

  const handleDelete = (server: MCPServer) => {
    if (confirm(`Remove "${server.name}" connector?`)) {
      deleteServer.mutate(server.id);
    }
  };

  const connectedCount = servers?.filter((s) => s.status === 'connected').length || 0;

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold">Service Connectors</h1>
          <p className="text-muted-foreground mt-1">
            {connectedCount} of {servers?.length || 0} services connected via MCP
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="icon" onClick={() => refetch()}>
            <RefreshCw className="w-4 h-4" />
          </Button>
          <Button onClick={() => setShowAddModal(true)}>
            <Plus className="w-4 h-4 mr-2" />
            Add Connector
          </Button>
        </div>
      </div>

      {isLoading ? (
        <div className="text-center py-12 text-muted-foreground">Loading connectors...</div>
      ) : servers?.length === 0 ? (
        <div className="text-center py-12 border-2 border-dashed rounded-lg">
          <p className="text-muted-foreground mb-4">No connectors configured yet</p>
          <Button onClick={() => setShowAddModal(true)}>
            <Plus className="w-4 h-4 mr-2" />
            Add Your First Connector
          </Button>
        </div>
      ) : (
        <div className="space-y-3">
          {servers?.map((server) => (
            <MCPServerCard
              key={server.id}
              server={server}
              onConfigure={setConfigureServer}
              onTest={handleTest}
              onViewTools={setViewToolsServer}
              onDelete={handleDelete}
              isTestingConnection={testingId === server.id}
            />
          ))}
        </div>
      )}

      {/* Modals */}
      {showAddModal && (
        <AddServerModal
          onClose={() => setShowAddModal(false)}
          onSuccess={() => {
            setShowAddModal(false);
            refetch();
          }}
        />
      )}

      {configureServer && (
        <ConfigureServerModal
          server={configureServer}
          onClose={() => setConfigureServer(null)}
          onSuccess={() => {
            setConfigureServer(null);
            refetch();
          }}
        />
      )}

      {viewToolsServer && (
        <ToolsDrawer server={viewToolsServer} onClose={() => setViewToolsServer(null)} />
      )}
    </div>
  );
}
