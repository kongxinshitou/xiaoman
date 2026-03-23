import client from './client'
import type { ChatSession, ChatMessage } from '../types/chat'

export const chatApi = {
  createSession: async (title = '新对话', active_provider_id?: string) => {
    const res = await client.post<ChatSession>('/chat/sessions', { title, active_provider_id })
    return res.data
  },

  listSessions: async () => {
    const res = await client.get<ChatSession[]>('/chat/sessions')
    return res.data
  },

  getSession: async (sessionId: string) => {
    const res = await client.get<ChatSession>(`/chat/sessions/${sessionId}`)
    return res.data
  },

  updateSession: async (sessionId: string, data: { title?: string; active_provider_id?: string }) => {
    const res = await client.patch<ChatSession>(`/chat/sessions/${sessionId}`, data)
    return res.data
  },

  deleteSession: async (sessionId: string) => {
    await client.delete(`/chat/sessions/${sessionId}`)
  },

  getMessages: async (sessionId: string) => {
    const res = await client.get<ChatMessage[]>(`/chat/sessions/${sessionId}/messages`)
    return res.data
  },
}
