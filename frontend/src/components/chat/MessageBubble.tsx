import { Avatar } from 'antd'
import { UserOutlined, RobotOutlined } from '@ant-design/icons'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { ChatMessage } from '../../types/chat'
import SourceCitation from './SourceCitation'
import WebResultCard from './WebResultCard'
import ThinkingPanel from './ThinkingPanel'
import { parseServerTime } from '../../utils/time'

interface Props {
  message: ChatMessage
}

export default function MessageBubble({ message }: Props) {
  const isUser = message.role === 'user'
  const isStreaming = message.isStreaming
  const hasWebResults = !isUser && ((message.webResults && message.webResults.length > 0) || message.isWebSearching)

  return (
    <div
      className="message-enter"
      style={{
        display: 'flex',
        justifyContent: isUser ? 'flex-end' : 'flex-start',
        marginBottom: 20,
        alignItems: 'flex-start',
        gap: 10,
      }}
    >
      {!isUser && (
        <Avatar
          size={36}
          style={{
            background: 'linear-gradient(135deg, #4f46e5, #7c3aed)',
            flexShrink: 0,
            marginTop: 2,
          }}
          icon={<RobotOutlined />}
        />
      )}

      <div style={{ maxWidth: '82%', minWidth: 60 }}>
        {/* Web search results */}
        {hasWebResults && (
          <div style={{ marginBottom: 8 }}>
            <WebResultCard
              results={message.webResults || []}
              isSearching={message.isWebSearching}
            />
          </div>
        )}

        {/* Thinking + tool calls panel */}
        {!isUser && (message.thinking || (message.toolCalls && message.toolCalls.length > 0)) && (
          <ThinkingPanel
            thinking={message.thinking}
            toolCalls={message.toolCalls}
            isStreaming={isStreaming}
          />
        )}

        {/* Citations */}
        {message.citations && message.citations.length > 0 && (
          <div style={{ marginBottom: 8 }}>
            <SourceCitation citations={message.citations} />
          </div>
        )}

        {/* Message bubble */}
        {(message.content || isStreaming) && (
          <div
            style={{
              background: isUser ? 'linear-gradient(135deg, #4f46e5, #6366f1)' : 'white',
              color: isUser ? 'white' : '#1a1a1a',
              padding: '10px 14px',
              borderRadius: isUser ? '18px 18px 4px 18px' : '4px 18px 18px 18px',
              boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
              wordBreak: 'break-word',
            }}
          >
            {isUser ? (
              <span style={{ whiteSpace: 'pre-wrap', fontSize: 14 }}>{message.content}</span>
            ) : (
              <div
                className={`markdown-body${isStreaming ? ' streaming-cursor' : ''}`}
                style={{ fontSize: 14 }}
              >
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {message.content || (isStreaming ? '' : '...')}
                </ReactMarkdown>
              </div>
            )}
          </div>
        )}

        {/* Timestamp */}
        <div
          style={{
            fontSize: 11,
            color: '#94a3b8',
            marginTop: 4,
            textAlign: isUser ? 'right' : 'left',
          }}
        >
          {parseServerTime(message.created_at)?.format('HH:mm') ?? ''}
        </div>
      </div>

      {isUser && (
        <Avatar
          size={36}
          style={{ background: '#e2e8f0', flexShrink: 0, marginTop: 2 }}
          icon={<UserOutlined style={{ color: '#64748b' }} />}
        />
      )}
    </div>
  )
}
