import { useCallback, useRef } from 'react'
import { useChatStore } from '../store/chatStore'
import type { ChatMessage, Citation, ToolCallInfo, WebResult, ImageInfo } from '../types/chat'
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
    addImage,
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
        imageDataUrl?: string   // base64 data URL for vision input
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
        images: [],
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
            // If there's an attached image, embed it in the message as vision content
            message: options?.imageDataUrl
              ? `[图片]\n${message}`
              : message,
            provider_id: options?.providerId,
            kb_ids: options?.kbIds,
            stream: true,
            web_search: options?.webSearch ?? false,
            image_data_url: options?.imageDataUrl,
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

        // ── Robust SSE parser ────────────────────────────────────────────────
        // An SSE event is terminated by a blank line (\n\n). We MUST process
        // whole events at a time — the previous implementation kept `eventType`
        // scoped to a single reader.read() iteration, so large payloads (e.g.
        // a ~500 KB base64 image_event) whose `event:` header and `data:` line
        // spanned multiple network reads would lose their event type and be
        // silently dropped. Buffer until we see \n\n, then dispatch the block.
        const dispatchEvent = (eventType: string, dataStr: string) => {
          if (!dataStr) return
          let data: unknown
          try {
            data = JSON.parse(dataStr)
          } catch {
            return
          }
          const d = data as Record<string, unknown>
          if (eventType === 'token') {
            appendToken(sessionId, (d.delta as string) || '')
          } else if (eventType === 'thinking') {
            appendThinking(sessionId, (d.delta as string) || '')
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
          } else if (eventType === 'image') {
            addImage(sessionId, data as ImageInfo)
          } else if (eventType === 'done') {
            finalizeMessage(sessionId, streamingId)
            const session = sessions.find((s) => s.id === sessionId)
            if (session) {
              updateSession({ ...session, updated_at: new Date().toISOString() })
            }
          } else if (eventType === 'error') {
            appendToken(sessionId, `\n[错误] ${(d.message as string) || ''}`)
            finalizeMessage(sessionId, streamingId)
          }
        }

        const parseEventBlock = (block: string) => {
          // Per SSE spec, an event block is a sequence of field lines.
          // We only care about `event:` and `data:` here. `data:` fields may
          // appear on multiple lines and should be joined with \n.
          let eventType = 'message'
          const dataLines: string[] = []
          for (const rawLine of block.split('\n')) {
            const line = rawLine.endsWith('\r') ? rawLine.slice(0, -1) : rawLine
            if (!line || line.startsWith(':')) continue
            if (line.startsWith('event: ')) {
              eventType = line.slice(7).trim()
            } else if (line.startsWith('event:')) {
              eventType = line.slice(6).trim()
            } else if (line.startsWith('data: ')) {
              dataLines.push(line.slice(6))
            } else if (line.startsWith('data:')) {
              dataLines.push(line.slice(5))
            }
          }
          dispatchEvent(eventType, dataLines.join('\n'))
        }

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })

          // Drain every complete event currently in the buffer.
          let sep = buffer.indexOf('\n\n')
          while (sep !== -1) {
            const block = buffer.slice(0, sep)
            buffer = buffer.slice(sep + 2)
            if (block.length > 0) parseEventBlock(block)
            sep = buffer.indexOf('\n\n')
          }
        }

        // Flush any trailing event that didn't end with \n\n (defensive).
        if (buffer.trim().length > 0) {
          parseEventBlock(buffer)
          buffer = ''
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
    [addMessage, setStreamingMessageId, appendToken, appendThinking, addCitation, addToolCall, updateLastToolCall, addWebResult, setWebSearching, addImage, finalizeMessage, setLoading, updateSession, sessions],
  )

  const stopStreaming = useCallback(() => {
    abortRef.current?.abort()
  }, [])

  return { sendMessage, stopStreaming }
}
