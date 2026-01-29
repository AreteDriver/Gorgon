import { useState, useEffect } from 'react';
import {
  Brain,
  Code,
  TestTube,
  Search,
  BarChart3,
  PieChart,
  FileOutput,
  Settings2,
  Power,
  Sparkles,
  Database,
  Server,
  Shield,
  ArrowRightLeft,
  Boxes,
  Bot,
  Loader2,
  AlertCircle,
  type LucideIcon,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import type { AgentDefinition, AgentProvider } from '@/types';
import { useAgentDefinitions } from '@/hooks/useApi';

// Map icon names from backend to Lucide components
const ICON_MAP: Record<string, LucideIcon> = {
  Brain,
  Code,
  TestTube,
  Search,
  BarChart3,
  PieChart,
  FileOutput,
  Database,
  Server,
  Shield,
  ArrowRightLeft,
  Boxes,
  Bot,
};

function getIcon(iconName: string): LucideIcon {
  return ICON_MAP[iconName] || Bot;
}

interface AgentConfig {
  enabled: boolean;
  provider: AgentProvider;
  model: string;
  temperature: number;
  maxTokens: number;
}

const defaultConfig: AgentConfig = {
  enabled: true,
  provider: 'openai',
  model: 'gpt-4',
  temperature: 0.7,
  maxTokens: 4096,
};

export function AgentsPage() {
  const { data: agents = [], isLoading: loading, error } = useAgentDefinitions();
  const [configs, setConfigs] = useState<Record<string, AgentConfig>>({});
  const [editingAgent, setEditingAgent] = useState<string | null>(null);

  // Initialize configs when agents are loaded
  useEffect(() => {
    if (agents.length > 0 && Object.keys(configs).length === 0) {
      const initialConfigs: Record<string, AgentConfig> = {};
      agents.forEach((agent) => {
        initialConfigs[agent.id] = { ...defaultConfig };
      });
      setConfigs(initialConfigs);
    }
  }, [agents, configs]);

  const enabledCount = Object.values(configs).filter((c) => c.enabled).length;

  const handleToggle = (agentId: string) => {
    setConfigs((prev) => ({
      ...prev,
      [agentId]: { ...prev[agentId], enabled: !prev[agentId].enabled },
    }));
  };

  const handleConfigChange = (agentId: string, updates: Partial<AgentConfig>) => {
    setConfigs((prev) => ({
      ...prev,
      [agentId]: { ...prev[agentId], ...updates },
    }));
  };

  if (loading) {
    return (
      <div className="p-6 max-w-6xl mx-auto flex items-center justify-center min-h-[400px]">
        <div className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin" />
          <span>Loading agents...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 max-w-6xl mx-auto flex items-center justify-center min-h-[400px]">
        <div className="flex items-center gap-2 text-destructive">
          <AlertCircle className="h-5 w-5" />
          <span>Failed to load agent definitions</span>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold">Agents</h1>
          <p className="text-muted-foreground mt-1">
            {enabledCount} of {agents.length} agents enabled
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-primary" />
          <span className="text-sm text-muted-foreground">Powered by OpenAI & Anthropic</span>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {agents.map((agent) => (
          <AgentCard
            key={agent.id}
            agent={agent}
            config={configs[agent.id] || defaultConfig}
            isEditing={editingAgent === agent.id}
            onToggle={() => handleToggle(agent.id)}
            onEdit={() => setEditingAgent(editingAgent === agent.id ? null : agent.id)}
            onConfigChange={(updates) => handleConfigChange(agent.id, updates)}
          />
        ))}
      </div>
    </div>
  );
}

interface AgentCardProps {
  agent: AgentDefinition;
  config: AgentConfig;
  isEditing: boolean;
  onToggle: () => void;
  onEdit: () => void;
  onConfigChange: (updates: Partial<AgentConfig>) => void;
}

function AgentCard({ agent, config, isEditing, onToggle, onEdit, onConfigChange }: AgentCardProps) {
  const Icon = getIcon(agent.icon);

  return (
    <Card className={`transition-all ${!config.enabled ? 'opacity-60' : ''}`}>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div
              className="p-2 rounded-lg"
              style={{ backgroundColor: `${agent.color}20`, color: agent.color }}
            >
              <Icon className="h-5 w-5" />
            </div>
            <div>
              <CardTitle className="text-lg">{agent.name}</CardTitle>
              <CardDescription className="text-xs mt-0.5">
                {config.provider} / {config.model}
              </CardDescription>
            </div>
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={onToggle}
            title={config.enabled ? 'Disable agent' : 'Enable agent'}
          >
            <Power className={`h-4 w-4 ${config.enabled ? 'text-green-500' : 'text-muted-foreground'}`} />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-muted-foreground">{agent.description}</p>

        <div className="flex flex-wrap gap-1">
          {agent.capabilities.map((cap) => (
            <span
              key={cap}
              className="text-xs px-2 py-0.5 rounded-full bg-muted text-muted-foreground"
            >
              {cap}
            </span>
          ))}
        </div>

        <div className="flex items-center justify-between pt-2 border-t">
          <div className="text-xs text-muted-foreground">
            Temp: {config.temperature} | Max: {config.maxTokens.toLocaleString()}
          </div>
          <Button variant="ghost" size="sm" onClick={onEdit}>
            <Settings2 className="h-4 w-4 mr-1" />
            {isEditing ? 'Close' : 'Configure'}
          </Button>
        </div>

        {isEditing && (
          <div className="pt-3 border-t space-y-3">
            <div>
              <label className="text-xs font-medium mb-1 block">Provider</label>
              <select
                value={config.provider}
                onChange={(e) => onConfigChange({ provider: e.target.value as AgentProvider })}
                className="w-full border rounded px-2 py-1.5 text-sm bg-background"
              >
                <option value="openai">OpenAI</option>
                <option value="anthropic">Anthropic</option>
              </select>
            </div>

            <div>
              <label className="text-xs font-medium mb-1 block">Model</label>
              <select
                value={config.model}
                onChange={(e) => onConfigChange({ model: e.target.value })}
                className="w-full border rounded px-2 py-1.5 text-sm bg-background"
              >
                {config.provider === 'openai' ? (
                  <>
                    <option value="gpt-4">GPT-4</option>
                    <option value="gpt-4-turbo">GPT-4 Turbo</option>
                    <option value="gpt-4-vision">GPT-4 Vision</option>
                    <option value="gpt-3.5-turbo">GPT-3.5 Turbo</option>
                  </>
                ) : (
                  <>
                    <option value="claude-3-opus">Claude 3 Opus</option>
                    <option value="claude-3-sonnet">Claude 3 Sonnet</option>
                    <option value="claude-3-haiku">Claude 3 Haiku</option>
                  </>
                )}
              </select>
            </div>

            <div>
              <label className="text-xs font-medium mb-1 block">
                Temperature: {config.temperature}
              </label>
              <input
                type="range"
                min="0"
                max="1"
                step="0.1"
                value={config.temperature}
                onChange={(e) => onConfigChange({ temperature: parseFloat(e.target.value) })}
                className="w-full"
              />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>Precise</span>
                <span>Creative</span>
              </div>
            </div>

            <div>
              <label className="text-xs font-medium mb-1 block">Max Tokens</label>
              <select
                value={config.maxTokens}
                onChange={(e) => onConfigChange({ maxTokens: parseInt(e.target.value) })}
                className="w-full border rounded px-2 py-1.5 text-sm bg-background"
              >
                <option value="1024">1,024</option>
                <option value="2048">2,048</option>
                <option value="4096">4,096</option>
                <option value="8192">8,192</option>
                <option value="16384">16,384</option>
              </select>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
