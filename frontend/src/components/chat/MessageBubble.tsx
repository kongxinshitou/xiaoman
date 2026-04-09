import { useState } from 'react'
import { Avatar, Modal } from 'antd'
import { UserOutlined, RobotOutlined } from '@ant-design/icons'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { ChatMessage, ImageInfo } from '../../types/chat'
import SourceCitation from './SourceCitation'
import WebResultCard from './WebResultCard'
import ThinkingPanel from './ThinkingPanel'
import { parseServerTime } from '../../utils/time'

interface Props {
  message: ChatMessage
}

/** Replace [IMG_xxx] markers in text with inline image elements. */
function renderContentWithImages(content: string, imageMap: Record<string, ImageInfo>) {
  const parts = content.split(/(\[IMG_[^\]]+\])/g)
  return parts.map((part, i) => {
    const match = part.match(/^\[(IMG_[^\]]+)\]$/)
    if (match) {
      const fullId = match[1]
      const full = imageMap[fullId]
      if (full?.base64) {
        return (
          <InlineImage key={i} id={full.id} base64={full.base64} description={full.description} />
        )
      }
      // Image not available — show description text instead of leaking the raw marker
      return (
        <span key={i} style={{ color: '#64748b', fontSize: 12 }}>
          [图片: {full?.description || fullId}]
        </span>
      )
    }
    return <ReactMarkdown key={i} remarkPlugins={[remarkGfm]}>{part}</ReactMarkdown>
  })
}

function InlineImage({ id, base64, description }: { id: string; base64: string; description: string }) {
  const [previewOpen, setPreviewOpen] = useState(false)
  const src = base64.startsWith('data:') ? base64 : `data:image/png;base64,${base64}`
  return (
    <>
      <div style={{ margin: '8px 0' }}>
        <img
          src={src}
          alt={description}
          title={description}
          style={{
            maxWidth: '100%',
            maxHeight: 300,
            borderRadius: 8,
            cursor: 'pointer',
            border: '1px solid #e2e8f0',
          }}
          onClick={() => setPreviewOpen(true)}
          onError={(e) => {
            (e.target as HTMLImageElement).style.display = 'none'
          }}
        />
        <div style={{ fontSize: 11, color: '#64748b', marginTop: 2 }}>{description}</div>
      </div>
      <Modal
        open={previewOpen}
        onCancel={() => setPreviewOpen(false)}
        footer={null}
        centered
        width="auto"
        style={{ maxWidth: '90vw' }}
      >
        <img src={src} alt={description} style={{ maxWidth: '85vw', maxHeight: '80vh', display: 'block' }} />
        <div style={{ marginTop: 8, color: '#64748b', fontSize: 13 }}>{description}</div>
      </Modal>
    </>
  )
}

export default function MessageBubble({ message }: Props) {
  const isUser = message.role === 'user'
  const isStreaming = message.isStreaming
  const hasWebResults = !isUser && ((message.webResults && message.webResults.length > 0) || message.isWebSearching)

  // Build a lookup map for images in this message
  const imageMap: Record<string, ImageInfo> = {}
  for (const img of message.images || []) {
    imageMap[img.id] = img
  }
  // Trigger marker-aware rendering whenever the assistant text contains an
  // [IMG_xxx] marker — even if images haven't streamed in yet, this prevents
  // raw markers leaking into ReactMarkdown (which would italicize the
  // surrounding underscores and otherwise garble the text).
  const hasImageMarkers = !isUser && /\[IMG_[^\]]+\]/.test(message.content || '')

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
          style={{ background: 'linear-gradient(135deg, #4f46e5, #7c3aed)', flexShrink: 0, marginTop: 2 }}
          icon={<RobotOutlined />}
        />
      )}

      <div style={{ maxWidth: '82%', minWidth: 60 }}>
        {/* Web search results */}
        {hasWebResults && (
          <div style={{ marginBottom: 8 }}>
            <WebResultCard results={message.webResults || []} isSearching={message.isWebSearching} />
          </div>
        )}

        {/* Thinking + tool calls panel */}
        {!isUser && (message.thinking || (message.toolCalls && message.toolCalls.length > 0)) && (
          <ThinkingPanel thinking={message.thinking} toolCalls={message.toolCalls} isStreaming={isStreaming} />
        )}

        {/* Citations */}
        {message.citations && message.citations.length > 0 && (
          <div style={{ marginBottom: 8 }}>
            <SourceCitation citations={message.citations} />
          </div>
        )}

        {/* User attached image preview */}
        {isUser && message.imageDataUrl && (
          <div style={{ marginBottom: 6 }}>
            <img
              src={message.imageDataUrl}
              alt="attached"
              style={{ maxHeight: 160, maxWidth: 260, borderRadius: 8, border: '1px solid rgba(255,255,255,0.3)' }}
            />
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
                {hasImageMarkers
                  ? renderContentWithImages(message.content || '', imageMap)
                  : (
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {message.content || (isStreaming ? '' : '...')}
                    </ReactMarkdown>
                  )
                }
              </div>
            )}
          </div>
        )}

        {/* Timestamp */}
        <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 4, textAlign: isUser ? 'right' : 'left' }}>
          {parseServerTime(message.created_at)?.format('HH:mm') ?? ''}
        </div>
      </div>

      {isUser && (
        <Avatar size={36} style={{ background: '#e2e8f0', flexShrink: 0, marginTop: 2 }} icon={<UserOutlined style={{ color: '#64748b' }} />} />
      )}
    </div>
  )
}
