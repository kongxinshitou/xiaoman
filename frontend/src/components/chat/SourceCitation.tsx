import { Tag, Tooltip } from 'antd'
import { FileTextOutlined } from '@ant-design/icons'
import type { Citation } from '../../types/chat'

interface Props {
  citations: Citation[]
}

export default function SourceCitation({ citations }: Props) {
  if (!citations || citations.length === 0) return null

  return (
    <div
      style={{
        background: '#fefce8',
        border: '1px solid #fde68a',
        borderRadius: 8,
        padding: '6px 10px',
      }}
    >
      <div style={{ fontSize: 11, color: '#92400e', marginBottom: 4, display: 'flex', alignItems: 'center', gap: 4 }}>
        <FileTextOutlined />
        <span>参考来源 ({citations.length})</span>
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
        {citations.map((c, i) => (
          <Tooltip key={i} title={c.text} placement="top">
            <Tag
              style={{
                cursor: 'pointer',
                fontSize: 11,
                background: '#fef3c7',
                borderColor: '#fcd34d',
                color: '#92400e',
              }}
            >
              [{i + 1}] 相关度 {Math.round(c.score * 100)}%
            </Tag>
          </Tooltip>
        ))}
      </div>
    </div>
  )
}
