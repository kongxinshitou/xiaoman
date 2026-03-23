import { Tag, Space } from 'antd'
import { ThunderboltOutlined, LoadingOutlined, CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons'
import type { ToolCallInfo } from '../../types/chat'

interface Props {
  toolCall: ToolCallInfo
}

export default function ToolCallCard({ toolCall }: Props) {
  const statusIcon = {
    running: <LoadingOutlined spin />,
    done: <CheckCircleOutlined />,
    error: <CloseCircleOutlined />,
  }[toolCall.status]

  const statusColor = {
    running: 'processing',
    done: 'success',
    error: 'error',
  }[toolCall.status] as 'processing' | 'success' | 'error'

  return (
    <div
      style={{
        background: '#f8faff',
        border: '1px solid #e0e7ff',
        borderRadius: 8,
        padding: '8px 12px',
        display: 'inline-flex',
        alignItems: 'center',
        gap: 8,
        fontSize: 12,
        color: '#4f46e5',
      }}
    >
      <ThunderboltOutlined />
      <Space size={6}>
        <span>工具调用:</span>
        <Tag color="purple" style={{ margin: 0, fontSize: 11 }}>
          {toolCall.tool}
        </Tag>
        <Tag color={statusColor} icon={statusIcon} style={{ margin: 0, fontSize: 11 }}>
          {toolCall.status === 'running' ? '执行中' : toolCall.status === 'done' ? '完成' : '错误'}
        </Tag>
      </Space>
    </div>
  )
}
