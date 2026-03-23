import { Modal, Form, Input, Select, Switch, Row, Col } from 'antd'
import { useEffect } from 'react'
import type { LLMProvider, LLMProviderCreate } from '../../types/llm'
import { PROVIDER_TYPES } from '../../types/llm'

interface Props {
  open: boolean
  onClose: () => void
  onSubmit: (data: LLMProviderCreate) => Promise<void>
  initialValues?: LLMProvider | null
  loading?: boolean
}

const BASE_URL_MAP: Record<string, string> = {
  qwen: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
  doubao: 'https://ark.cn-beijing.volces.com/api/v3',
  zhipu: 'https://open.bigmodel.cn/api/paas/v4/',
  moonshot: 'https://api.moonshot.cn/v1',
  deepseek: 'https://api.deepseek.com',
  minimax: 'https://api.minimax.chat/v1',
  baichuan: 'https://api.baichuan-ai.com/v1',
}

export default function ProviderForm({ open, onClose, onSubmit, initialValues, loading }: Props) {
  const [form] = Form.useForm()
  const isEdit = !!initialValues

  useEffect(() => {
    if (open) {
      if (initialValues) {
        form.setFieldsValue({
          ...initialValues,
          api_key: '',
        })
      } else {
        form.resetFields()
        form.setFieldsValue({ is_active: true, is_default: false })
      }
    }
  }, [open, initialValues])

  const handleProviderTypeChange = (value: string) => {
    const baseUrl = BASE_URL_MAP[value]
    if (baseUrl) {
      form.setFieldValue('base_url', baseUrl)
    }
  }

  const handleOk = async () => {
    const values = await form.validateFields()
    if (isEdit && !values.api_key) {
      delete values.api_key
    }
    await onSubmit(values)
    form.resetFields()
  }

  return (
    <Modal
      title={isEdit ? '编辑 LLM 提供商' : '添加 LLM 提供商'}
      open={open}
      onOk={handleOk}
      onCancel={onClose}
      confirmLoading={loading}
      okText={isEdit ? '保存' : '添加'}
      cancelText="取消"
      width={520}
    >
      <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
        <Row gutter={16}>
          <Col span={12}>
            <Form.Item name="name" label="显示名称" rules={[{ required: true }]}>
              <Input placeholder="例如：公司GPT-4" />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item name="provider_type" label="提供商类型" rules={[{ required: true }]}>
              <Select
                options={PROVIDER_TYPES}
                onChange={handleProviderTypeChange}
                placeholder="选择类型"
              />
            </Form.Item>
          </Col>
        </Row>

        <Form.Item name="model_name" label="模型名称" rules={[{ required: true }]}>
          <Input placeholder="例如：gpt-4o, claude-3-5-sonnet, qwen-max..." />
        </Form.Item>

        <Form.Item
          name="api_key"
          label={isEdit ? 'API Key (留空保持不变)' : 'API Key'}
          rules={isEdit ? [] : [{ required: true }]}
        >
          <Input.Password placeholder="sk-..." />
        </Form.Item>

        <Form.Item name="base_url" label="Base URL (可选)">
          <Input placeholder="https://..." />
        </Form.Item>

        <Row gutter={16}>
          <Col span={12}>
            <Form.Item name="is_active" label="启用" valuePropName="checked">
              <Switch />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item name="is_default" label="设为默认" valuePropName="checked">
              <Switch />
            </Form.Item>
          </Col>
        </Row>
      </Form>
    </Modal>
  )
}
