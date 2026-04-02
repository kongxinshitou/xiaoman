import { useState, useRef, useCallback, useEffect } from 'react'
import { Button, Input, Tooltip, Select, Tag, message } from 'antd'
import {
  SendOutlined,
  StopOutlined,
  DatabaseOutlined,
  GlobalOutlined,
  PaperClipOutlined,
  CloseOutlined,
  LoadingOutlined,
} from '@ant-design/icons'
import { useSettingsStore } from '../../store/settingsStore'
import { useChatStore } from '../../store/chatStore'
import client from '../../api/client'

const { TextArea } = Input

interface Props {
  sessionId: string
  onSend: (message: string, webSearch: boolean) => void
  disabled?: boolean
  isStreaming?: boolean
  onStop?: () => void
}

const ACCEPTED_TYPES = '.txt,.md,.pdf,.docx,.pptx,.jpg,.jpeg,.png,.bmp,.tiff,.gif,.webp'

export default function ChatInput({ sessionId, onSend, disabled, isStreaming, onStop }: Props) {
  const { draftInputs, setDraftInput } = useChatStore()
  const [value, setValue] = useState(() => draftInputs[sessionId] || '')
  const [webSearch, setWebSearch] = useState(false)
  const [attachedFile, setAttachedFile] = useState<{ name: string; text: string } | null>(null)
  const [parsingFile, setParsingFile] = useState(false)
  const textAreaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Restore draft when switching sessions
  useEffect(() => {
    setValue(draftInputs[sessionId] || '')
  }, [sessionId])
  const { selectedKbIds, knowledgeBases, selectedProviderId, providers } =
    useSettingsStore()

  const handleSend = useCallback(() => {
    const trimmed = value.trim()
    if (!trimmed && !attachedFile) return
    if (disabled || isStreaming) return

    let finalMessage = trimmed
    if (attachedFile) {
      finalMessage = `[附件: ${attachedFile.name}]\n${attachedFile.text}\n---\n${trimmed}`
    }
    onSend(finalMessage, webSearch)
    setValue('')
    setDraftInput(sessionId, '')
    setAttachedFile(null)
  }, [value, disabled, isStreaming, onSend, webSearch, attachedFile, sessionId, setDraftInput])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    // Reset input so same file can be re-selected
    e.target.value = ''

    setParsingFile(true)
    try {
      const formData = new FormData()
      formData.append('file', file)
      const res = await client.post<{ text: string; filename: string; truncated: boolean }>(
        '/chat/parse-file',
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' } }
      )
      setAttachedFile({ name: res.data.filename, text: res.data.text })
      if (res.data.truncated) {
        message.warning('文件内容较长，已截取前 8000 字符作为上下文')
      }
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } }
      message.error(`解析文件失败: ${e?.response?.data?.detail || '未知错误'}`)
    } finally {
      setParsingFile(false)
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
      {/* KB, Provider selectors and Web Search toggle */}
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
        <Tooltip title={webSearch ? '关闭联网搜索' : '开启联网搜索'}>
          <Button
            size="small"
            icon={<GlobalOutlined />}
            onClick={() => setWebSearch((v) => !v)}
            style={{
              borderRadius: 6,
              flexShrink: 0,
              borderColor: webSearch ? '#0284c7' : undefined,
              color: webSearch ? '#0284c7' : undefined,
              background: webSearch ? '#f0f9ff' : undefined,
            }}
          >
            联网
          </Button>
        </Tooltip>
      </div>

      {/* Attached file indicator */}
      {attachedFile && (
        <div style={{ marginBottom: 6 }}>
          <Tag
            color="blue"
            closable
            onClose={() => setAttachedFile(null)}
            style={{ fontSize: 12 }}
          >
            📄 {attachedFile.name}
          </Tag>
        </div>
      )}

      {/* Input area */}
      <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
        <input
          ref={fileInputRef}
          type="file"
          accept={ACCEPTED_TYPES}
          style={{ display: 'none' }}
          onChange={handleFileChange}
        />
        <Tooltip title="附加文件">
          <Button
            size="small"
            icon={parsingFile ? <LoadingOutlined /> : <PaperClipOutlined />}
            onClick={() => fileInputRef.current?.click()}
            disabled={parsingFile || disabled}
            style={{
              borderRadius: 8,
              flexShrink: 0,
              height: 36,
              borderColor: attachedFile ? '#4f46e5' : undefined,
              color: attachedFile ? '#4f46e5' : undefined,
              background: attachedFile ? '#eef2ff' : undefined,
            }}
          />
        </Tooltip>
        <TextArea
          ref={textAreaRef as any}
          value={value}
          onChange={(e) => { setValue(e.target.value); setDraftInput(sessionId, e.target.value) }}
          onKeyDown={handleKeyDown}
          placeholder={attachedFile ? '输入问题... (已附加文件)' : '输入消息... (Enter 发送, Shift+Enter 换行)'}
          autoSize={{ minRows: 2, maxRows: 8 }}
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
              disabled={(!value.trim() && !attachedFile) || disabled}
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
