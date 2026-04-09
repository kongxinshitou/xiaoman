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
  PictureOutlined,
  AudioOutlined,
  AudioMutedOutlined,
} from '@ant-design/icons'
import { useSettingsStore } from '../../store/settingsStore'
import { useChatStore } from '../../store/chatStore'
import client from '../../api/client'

const { TextArea } = Input

interface Props {
  sessionId: string
  onSend: (message: string, webSearch: boolean, imageDataUrl?: string) => void
  disabled?: boolean
  isStreaming?: boolean
  onStop?: () => void
}

const ACCEPTED_TYPES = '.txt,.md,.pdf,.docx,.pptx,.jpg,.jpeg,.png,.bmp,.tiff,.gif,.webp,.xlsx,.xls'
const IMAGE_TYPES = '.jpg,.jpeg,.png,.webp,.gif,.bmp'

export default function ChatInput({ sessionId, onSend, disabled, isStreaming, onStop }: Props) {
  const { draftInputs, setDraftInput } = useChatStore()
  const [value, setValue] = useState(() => draftInputs[sessionId] || '')
  const [webSearch, setWebSearch] = useState(false)
  const [attachedFile, setAttachedFile] = useState<{ name: string; text: string } | null>(null)
  const [attachedImage, setAttachedImage] = useState<{ name: string; dataUrl: string } | null>(null)
  const [parsingFile, setParsingFile] = useState(false)
  const [isRecording, setIsRecording] = useState(false)
  const [transcribing, setTranscribing] = useState(false)
  const textAreaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const imageInputRef = useRef<HTMLInputElement>(null)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const audioChunksRef = useRef<Blob[]>([])

  // Restore draft when switching sessions
  useEffect(() => {
    setValue(draftInputs[sessionId] || '')
  }, [sessionId])
  const { selectedKbIds, knowledgeBases, selectedProviderId, providers } = useSettingsStore()

  const handleSend = useCallback(() => {
    const trimmed = value.trim()
    if (!trimmed && !attachedFile && !attachedImage) return
    if (disabled || isStreaming) return

    let finalMessage = trimmed
    if (attachedFile) {
      finalMessage = `[附件: ${attachedFile.name}]\n${attachedFile.text}\n---\n${trimmed}`
    }
    onSend(finalMessage, webSearch, attachedImage?.dataUrl)
    setValue('')
    setDraftInput(sessionId, '')
    setAttachedFile(null)
    setAttachedImage(null)
  }, [value, disabled, isStreaming, onSend, webSearch, attachedFile, attachedImage, sessionId, setDraftInput])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
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

  const handleImageChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    e.target.value = ''

    setParsingFile(true)
    try {
      const formData = new FormData()
      formData.append('file', file)
      const res = await client.post<{ filename: string; data_url: string; mime_type: string }>(
        '/chat/upload-image',
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' } }
      )
      setAttachedImage({ name: res.data.filename, dataUrl: res.data.data_url })
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } }
      message.error(`图片上传失败: ${e?.response?.data?.detail || '未知错误'}`)
    } finally {
      setParsingFile(false)
    }
  }

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream)
      audioChunksRef.current = []
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data)
      }
      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop())
        const blob = new Blob(audioChunksRef.current, { type: 'audio/webm' })
        await transcribeAudio(blob)
      }
      recorder.start()
      mediaRecorderRef.current = recorder
      setIsRecording(true)
    } catch {
      message.error('无法访问麦克风，请检查浏览器权限')
    }
  }

  const stopRecording = () => {
    mediaRecorderRef.current?.stop()
    mediaRecorderRef.current = null
    setIsRecording(false)
  }

  const transcribeAudio = async (blob: Blob) => {
    setTranscribing(true)
    try {
      const formData = new FormData()
      formData.append('file', blob, 'recording.webm')
      const res = await client.post<{ text: string }>(
        '/chat/transcribe',
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' } }
      )
      const transcribed = res.data.text.trim()
      if (transcribed) {
        setValue((prev) => prev ? `${prev} ${transcribed}` : transcribed)
        message.success('语音识别完成，请确认后发送')
      } else {
        message.warning('未识别到语音内容')
      }
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } }
      message.error(`语音识别失败: ${e?.response?.data?.detail || '未知错误'}`)
    } finally {
      setTranscribing(false)
    }
  }

  return (
    <div style={{ padding: '12px 16px', background: 'white', borderTop: '1px solid #f0f0f0' }}>
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

      {/* Attached file / image indicators */}
      {(attachedFile || attachedImage) && (
        <div style={{ marginBottom: 6, display: 'flex', gap: 4, flexWrap: 'wrap' }}>
          {attachedFile && (
            <Tag color="blue" closable onClose={() => setAttachedFile(null)} style={{ fontSize: 12 }}>
              📄 {attachedFile.name}
            </Tag>
          )}
          {attachedImage && (
            <Tag color="purple" closable onClose={() => setAttachedImage(null)} style={{ fontSize: 12 }}>
              🖼️ {attachedImage.name}
            </Tag>
          )}
        </div>
      )}

      {/* Attached image preview */}
      {attachedImage && (
        <div style={{ marginBottom: 8 }}>
          <img
            src={attachedImage.dataUrl}
            alt="preview"
            style={{ maxHeight: 80, maxWidth: 160, borderRadius: 6, border: '1px solid #e2e8f0' }}
          />
        </div>
      )}

      {/* Input area */}
      <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
        {/* Document attachment */}
        <input ref={fileInputRef} type="file" accept={ACCEPTED_TYPES} style={{ display: 'none' }} onChange={handleFileChange} />
        {/* Image attachment for vision */}
        <input ref={imageInputRef} type="file" accept={IMAGE_TYPES} style={{ display: 'none' }} onChange={handleImageChange} />

        <Tooltip title="附加文档">
          <Button
            size="small"
            icon={parsingFile && !attachedImage ? <LoadingOutlined /> : <PaperClipOutlined />}
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

        <Tooltip title="上传图片（视觉理解）">
          <Button
            size="small"
            icon={parsingFile && !attachedFile ? <LoadingOutlined /> : <PictureOutlined />}
            onClick={() => imageInputRef.current?.click()}
            disabled={parsingFile || disabled}
            style={{
              borderRadius: 8,
              flexShrink: 0,
              height: 36,
              borderColor: attachedImage ? '#7c3aed' : undefined,
              color: attachedImage ? '#7c3aed' : undefined,
              background: attachedImage ? '#f5f3ff' : undefined,
            }}
          />
        </Tooltip>

        <Tooltip title={isRecording ? '点击停止录音' : transcribing ? '识别中...' : '语音输入'}>
          <Button
            size="small"
            icon={transcribing ? <LoadingOutlined /> : isRecording ? <AudioMutedOutlined /> : <AudioOutlined />}
            onClick={isRecording ? stopRecording : startRecording}
            disabled={transcribing || disabled}
            danger={isRecording}
            style={{
              borderRadius: 8,
              flexShrink: 0,
              height: 36,
              animation: isRecording ? 'pulse 1s infinite' : undefined,
            }}
          />
        </Tooltip>

        <TextArea
          ref={textAreaRef as any}
          value={value}
          onChange={(e) => { setValue(e.target.value); setDraftInput(sessionId, e.target.value) }}
          onKeyDown={handleKeyDown}
          placeholder={
            attachedImage
              ? '输入关于图片的问题... (Enter 发送)'
              : attachedFile
              ? '输入问题... (已附加文件)'
              : isRecording
              ? '正在录音...'
              : '输入消息... (Enter 发送, Shift+Enter 换行)'
          }
          autoSize={{ minRows: 2, maxRows: 8 }}
          disabled={disabled || isRecording}
          style={{ flex: 1, borderRadius: 12, resize: 'none', fontSize: 14 }}
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
              disabled={(!value.trim() && !attachedFile && !attachedImage) || disabled}
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
