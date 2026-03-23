import { Modal, Form, Input, Select } from 'antd'
import type { KnowledgeBase, KnowledgeBaseCreate } from '../../types/knowledge'
import { useEffect } from 'react'

interface Props {
  open: boolean
  onClose: () => void
  onSubmit: (data: KnowledgeBaseCreate) => Promise<void>
  initialValues?: KnowledgeBase | null
  loading?: boolean
}

const EMBED_MODELS = [
  { value: 'text2vec-base-chinese', label: 'text2vec-base-chinese (推荐)' },
  { value: 'text-embedding-ada-002', label: 'OpenAI Ada-002' },
  { value: 'text-embedding-3-small', label: 'OpenAI Embedding-3-small' },
]

export default function KnowledgeBaseForm({ open, onClose, onSubmit, initialValues, loading }: Props) {
  const [form] = Form.useForm()
  const isEdit = !!initialValues

  useEffect(() => {
    if (open) {
      if (initialValues) {
        form.setFieldsValue({
          name: initialValues.name,
          description: initialValues.description,
          embed_model: initialValues.embed_model,
        })
      } else {
        form.resetFields()
      }
    }
  }, [open, initialValues])

  const handleOk = async () => {
    const values = await form.validateFields()
    await onSubmit(values)
    form.resetFields()
  }

  return (
    <Modal
      title={isEdit ? '编辑知识库' : '新建知识库'}
      open={open}
      onOk={handleOk}
      onCancel={onClose}
      confirmLoading={loading}
      okText={isEdit ? '保存' : '创建'}
      cancelText="取消"
      width={480}
    >
      <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
        <Form.Item name="name" label="知识库名称" rules={[{ required: true, message: '请输入知识库名称' }]}>
          <Input placeholder="例如：产品手册、运维文档..." />
        </Form.Item>
        <Form.Item name="description" label="描述">
          <Input.TextArea rows={3} placeholder="简要描述知识库内容..." />
        </Form.Item>
        <Form.Item name="embed_model" label="嵌入模型" initialValue="text2vec-base-chinese">
          <Select options={EMBED_MODELS} />
        </Form.Item>
      </Form>
    </Modal>
  )
}
