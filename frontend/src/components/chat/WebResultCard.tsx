import { useState } from 'react'
import { Tag, Spin } from 'antd'
import { GlobalOutlined, LinkOutlined, CaretDownOutlined, CaretRightOutlined } from '@ant-design/icons'
import type { WebResult } from '../../types/chat'

interface Props {
  results: WebResult[]
  isSearching?: boolean
}

export default function WebResultCard({ results, isSearching }: Props) {
  const [collapsed, setCollapsed] = useState(false)

  const validResults = results.filter((r) => r.title || r.snippet)

  return (
    <div
      style={{
        background: '#f0f9ff',
        border: '1px solid #bae6fd',
        borderRadius: 10,
        marginBottom: 8,
        overflow: 'hidden',
      }}
    >
      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          padding: '7px 12px',
          cursor: 'pointer',
          userSelect: 'none',
        }}
        onClick={() => setCollapsed((v) => !v)}
      >
        {isSearching ? (
          <Spin size="small" />
        ) : (
          <GlobalOutlined style={{ color: '#0284c7', fontSize: 13 }} />
        )}
        <span style={{ fontSize: 12, color: '#0369a1', fontWeight: 500 }}>
          {isSearching ? '正在联网搜索...' : `联网搜索结果 (${validResults.length} 条)`}
        </span>
        {!isSearching && (
          <span style={{ marginLeft: 'auto', color: '#94a3b8' }}>
            {collapsed ? <CaretRightOutlined /> : <CaretDownOutlined />}
          </span>
        )}
      </div>

      {/* Results list */}
      {!collapsed && !isSearching && validResults.length > 0 && (
        <div style={{ borderTop: '1px solid #bae6fd', padding: '6px 0' }}>
          {validResults.map((r, idx) => (
            <div
              key={idx}
              style={{
                padding: '6px 12px',
                borderBottom: idx < validResults.length - 1 ? '1px solid #e0f2fe' : 'none',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 6 }}>
                <Tag
                  color="blue"
                  style={{ fontSize: 10, flexShrink: 0, marginTop: 1, lineHeight: '16px' }}
                >
                  {idx + 1}
                </Tag>
                <div style={{ minWidth: 0 }}>
                  {r.url ? (
                    <a
                      href={r.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{
                        fontSize: 12,
                        fontWeight: 500,
                        color: '#0369a1',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 3,
                        marginBottom: 2,
                        wordBreak: 'break-all',
                      }}
                    >
                      <LinkOutlined style={{ flexShrink: 0 }} />
                      {r.title || r.url}
                    </a>
                  ) : (
                    <span style={{ fontSize: 12, fontWeight: 500, color: '#1e293b' }}>
                      {r.title}
                    </span>
                  )}
                  {r.snippet && (
                    <p
                      style={{
                        margin: 0,
                        fontSize: 11,
                        color: '#475569',
                        lineHeight: 1.5,
                        display: '-webkit-box',
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: 'vertical',
                        overflow: 'hidden',
                      }}
                    >
                      {r.snippet}
                    </p>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
