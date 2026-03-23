import { Upload, message } from 'antd'
import { InboxOutlined } from '@ant-design/icons'
import type { UploadFile } from 'antd'
import { knowledgeApi } from '../../api/knowledge'

const { Dragger } = Upload

interface Props {
  kbId: string
  onUploadComplete: () => void
}

const ACCEPTED_TYPES = '.txt,.md,.pdf,.docx,.pptx'

export default function DocumentUploader({ kbId, onUploadComplete }: Props) {
  const handleUpload = async (file: File): Promise<boolean> => {
    try {
      await knowledgeApi.uploadDocument(kbId, file)
      message.success(`${file.name} 上传成功`)
      onUploadComplete()
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } }
      message.error(`上传失败: ${error?.response?.data?.detail || '未知错误'}`)
    }
    return false
  }

  return (
    <Dragger
      multiple
      accept={ACCEPTED_TYPES}
      beforeUpload={handleUpload}
      showUploadList={false}
      style={{ marginBottom: 16 }}
    >
      <p className="ant-upload-drag-icon">
        <InboxOutlined style={{ color: '#4f46e5' }} />
      </p>
      <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
      <p className="ant-upload-hint">
        支持 PDF、Word (.docx)、PowerPoint (.pptx)、Markdown (.md)、纯文本 (.txt)
        <br />
        单个文件最大 50MB
      </p>
    </Dragger>
  )
}
