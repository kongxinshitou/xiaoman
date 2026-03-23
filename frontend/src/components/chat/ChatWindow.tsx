import { useEffect, useRef } from 'react'
import { Empty, Spin } from 'antd'
import { RobotOutlined } from '@ant-design/icons'
import { useChatStore } from '../../store/chatStore'
import { chatApi } from '../../api/chat'
import MessageBubble from './MessageBubble'
import ChatInput from './ChatInput'
import { useStreamingChat } from '../../hooks/useStreamingChat'
import { useSettingsStore } from '../../store/settingsStore'

interface Props {
  sessionId: string
}

export default function ChatWindow({ sessionId }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)
  const { messages, isLoading, setMessages, addMessage, streamingMessageId } = useChatStore()
  const { selectedProviderId, selectedKbIds } = useSettingsStore()
  const { sendMessage, stopStreaming } = useStreamingChat()

  const sessionMessages = messages[sessionId] || []

  useEffect(() => {
    // Load messages for session
    chatApi.getMessages(sessionId).then((msgs) => {
      setMessages(sessionId, msgs)
    }).catch(() => {})
  }, [sessionId])

  useEffect(() => {
    // Auto-scroll to bottom
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [sessionMessages.length, sessionMessages[sessionMessages.length - 1]?.content])

  const handleSend = async (message: string) => {
    // Optimistically add user message
    const userMsg = {
      id: Date.now().toString(),
      session_id: sessionId,
      role: 'user' as const,
      content: message,
      meta: '{}',
      created_at: new Date().toISOString(),
    }
    addMessage(sessionId, userMsg)

    await sendMessage(sessionId, message, {
      providerId: selectedProviderId || undefined,
      kbIds: selectedKbIds.length > 0 ? selectedKbIds : undefined,
    })
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: '#f8fafc' }}>
      {/* Messages area */}
      <div style={{ flex: 1, overflow: 'auto', padding: '20px 24px' }}>
        {sessionMessages.length === 0 && !isLoading ? (
          <div
            style={{
              height: '100%',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 16,
            }}
          >
            <div
              style={{
                width: 72,
                height: 72,
                background: 'linear-gradient(135deg, #4f46e5, #7c3aed)',
                borderRadius: 20,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <RobotOutlined style={{ fontSize: 36, color: 'white' }} />
            </div>
            <div style={{ textAlign: 'center' }}>
              <h3 style={{ margin: 0, color: '#1e293b', fontSize: 18 }}>晓曼智能助手</h3>
              <p style={{ color: '#64748b', margin: '8px 0 0', fontSize: 14 }}>
                我可以帮您查询知识库、执行运维操作、或直接回答问题
              </p>
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'center' }}>
              {['如何排查服务故障？', '查看最近的部署记录', '帮我写一个监控脚本'].map((q) => (
                <div
                  key={q}
                  onClick={() => handleSend(q)}
                  style={{
                    padding: '8px 14px',
                    background: 'white',
                    border: '1px solid #e2e8f0',
                    borderRadius: 20,
                    cursor: 'pointer',
                    fontSize: 13,
                    color: '#4f46e5',
                    transition: 'all 0.2s',
                  }}
                  onMouseEnter={(e) => {
                    ;(e.target as HTMLDivElement).style.background = '#eef2ff'
                    ;(e.target as HTMLDivElement).style.borderColor = '#4f46e5'
                  }}
                  onMouseLeave={(e) => {
                    ;(e.target as HTMLDivElement).style.background = 'white'
                    ;(e.target as HTMLDivElement).style.borderColor = '#e2e8f0'
                  }}
                >
                  {q}
                </div>
              ))}
            </div>
          </div>
        ) : (
          <>
            {sessionMessages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}
            {isLoading && !streamingMessageId && (
              <div style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: 16 }}>
                <Spin size="small" style={{ marginLeft: 46 }} />
              </div>
            )}
          </>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <ChatInput
        sessionId={sessionId}
        onSend={handleSend}
        disabled={false}
        isStreaming={!!streamingMessageId}
        onStop={stopStreaming}
      />
    </div>
  )
}
