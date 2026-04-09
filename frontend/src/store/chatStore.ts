import { create } from 'zustand'
import type { ChatSession, ChatMessage, Citation, ToolCallInfo, WebResult, ImageInfo } from '../types/chat'

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
  appendThinking: (sessionId: string, delta: string) => void
  addCitation: (sessionId: string, citation: Citation) => void
  addToolCall: (sessionId: string, toolCall: ToolCallInfo) => void
  updateLastToolCall: (sessionId: string, toolCall: ToolCallInfo) => void
  addWebResult: (sessionId: string, result: WebResult) => void
  setWebSearching: (sessionId: string, searching: boolean) => void
  addImage: (sessionId: string, image: ImageInfo) => void
  finalizeMessage: (sessionId: string, messageId: string) => void

  setLoading: (loading: boolean) => void
  getActiveMessages: () => ChatMessage[]

  draftInputs: Record<string, string>
  setDraftInput: (sessionId: string, value: string) => void
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

  appendThinking: (sessionId, delta) =>
    set((s) => {
      const msgs = s.messages[sessionId] || []
      const streamingId = s.streamingMessageId
      if (!streamingId) return {}
      return {
        messages: {
          ...s.messages,
          [sessionId]: msgs.map((msg) =>
            msg.id === streamingId
              ? { ...msg, thinking: (msg.thinking || '') + delta }
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

  addToolCall: (sessionId, toolCall) =>
    set((s) => {
      const msgs = s.messages[sessionId] || []
      const streamingId = s.streamingMessageId
      if (!streamingId) return {}
      return {
        messages: {
          ...s.messages,
          [sessionId]: msgs.map((msg) =>
            msg.id === streamingId
              ? { ...msg, toolCalls: [...(msg.toolCalls || []), toolCall] }
              : msg,
          ),
        },
      }
    }),

  updateLastToolCall: (sessionId, toolCall) =>
    set((s) => {
      const msgs = s.messages[sessionId] || []
      const streamingId = s.streamingMessageId
      if (!streamingId) return {}
      return {
        messages: {
          ...s.messages,
          [sessionId]: msgs.map((msg) => {
            if (msg.id !== streamingId) return msg
            const prev = msg.toolCalls || []
            if (prev.length === 0) return { ...msg, toolCalls: [toolCall] }
            // Find the last tool call with the matching tool name to update
            let targetIdx = -1
            for (let i = prev.length - 1; i >= 0; i--) {
              if (prev[i].tool === toolCall.tool) {
                targetIdx = i
                break
              }
            }
            if (targetIdx === -1) targetIdx = prev.length - 1
            return {
              ...msg,
              toolCalls: prev.map((tc, i) => (i === targetIdx ? toolCall : tc)),
            }
          }),
        },
      }
    }),

  addWebResult: (sessionId, result) =>
    set((s) => {
      const msgs = s.messages[sessionId] || []
      const streamingId = s.streamingMessageId
      if (!streamingId) return {}
      return {
        messages: {
          ...s.messages,
          [sessionId]: msgs.map((msg) =>
            msg.id === streamingId
              ? { ...msg, webResults: [...(msg.webResults || []), result], isWebSearching: false }
              : msg,
          ),
        },
      }
    }),

  setWebSearching: (sessionId, searching) =>
    set((s) => {
      const msgs = s.messages[sessionId] || []
      const streamingId = s.streamingMessageId
      if (!streamingId) return {}
      return {
        messages: {
          ...s.messages,
          [sessionId]: msgs.map((msg) =>
            msg.id === streamingId ? { ...msg, isWebSearching: searching } : msg,
          ),
        },
      }
    }),

  addImage: (sessionId, image) =>
    set((s) => {
      const msgs = s.messages[sessionId] || []
      const streamingId = s.streamingMessageId
      if (!streamingId) return {}
      return {
        messages: {
          ...s.messages,
          [sessionId]: msgs.map((msg) =>
            msg.id === streamingId
              ? { ...msg, images: [...(msg.images || []), image] }
              : msg,
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

  draftInputs: {},
  setDraftInput: (sessionId, value) =>
    set((s) => ({ draftInputs: { ...s.draftInputs, [sessionId]: value } })),

  getActiveMessages: () => {
    const { activeSessionId, messages } = get()
    if (!activeSessionId) return []
    return messages[activeSessionId] || []
  },
}))
