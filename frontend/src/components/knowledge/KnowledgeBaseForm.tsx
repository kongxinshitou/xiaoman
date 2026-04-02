import { Modal, Form, Input, InputNumber, Select, Divider, Typography } from 'antd'
import type { KnowledgeBase, KnowledgeBaseCreate } from '../../types/knowledge'
import type { EmbedProvider } from '../../types/embed'
import type { OCRProvider } from '../../types/ocr'
import { useEffect } from 'react'

const { Text } = Typography

interface Props {
  open: boolean
  onClose: () => void
  onSubmit: (data: KnowledgeBaseCreate) => Promise<void>
  initialValues?: KnowledgeBase | null
  loading?: boolean
  embedProviders?: EmbedProvider[]
  ocrProviders?: OCRProvider[]
}

export default function KnowledgeBaseForm({
  open,
  onClose,
  onSubmit,
  initialValues,
  loading,
  embedProviders = [],
  ocrProviders = [],
}: Props) {
  const [form] = Form.useForm()
  const isEdit = !!initialValues

  useEffect(() => {
    if (open) {
      if (initialValues) {
        form.setFieldsValue({
          name: initialValues.name,
          description: initialValues.description,
          embed_provider_id: initialValues.embed_provider_id || null,
          ocr_provider_id: initialValues.ocr_provider_id || null,
          chunk_size: initialValues.chunk_size ?? 500,
          chunk_overlap: initialValues.chunk_overlap ?? 50,
          top_k: initialValues.top_k ?? 5,
        })
      } else {
        form.resetFields()
      }
    }
  }, [open, initialValues])

  const handleOk = async () => {
    const values = await form.validateFields()
    // Convert empty string to null
    if (!values.embed_provider_id) values.embed_provider_id = null
    if (!values.ocr_provider_id) values.ocr_provider_id = null
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
      width={520}
    >
      <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
        <Form.Item name="name" label="知识库名称" rules={[{ required: true, message: '请输入知识库名称' }]}>
          <Input placeholder="例如：产品手册、运维文档..." />
        </Form.Item>
        <Form.Item name="description" label="描述">
          <Input.TextArea rows={2} placeholder="简要描述知识库内容..." />
        </Form.Item>

        <Divider orientation="left" style={{ fontSize: 13, color: '#64748b', margin: '12px 0' }}>
          语义检索配置（可选）
        </Divider>
        <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 12 }}>
          选择 Embedding 提供商后，知识库将使用语义向量检索，效果更好；留空则使用关键词匹配。
          <br />
          如需添加 Embedding 提供商，请前往「设置 → Embed 模型」。
        </Text>

        <Form.Item name="embed_provider_id" label="Embedding 提供商">
          <Select
            allowClear
            placeholder="不使用语义检索（关键词匹配）"
            options={[
              ...embedProviders
                .filter((p) => p.is_active)
                .map((p) => ({
                  value: p.id,
                  label: `${p.name} (${p.model_name})`,
                })),
            ]}
          />
        </Form.Item>

        <Divider orientation="left" style={{ fontSize: 13, color: '#64748b', margin: '12px 0' }}>
          OCR 配置（可选）
        </Divider>
        <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 12 }}>
          上传图片时使用的视觉模型；留空则使用「设置 → OCR 视觉模型」中配置的默认提供商。
          <br />
          如需添加 OCR 提供商，请前往「设置 → OCR 视觉模型」。
        </Text>

        <Form.Item name="ocr_provider_id" label="OCR 视觉提供商">
          <Select
            allowClear
            placeholder="使用默认视觉模型"
            options={ocrProviders
              .filter((p) => p.is_active)
              .map((p) => ({
                value: p.id,
                label: `${p.name} (${p.model_name})`,
              }))}
            notFoundContent={
              ocrProviders.length === 0
                ? '暂无 OCR 提供商，请在「设置 → OCR 视觉模型」中添加'
                : '无匹配'
            }
          />
        </Form.Item>

        <Divider orientation="left" style={{ fontSize: 13, color: '#64748b', margin: '12px 0' }}>
          RAG 参数配置
        </Divider>
        <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 12 }}>
          配置文档分块和检索参数。修改分块参数后需要重新上传文档才能生效。
        </Text>

        <Form.Item name="chunk_size" label="分块大小（字符）" initialValue={500}>
          <InputNumber min={100} max={4000} style={{ width: '100%' }} placeholder="默认 500" />
        </Form.Item>
        <Form.Item name="chunk_overlap" label="分块重叠（字符）" initialValue={50}>
          <InputNumber min={0} max={500} style={{ width: '100%' }} placeholder="默认 50" />
        </Form.Item>
        <Form.Item name="top_k" label="检索返回数量（Top K）" initialValue={5}>
          <InputNumber min={1} max={20} style={{ width: '100%' }} placeholder="默认 5" />
        </Form.Item>
      </Form>
    </Modal>
  )
}
