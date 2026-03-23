import { create } from 'zustand'
import type { ChatSession, ChatMessage, Citation, ToolCallInfo } from '../types/chat'

interface ChatState {
  sessions: ChatSession[]
  activeSessionId: string | null
  messages: Record<string, ChatMessage[]>
  streamingMessageId: string | null
  isLoading: boolean

  setSessions: (sessions: ChatSession[]) => void
  addSession: (session: ChatSession) => void
  updateSession: (session: ChatSession) => void
  removeSession: (sessionId: string) => void
  setActiveSession: (sessionId: string | null) => void

  setMessages: (sessionId: string, messages: ChatMessage[]) => void
  addMessage: (sessionId: string, message: ChatMessage) => void
  setStreamingMessageId: (id: string | null) => void
  appendToken: (sessionId: string, delta: string) => void
  addCitation: (sessionId: string, citation: Citation) => void
  setToolCall: (sessionId: string, toolCall: ToolCallInfo) => void
  finalizeMessage: (sessionId: string, messageId: string) => void

  setLoading: (loading: boolean) => void
  getActiveMessages: () => ChatMessage[]
}

export const useChatStore = create<ChatState>((set, get) => ({
  sessions: [],
  activeSessionId: null,
  messages: {},
  streamingMessageId: null,
  isLoading: false,

  setSessions: (sessions) => set({ sessions }),
  addSession: (session) => set((s) => ({ sessions: [session, ...s.sessions] })),
  updateSession: (session) =>
    set((s) => ({
      sessions: s.sessions.map((ses) => (ses.id === session.id ? session : ses)),
    })),
  removeSession: (sessionId) =>
    set((s) => ({
      sessions: s.sessions.filter((ses) => ses.id !== sessionId),
      activeSessionId: s.activeSessionId === sessionId ? null : s.activeSessionId,
    })),
  setActiveSession: (sessionId) => set({ activeSessionId: sessionId }),

  setMessages: (sessionId, messages) =>
    set((s) => ({ messages: { ...s.messages, [sessionId]: messages } })),
  addMessage: (sessionId, message) =>
    set((s) => ({
      messages: {
        ...s.messages,
        [sessionId]: [...(s.messages[sessionId] || []), message],
      },
    })),
  setStreamingMessageId: (id) => set({ streamingMessageId: id }),

  appendToken: (sessionId, delta) =>
    set((s) => {
      const msgs = s.messages[sessionId] || []
      const streamingId = s.streamingMessageId
      if (!streamingId) return {}
      return {
        messages: {
          ...s.messages,
          [sessionId]: msgs.map((msg) =>
            msg.id === streamingId
              ? { ...msg, content: msg.content + delta }
              : msg,
          ),
        },
      }
    }),

  addCitation: (sessionId, citation) =>
    set((s) => {
      const msgs = s.messages[sessionId] || []
      const streamingId = s.streamingMessageId
      if (!streamingId) return {}
      return {
        messages: {
          ...s.messages,
          [sessionId]: msgs.map((msg) =>
            msg.id === streamingId
              ? { ...msg, citations: [...(msg.citations || []), citation] }
              : msg,
          ),
        },
      }
    }),

  setToolCall: (sessionId, toolCall) =>
    set((s) => {
      const msgs = s.messages[sessionId] || []
      const streamingId = s.streamingMessageId
      if (!streamingId) return {}
      return {
        messages: {
          ...s.messages,
          [sessionId]: msgs.map((msg) =>
            msg.id === streamingId ? { ...msg, toolCall } : msg,
          ),
        },
      }
    }),

  finalizeMessage: (sessionId, messageId) =>
    set((s) => ({
      streamingMessageId: null,
      messages: {
        ...s.messages,
        [sessionId]: (s.messages[sessionId] || []).map((msg) =>
          msg.id === messageId ? { ...msg, isStreaming: false } : msg,
        ),
      },
    })),

  setLoading: (loading) => set({ isLoading: loading }),

  getActiveMessages: () => {
    const { activeSessionId, messages } = get()
    if (!activeSessionId) return []
    return messages[activeSessionId] || []
  },
}))
