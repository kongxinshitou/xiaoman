import { useState, useCallback } from 'react'
import { Upload, Progress, Tag, Typography, Button } from 'antd'
import {
  InboxOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  LoadingOutlined,
  ClearOutlined,
} from '@ant-design/icons'
import { knowledgeApi } from '../../api/knowledge'

const { Dragger } = Upload
const { Text } = Typography

interface Props {
  kbId: string
  onUploadComplete: () => void
}

interface FileState {
  status: 'uploading' | 'done' | 'error'
  progress: number
  error?: string
}

const ACCEPTED_TYPES = '.txt,.md,.pdf,.docx,.pptx,.xlsx,.xls,.jpg,.jpeg,.png,.bmp,.tiff,.gif,.webp'

export default function DocumentUploader({ kbId, onUploadComplete }: Props) {
  const [fileStates, setFileStates] = useState<Record<string, FileState>>({})

  const updateFile = useCallback((name: string, patch: Partial<FileState>) => {
    setFileStates((prev) => ({
      ...prev,
      [name]: { ...prev[name], ...patch } as FileState,
    }))
  }, [])

  const uploadOne = async (file: File): Promise<void> => {
    const key = `${file.name}-${file.size}`
    setFileStates((prev) => ({ ...prev, [key]: { status: 'uploading', progress: 0 } }))
    try {
      await knowledgeApi.uploadDocument(kbId, file, (p) => updateFile(key, { progress: p }))
      updateFile(key, { status: 'done', progress: 100 })
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } }
      updateFile(key, { status: 'error', error: e?.response?.data?.detail || '上传失败' })
    }
  }

  const handleBeforeUpload = useCallback(
    (_file: File, fileList: File[]) => {
      if (fileList[0] === _file) {
        Promise.allSettled(fileList.map(uploadOne)).then(() => {
          onUploadComplete()
        })
      }
      return false
    },
    [kbId, onUploadComplete]
  )

  const clearCompleted = useCallback(() => {
    setFileStates((prev) => {
      const next: Record<string, FileState> = {}
      for (const [key, state] of Object.entries(prev)) {
        if (state.status === 'uploading') {
          next[key] = state
        }
      }
      return next
    })
  }, [])

  const activeFiles = Object.entries(fileStates)
  const hasCompleted = activeFiles.some(([, s]) => s.status === 'done' || s.status === 'error')

  return (
    <div style={{ marginBottom: 16 }}>
      <Dragger
        multiple
        accept={ACCEPTED_TYPES}
        beforeUpload={handleBeforeUpload}
        showUploadList={false}
        style={{ padding: 0 }}
      >
        <div style={{ padding: '24px 16px', textAlign: 'center' }}>
          <InboxOutlined style={{ fontSize: 40, color: '#4f46e5', display: 'block', marginBottom: 12 }} />
          <Text style={{ fontSize: 14, fontWeight: 500, display: 'block' }}>
            点击或拖拽文件上传
          </Text>
          <Text type="secondary" style={{ fontSize: 12 }}>
            支持 PDF、Word、PPT、Excel、Markdown、TXT、图片（OCR）
          </Text>
          <br />
          <Text type="secondary" style={{ fontSize: 11 }}>
            单文件最大 50MB
          </Text>
        </div>
      </Dragger>

      {activeFiles.length > 0 && (
        <div style={{ marginTop: 12 }}>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: 6,
            }}
          >
            <Text type="secondary" style={{ fontSize: 12 }}>
              上传队列（{activeFiles.length} 个文件）
            </Text>
            {hasCompleted && (
              <Button
                type="text"
                size="small"
                icon={<ClearOutlined />}
                onClick={clearCompleted}
                style={{ fontSize: 12, color: '#94a3b8', padding: '0 4px' }}
              >
                清除已完成
              </Button>
            )}
          </div>
          {activeFiles.map(([key, state]) => {
            const displayName = key.replace(/-\d+$/, '')
            const rowBg =
              state.status === 'error'
                ? '#fff5f5'
                : state.status === 'done'
                ? '#f0fdf4'
                : '#f8fafc'
            return (
              <div
                key={key}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '6px 8px',
                  borderRadius: 6,
                  background: rowBg,
                  marginBottom: 4,
                }}
              >
                <div style={{ width: 16, flexShrink: 0 }}>
                  {state.status === 'uploading' && (
                    <LoadingOutlined style={{ color: '#4f46e5', fontSize: 13 }} />
                  )}
                  {state.status === 'done' && (
                    <CheckCircleOutlined style={{ color: '#22c55e', fontSize: 13 }} />
                  )}
                  {state.status === 'error' && (
                    <CloseCircleOutlined style={{ color: '#ef4444', fontSize: 13 }} />
                  )}
                </div>
                <Text
                  style={{
                    flex: 1,
                    fontSize: 12,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                  title={displayName}
                >
                  {displayName}
                </Text>
                {state.status === 'uploading' && (
                  <Progress
                    percent={state.progress}
                    size="small"
                    style={{ width: 100, margin: 0 }}
                    showInfo={false}
                    strokeColor="#4f46e5"
                  />
                )}
                {state.status === 'done' && (
                  <Tag color="success" style={{ fontSize: 11, margin: 0 }}>
                    完成
                  </Tag>
                )}
                {state.status === 'error' && (
                  <Tag color="error" style={{ fontSize: 11, margin: 0 }} title={state.error}>
                    失败
                  </Tag>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
