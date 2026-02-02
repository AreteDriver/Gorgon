import { create } from 'zustand';
import type { ChatSession, ChatMessage, ChatMode, StreamChunk } from '@/types/chat';
import { api } from '@/api/client';

interface ChatState {
  // Session state
  sessions: ChatSession[];
  activeSessionId: string | null;
  activeSession: ChatSession | null;
  messages: ChatMessage[];

  // UI state
  isLoading: boolean;
  isStreaming: boolean;
  streamingContent: string;
  streamingAgent: string | null;
  error: string | null;

  // Actions
  fetchSessions: () => Promise<void>;
  createSession: (projectPath?: string, mode?: ChatMode) => Promise<string>;
  selectSession: (sessionId: string) => Promise<void>;
  deleteSession: (sessionId: string) => Promise<void>;
  sendMessage: (content: string) => Promise<void>;
  cancelGeneration: () => void;
  clearError: () => void;
}

export const useChatStore = create<ChatState>((set, get) => ({
  // Initial state
  sessions: [],
  activeSessionId: null,
  activeSession: null,
  messages: [],
  isLoading: false,
  isStreaming: false,
  streamingContent: '',
  streamingAgent: null,
  error: null,

  fetchSessions: async () => {
    try {
      set({ isLoading: true, error: null });
      const sessions = await api.getChatSessions();
      set({ sessions, isLoading: false });
    } catch (err) {
      set({ error: 'Failed to fetch sessions', isLoading: false });
    }
  },

  createSession: async (projectPath?: string, mode: ChatMode = 'assistant') => {
    try {
      set({ isLoading: true, error: null });
      const newSession = await api.createChatSession({
        project_path: projectPath,
        mode,
      });

      set((state) => ({
        sessions: [newSession, ...state.sessions],
        activeSessionId: newSession.id,
        activeSession: newSession,
        messages: [],
        isLoading: false,
      }));

      return newSession.id;
    } catch (err) {
      set({ error: 'Failed to create session', isLoading: false });
      throw err;
    }
  },

  selectSession: async (sessionId: string) => {
    try {
      set({ isLoading: true, error: null, activeSessionId: sessionId });
      const sessionDetail = await api.getChatSession(sessionId);
      set({
        activeSession: sessionDetail,
        messages: sessionDetail.messages || [],
        isLoading: false,
      });
    } catch (err) {
      set({ error: 'Failed to load session', isLoading: false });
    }
  },

  deleteSession: async (sessionId: string) => {
    try {
      await api.deleteChatSession(sessionId);
      set((state) => ({
        sessions: state.sessions.filter((s) => s.id !== sessionId),
        activeSessionId: state.activeSessionId === sessionId ? null : state.activeSessionId,
        activeSession: state.activeSessionId === sessionId ? null : state.activeSession,
        messages: state.activeSessionId === sessionId ? [] : state.messages,
      }));
    } catch (err) {
      set({ error: 'Failed to delete session' });
    }
  },

  sendMessage: async (content: string) => {
    const { activeSessionId, messages } = get();
    if (!activeSessionId) {
      set({ error: 'No active session' });
      return;
    }

    // Add user message optimistically
    const userMessage: ChatMessage = {
      id: `temp-${Date.now()}`,
      session_id: activeSessionId,
      role: 'user',
      content,
      created_at: new Date().toISOString(),
    };

    set({
      messages: [...messages, userMessage],
      isStreaming: true,
      streamingContent: '',
      streamingAgent: null,
      error: null,
    });

    try {
      // Use fetch for SSE streaming
      const response = await fetch(`${api.getBaseUrl()}/chat/sessions/${activeSessionId}/messages`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${api.getAuthToken()}`,
        },
        body: JSON.stringify({ content }),
      });

      if (!response.ok) {
        throw new Error('Failed to send message');
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('No response body');
      }

      const decoder = new TextDecoder();
      let fullContent = '';
      let currentAgent: string | null = null;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const text = decoder.decode(value, { stream: true });
        const lines = text.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const chunk: StreamChunk = JSON.parse(line.slice(6));

              if (chunk.type === 'text' && chunk.content) {
                fullContent += chunk.content;
                set({ streamingContent: fullContent });
              }

              if (chunk.agent) {
                currentAgent = chunk.agent;
                set({ streamingAgent: chunk.agent });
              }

              if (chunk.type === 'error' && chunk.error) {
                set({ error: chunk.error });
              }

              if (chunk.type === 'done') {
                // Add assistant message to messages
                const assistantMessage: ChatMessage = {
                  id: `msg-${Date.now()}`,
                  session_id: activeSessionId,
                  role: 'assistant',
                  content: fullContent,
                  agent: currentAgent || undefined,
                  created_at: new Date().toISOString(),
                };

                set((state) => ({
                  messages: [...state.messages, assistantMessage],
                  isStreaming: false,
                  streamingContent: '',
                  streamingAgent: null,
                }));
              }
            } catch {
              // Ignore parse errors for incomplete chunks
            }
          }
        }
      }
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : 'Failed to send message',
        isStreaming: false,
      });
    }
  },

  cancelGeneration: () => {
    // TODO: Implement actual cancellation via API
    set({ isStreaming: false, streamingContent: '', streamingAgent: null });
  },

  clearError: () => {
    set({ error: null });
  },
}));
