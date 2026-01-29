import { useState } from 'react';
import { Moon, Sun, Monitor, Bell, Eye, Database, Key, Save, Trash2, Check, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { usePreferencesStore } from '@/stores';
import {
  useUpdatePreferences,
  useApiKeyStatus,
  useSetApiKey,
  useDeleteApiKey,
} from '@/hooks/useApi';
import type { ApiKeyStatus } from '@/api/client';

export function SettingsPage() {
  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Settings</h1>
        <p className="text-muted-foreground mt-1">
          Manage your preferences and configuration
        </p>
      </div>

      <AppearanceSection />
      <NotificationsSection />
      <DisplaySection />
      <APIKeysSection />
      <DataSection />
    </div>
  );
}

function AppearanceSection() {
  const { theme, setTheme } = usePreferencesStore();
  const updatePreferences = useUpdatePreferences();

  const themes: Array<{ value: 'light' | 'dark' | 'system'; label: string; icon: typeof Sun }> = [
    { value: 'light', label: 'Light', icon: Sun },
    { value: 'dark', label: 'Dark', icon: Moon },
    { value: 'system', label: 'System', icon: Monitor },
  ];

  const handleThemeChange = (newTheme: 'light' | 'dark' | 'system') => {
    setTheme(newTheme);
    // Persist to backend
    updatePreferences.mutate({ theme: newTheme });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Sun className="h-5 w-5" />
          Appearance
        </CardTitle>
        <CardDescription>Customize how Gorgon looks</CardDescription>
      </CardHeader>
      <CardContent>
        <div>
          <label className="text-sm font-medium mb-3 block">Theme</label>
          <div className="flex gap-2">
            {themes.map(({ value, label, icon: Icon }) => (
              <Button
                key={value}
                variant={theme === value ? 'default' : 'outline'}
                className="flex-1"
                onClick={() => handleThemeChange(value)}
                disabled={updatePreferences.isPending}
              >
                <Icon className="h-4 w-4 mr-2" />
                {label}
              </Button>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function NotificationsSection() {
  const { notifications, setNotification } = usePreferencesStore();
  const updatePreferences = useUpdatePreferences();

  const notificationOptions = [
    {
      key: 'executionComplete' as const,
      apiKey: 'execution_complete' as const,
      label: 'Execution Complete',
      description: 'Notify when a workflow execution finishes successfully',
    },
    {
      key: 'executionFailed' as const,
      apiKey: 'execution_failed' as const,
      label: 'Execution Failed',
      description: 'Notify when a workflow execution fails',
    },
    {
      key: 'budgetAlert' as const,
      apiKey: 'budget_alert' as const,
      label: 'Budget Alerts',
      description: 'Notify when spending approaches budget limits',
    },
  ];

  const handleNotificationChange = (
    key: keyof typeof notifications,
    apiKey: 'execution_complete' | 'execution_failed' | 'budget_alert',
    value: boolean
  ) => {
    setNotification(key, value);
    // Persist to backend
    updatePreferences.mutate({
      notifications: { [apiKey]: value },
    });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Bell className="h-5 w-5" />
          Notifications
        </CardTitle>
        <CardDescription>Choose what notifications you receive</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {notificationOptions.map(({ key, apiKey, label, description }) => (
          <div key={key} className="flex items-center justify-between">
            <div>
              <p className="font-medium text-sm">{label}</p>
              <p className="text-sm text-muted-foreground">{description}</p>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={notifications[key]}
                onChange={(e) => handleNotificationChange(key, apiKey, e.target.checked)}
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-muted peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-ring rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-background after:border-border after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary"></div>
            </label>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function DisplaySection() {
  const { compactView, setCompactView, showCosts, setShowCosts, defaultPageSize, setDefaultPageSize } =
    usePreferencesStore();
  const updatePreferences = useUpdatePreferences();

  const handleCompactViewChange = (value: boolean) => {
    setCompactView(value);
    updatePreferences.mutate({ compact_view: value });
  };

  const handleShowCostsChange = (value: boolean) => {
    setShowCosts(value);
    updatePreferences.mutate({ show_costs: value });
  };

  const handlePageSizeChange = (value: number) => {
    setDefaultPageSize(value);
    updatePreferences.mutate({ default_page_size: value });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Eye className="h-5 w-5" />
          Display
        </CardTitle>
        <CardDescription>Configure how data is displayed</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="font-medium text-sm">Compact View</p>
            <p className="text-sm text-muted-foreground">Use smaller spacing and fonts</p>
          </div>
          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={compactView}
              onChange={(e) => handleCompactViewChange(e.target.checked)}
              className="sr-only peer"
            />
            <div className="w-11 h-6 bg-muted peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-ring rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-background after:border-border after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary"></div>
          </label>
        </div>

        <div className="flex items-center justify-between">
          <div>
            <p className="font-medium text-sm">Show Costs</p>
            <p className="text-sm text-muted-foreground">Display cost information in executions</p>
          </div>
          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={showCosts}
              onChange={(e) => handleShowCostsChange(e.target.checked)}
              className="sr-only peer"
            />
            <div className="w-11 h-6 bg-muted peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-ring rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-background after:border-border after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary"></div>
          </label>
        </div>

        <div className="flex items-center justify-between">
          <div>
            <p className="font-medium text-sm">Default Page Size</p>
            <p className="text-sm text-muted-foreground">Number of items per page in lists</p>
          </div>
          <select
            value={defaultPageSize}
            onChange={(e) => handlePageSizeChange(Number(e.target.value))}
            className="border rounded px-3 py-1.5 text-sm bg-background"
          >
            <option value={10}>10</option>
            <option value={20}>20</option>
            <option value={50}>50</option>
            <option value={100}>100</option>
          </select>
        </div>
      </CardContent>
    </Card>
  );
}

function APIKeysSection() {
  const { data: keyStatus, isLoading: isLoadingStatus } = useApiKeyStatus();
  const setApiKey = useSetApiKey();
  const deleteApiKey = useDeleteApiKey();

  const [keys, setKeys] = useState({
    openai: '',
    anthropic: '',
    github: '',
  });
  const [showKeys, setShowKeys] = useState({
    openai: false,
    anthropic: false,
    github: false,
  });
  const [savingKey, setSavingKey] = useState<string | null>(null);

  const apiKeyFields = [
    { key: 'openai' as const, label: 'OpenAI API Key', placeholder: 'sk-...' },
    { key: 'anthropic' as const, label: 'Anthropic API Key', placeholder: 'sk-ant-...' },
    { key: 'github' as const, label: 'GitHub Token', placeholder: 'ghp_...' },
  ];

  const handleSaveKey = async (provider: 'openai' | 'anthropic' | 'github') => {
    const key = keys[provider];
    if (!key || key.length < 10) return;

    setSavingKey(provider);
    try {
      await setApiKey.mutateAsync({ provider, key });
      // Clear the input after successful save
      setKeys((prev) => ({ ...prev, [provider]: '' }));
    } catch (error) {
      console.error('Failed to save API key:', error);
    } finally {
      setSavingKey(null);
    }
  };

  const handleDeleteKey = async (provider: string) => {
    if (!confirm(`Are you sure you want to delete the ${provider} API key?`)) return;

    try {
      await deleteApiKey.mutateAsync(provider);
    } catch (error) {
      console.error('Failed to delete API key:', error);
    }
  };

  const getKeyConfigured = (provider: keyof ApiKeyStatus): boolean => {
    return keyStatus?.[provider] ?? false;
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Key className="h-5 w-5" />
          API Keys
        </CardTitle>
        <CardDescription>Configure API keys for AI providers and integrations</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {isLoadingStatus ? (
          <div className="flex items-center justify-center py-4">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : (
          apiKeyFields.map(({ key, label, placeholder }) => (
            <div key={key}>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-sm font-medium">{label}</label>
                {getKeyConfigured(key) && (
                  <span className="flex items-center gap-1 text-xs text-green-600">
                    <Check className="h-3 w-3" />
                    Configured
                  </span>
                )}
              </div>
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <input
                    type={showKeys[key] ? 'text' : 'password'}
                    value={keys[key]}
                    onChange={(e) => setKeys({ ...keys, [key]: e.target.value })}
                    placeholder={getKeyConfigured(key) ? '(configured - enter new key to update)' : placeholder}
                    className="w-full border rounded px-3 py-2 text-sm font-mono pr-16 bg-background"
                  />
                  <button
                    type="button"
                    onClick={() => setShowKeys({ ...showKeys, [key]: !showKeys[key] })}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-muted-foreground hover:text-foreground"
                  >
                    {showKeys[key] ? 'Hide' : 'Show'}
                  </button>
                </div>
                <Button
                  size="sm"
                  onClick={() => handleSaveKey(key)}
                  disabled={!keys[key] || keys[key].length < 10 || savingKey === key}
                >
                  {savingKey === key ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Save className="h-4 w-4" />
                  )}
                </Button>
                {getKeyConfigured(key) && (
                  <Button
                    size="sm"
                    variant="destructive"
                    onClick={() => handleDeleteKey(key)}
                    disabled={deleteApiKey.isPending}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                )}
              </div>
            </div>
          ))
        )}

        <p className="text-xs text-muted-foreground">
          API keys are encrypted and stored securely. They are only used for communicating with the
          respective services.
        </p>
      </CardContent>
    </Card>
  );
}

function DataSection() {
  const [clearing, setClearing] = useState(false);

  const handleClearCache = () => {
    setClearing(true);
    // Clear local storage cache
    setTimeout(() => {
      localStorage.removeItem('gorgon-preferences');
      setClearing(false);
      window.location.reload();
    }, 1000);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Database className="h-5 w-5" />
          Data Management
        </CardTitle>
        <CardDescription>Manage local data and cache</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="font-medium text-sm">Clear Local Cache</p>
            <p className="text-sm text-muted-foreground">
              Reset all preferences and cached data. This will reload the page.
            </p>
          </div>
          <Button variant="destructive" size="sm" onClick={handleClearCache} disabled={clearing}>
            <Trash2 className="h-4 w-4 mr-2" />
            {clearing ? 'Clearing...' : 'Clear Cache'}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
