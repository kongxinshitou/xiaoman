import { useState, useRef, useCallback } from 'react'
import { Button, Input, Space, Tooltip, Select } from 'antd'
import {
  SendOutlined,
  StopOutlined,
  DatabaseOutlined,
} from '@ant-design/icons'
import { useChatStore } from '../../store/chatStore'
import { useSettingsStore } from '../../store/settingsStore'

const { TextArea } = Input

interface Props {
  sessionId: string
  onSend: (message: string) => void
  disabled?: boolean
  isStreaming?: boolean
  onStop?: () => void
}

export default function ChatInput({ sessionId, onSend, disabled, isStreaming, onStop }: Props) {
  const [value, setValue] = useState('')
  const textAreaRef = useRef<HTMLTextAreaElement>(null)
  const { selectedKbIds, toggleKbSelection, knowledgeBases, selectedProviderId, providers } =
    useSettingsStore()

  const handleSend = useCallback(() => {
    const trimmed = value.trim()
    if (!trimmed || disabled || isStreaming) return
    onSend(trimmed)
    setValue('')
  }, [value, disabled, isStreaming, onSend])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div
      style={{
        padding: '12px 16px',
        background: 'white',
        borderTop: '1px solid #f0f0f0',
      }}
    >
      {/* KB and Provider selectors */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 8, alignItems: 'center' }}>
        <Select
          mode="multiple"
          placeholder="选择知识库 (可选)"
          value={selectedKbIds}
          onChange={(ids) => useSettingsStore.getState().setSelectedKbIds(ids)}
          size="small"
          style={{ flex: 1 }}
          maxTagCount={2}
          allowClear
          options={knowledgeBases.map((kb) => ({ value: kb.id, label: kb.name }))}
          suffixIcon={<DatabaseOutlined />}
        />
        <Select
          placeholder="默认模型"
          value={selectedProviderId || undefined}
          onChange={(id) => useSettingsStore.getState().setSelectedProvider(id)}
          size="small"
          style={{ width: 160 }}
          allowClear
          options={providers
            .filter((p) => p.is_active)
            .map((p) => ({ value: p.id, label: p.name }))}
        />
      </div>

      {/* Input area */}
      <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
        <TextArea
          ref={textAreaRef as any}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入消息... (Enter 发送, Shift+Enter 换行)"
          autoSize={{ minRows: 1, maxRows: 6 }}
          disabled={disabled}
          style={{
            flex: 1,
            borderRadius: 12,
            resize: 'none',
            fontSize: 14,
          }}
        />
        {isStreaming ? (
          <Button
            type="primary"
            danger
            icon={<StopOutlined />}
            onClick={onStop}
            style={{ borderRadius: 10, height: 36 }}
          >
            停止
          </Button>
        ) : (
          <Tooltip title="发送 (Enter)">
            <Button
              type="primary"
              icon={<SendOutlined />}
              onClick={handleSend}
              disabled={!value.trim() || disabled}
              style={{
                borderRadius: 10,
                height: 36,
                background: 'linear-gradient(135deg, #4f46e5, #6366f1)',
                border: 'none',
              }}
            >
              发送
            </Button>
          </Tooltip>
        )}
      </div>
    </div>
  )
}
