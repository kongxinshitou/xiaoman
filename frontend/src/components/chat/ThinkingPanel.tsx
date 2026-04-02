import { useState } from 'react'
import { LoadingOutlined } from '@ant-design/icons'
import type { ToolCallInfo } from '../../types/chat'
import ToolCallCard from './ToolCallCard'

interface Props {
  thinking?: string
  toolCalls?: ToolCallInfo[]
  isStreaming?: boolean
}

export default function ThinkingPanel({ thinking, toolCalls, isStreaming }: Props) {
  const [expanded, setExpanded] = useState(false)

  const hasThinking = !!thinking
  const toolCount = toolCalls?.length ?? 0
  const hasContent = hasThinking || toolCount > 0

  if (!hasContent) return null

  const isActive = isStreaming && (
    toolCalls?.some((tc) => tc.status === 'running') || (!toolCount && hasThinking)
  )

  const headerLabel = isActive
    ? toolCount > 0
      ? `正在调用工具 · 已执行 ${toolCount} 步`
      : '正在思考中...'
    : [
        hasThinking ? '深度思考' : null,
        toolCount > 0 ? `已调用 ${toolCount} 个工具` : null,
      ]
        .filter(Boolean)
        .join(' · ')

  return (
    <div
      style={{
        marginBottom: 8,
        border: '1px solid #e0e7ff',
        borderRadius: 10,
        overflow: 'hidden',
        background: '#f8faff',
      }}
    >
      {/* Header toggle */}
      <button
        onClick={() => setExpanded((v) => !v)}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '8px 12px',
          background: 'transparent',
          border: 'none',
          cursor: 'pointer',
          fontSize: 12,
          color: '#4f46e5',
          textAlign: 'left',
        }}
      >
        {isActive ? (
          <LoadingOutlined spin style={{ fontSize: 13 }} />
        ) : (
          <span style={{ fontSize: 13 }}>🔮</span>
        )}
        <span style={{ flex: 1, fontWeight: 500 }}>{headerLabel}</span>
        <span style={{ fontSize: 11, color: '#94a3b8' }}>{expanded ? '收起 ▴' : '展开 ▾'}</span>
      </button>

      {/* Expanded content */}
      {expanded && (
        <div style={{ padding: '4px 12px 12px' }}>
          {/* Thinking text */}
          {hasThinking && (
            <div style={{ marginBottom: toolCount > 0 ? 10 : 0 }}>
              <div
                style={{
                  fontSize: 11,
                  color: '#64748b',
                  marginBottom: 4,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4,
                }}
              >
                💭 推理过程
              </div>
              <div
                style={{
                  background: '#f1f5f9',
                  border: '1px solid #e2e8f0',
                  borderRadius: 6,
                  padding: '8px 10px',
                  fontSize: 12,
                  color: '#475569',
                  fontFamily: 'ui-monospace, monospace',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                  maxHeight: 240,
                  overflowY: 'auto',
                }}
              >
                {thinking}
              </div>
            </div>
          )}

          {/* Tool calls list */}
          {toolCount > 0 && (
            <div>
              {hasThinking && (
                <div style={{ fontSize: 11, color: '#64748b', marginBottom: 6, marginTop: 4 }}>
                  ⚡ 工具调用记录
                </div>
              )}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {toolCalls!.map((tc, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ fontSize: 11, color: '#94a3b8', minWidth: 24 }}>
                      #{i + 1}
                    </span>
                    <ToolCallCard toolCall={tc} />
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
