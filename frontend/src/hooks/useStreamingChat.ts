import { useCallback, useRef } from 'react'
import { useChatStore } from '../store/chatStore'
import type { ChatMessage, Citation, ToolCallInfo, WebResult } from '../types/chat'
// Simple ID generator
function generateId(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2)
}

export function useStreamingChat() {
  const abortRef = useRef<AbortController | null>(null)
  const {
    addMessage,
    setStreamingMessageId,
    appendToken,
    appendThinking,
    addCitation,
    addToolCall,
    updateLastToolCall,
    addWebResult,
    setWebSearching,
    finalizeMessage,
    setLoading,
    updateSession,
    sessions,
  } = useChatStore()

  const sendMessage = useCallback(
    async (
      sessionId: string,
      message: string,
      options?: {
        providerId?: string
        kbIds?: string[]
        webSearch?: boolean
      },
    ) => {
      const token = localStorage.getItem('xiaoman_token')
      if (!token) return

      // Create placeholder streaming message
      const streamingId = generateId()
      const streamingMsg: ChatMessage = {
        id: streamingId,
        session_id: sessionId,
        role: 'assistant',
        content: '',
        meta: '{}',
        created_at: new Date().toISOString(),
        isStreaming: true,
        citations: [],
        toolCalls: [],
      }

      setStreamingMessageId(streamingId)
      addMessage(sessionId, streamingMsg)
      setLoading(true)

      abortRef.current = new AbortController()

      try {
        const response = await fetch('/api/v1/chat/stream', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            session_id: sessionId,
            message,
            provider_id: options?.providerId,
            kb_ids: options?.kbIds,
            stream: true,
            web_search: options?.webSearch ?? false,
          }),
          signal: abortRef.current.signal,
        })

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`)
        }

        const reader = response.body?.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        if (!reader) throw new Error('No response body')

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() || ''

          let eventType = ''
          for (const line of lines) {
            if (line.startsWith('event: ')) {
              eventType = line.slice(7).trim()
            } else if (line.startsWith('data: ')) {
              const dataStr = line.slice(6).trim()
              try {
                const data = JSON.parse(dataStr)
                if (eventType === 'token') {
                  appendToken(sessionId, data.delta || '')
                } else if (eventType === 'thinking') {
                  appendThinking(sessionId, data.delta || '')
                } else if (eventType === 'citation') {
                  addCitation(sessionId, data as Citation)
                } else if (eventType === 'tool_call') {
                  const toolCall = data as ToolCallInfo
                  if (toolCall.message === '正在调用工具...') {
                    addToolCall(sessionId, toolCall)
                  } else {
                    updateLastToolCall(sessionId, toolCall)
                  }
                } else if (eventType === 'web_search_start') {
                  setWebSearching(sessionId, true)
                } else if (eventType === 'web_result') {
                  addWebResult(sessionId, data as WebResult)
                } else if (eventType === 'done') {
                  finalizeMessage(sessionId, streamingId)
                  // Update session title if changed
                  const session = sessions.find((s) => s.id === sessionId)
                  if (session) {
                    updateSession({ ...session, updated_at: new Date().toISOString() })
                  }
                } else if (eventType === 'error') {
                  appendToken(sessionId, `\n[错误] ${data.message}`)
                  finalizeMessage(sessionId, streamingId)
                }
              } catch {
                // Ignore parse errors
              }
              eventType = ''
            }
          }
        }
      } catch (err: unknown) {
        if (err instanceof Error && err.name !== 'AbortError') {
          appendToken(sessionId, `\n[连接错误] ${err.message}`)
        }
        finalizeMessage(sessionId, streamingId)
      } finally {
        setLoading(false)
        abortRef.current = null
      }
    },
    [addMessage, setStreamingMessageId, appendToken, appendThinking, addCitation, addToolCall, updateLastToolCall, addWebResult, setWebSearching, finalizeMessage, setLoading, updateSession, sessions],
  )

  const stopStreaming = useCallback(() => {
    abortRef.current?.abort()
  }, [])

  return { sendMessage, stopStreaming }
}
