import { Modal, Form, Input, Select, Switch, Row, Col, Button, message } from 'antd'
import { SyncOutlined } from '@ant-design/icons'
import { useEffect, useState } from 'react'
import type { EmbedProvider, EmbedProviderCreate } from '../../types/embed'
import { EMBED_PROVIDER_TYPES, EMBED_BASE_URL_MAP } from '../../types/embed'
import { embedProvidersApi } from '../../api/embedProviders'

interface Props {
  open: boolean
  onClose: () => void
  onSubmit: (data: EmbedProviderCreate) => Promise<void>
  initialValues?: EmbedProvider | null
  loading?: boolean
}

export default function EmbedProviderForm({ open, onClose, onSubmit, initialValues, loading }: Props) {
  const [form] = Form.useForm()
  const isEdit = !!initialValues
  const [modelOptions, setModelOptions] = useState<{ value: string; label: string }[]>([])
  const [fetchingModels, setFetchingModels] = useState(false)

  useEffect(() => {
    if (open) {
      if (initialValues) {
        form.setFieldsValue({
          ...initialValues,
          api_key: '',
        })
        if (initialValues.model_name) {
          setModelOptions([{ value: initialValues.model_name, label: initialValues.model_name }])
        }
      } else {
        form.resetFields()
        form.setFieldsValue({ is_active: true, is_default: false })
        setModelOptions([])
      }
    }
  }, [open, initialValues])

  const handleProviderTypeChange = (value: string) => {
    const baseUrl = EMBED_BASE_URL_MAP[value]
    if (baseUrl) {
      form.setFieldValue('base_url', baseUrl)
    }
    setModelOptions([])
    form.setFieldValue('model_name', undefined)
  }

  const handleFetchModels = async () => {
    const providerType = form.getFieldValue('provider_type')
    const apiKey = form.getFieldValue('api_key')
    const baseUrl = form.getFieldValue('base_url')

    if (!providerType) {
      message.warning('请先选择提供商类型')
      return
    }
    if (!apiKey && !isEdit) {
      message.warning('请先输入 API Key')
      return
    }

    setFetchingModels(true)
    try {
      const models = await embedProvidersApi.fetchModels({
        provider_type: providerType,
        api_key: apiKey || '__use_stored__',
        base_url: baseUrl || undefined,
      })
      const options = models.map((m) => ({ value: m, label: m }))
      setModelOptions(options)
      if (options.length > 0 && !form.getFieldValue('model_name')) {
        form.setFieldValue('model_name', options[0].value)
      }
      message.success(`已获取 ${models.length} 个可用模型`)
    } catch {
      message.error('获取模型列表失败，已显示推荐模型')
    } finally {
      setFetchingModels(false)
    }
  }

  const handleOk = async () => {
    const values = await form.validateFields()
    if (isEdit && !values.api_key) {
      delete values.api_key
    }
    await onSubmit(values)
    form.resetFields()
    setModelOptions([])
  }

  return (
    <Modal
      title={isEdit ? '编辑 Embed 提供商' : '添加 Embed 提供商'}
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
              <Input placeholder="例如：OpenAI Embedding" />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item name="provider_type" label="提供商类型" rules={[{ required: true }]}>
              <Select
                options={EMBED_PROVIDER_TYPES}
                onChange={handleProviderTypeChange}
                placeholder="选择类型"
              />
            </Form.Item>
          </Col>
        </Row>

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

        <Form.Item
          name="model_name"
          label={
            <span>
              模型名称
              <Button
                type="link"
                size="small"
                icon={<SyncOutlined spin={fetchingModels} />}
                onClick={handleFetchModels}
                loading={fetchingModels}
                style={{ marginLeft: 8, padding: '0 4px', height: 'auto', fontSize: 12 }}
              >
                获取可用模型
              </Button>
            </span>
          }
          rules={[{ required: true, message: '请选择或输入模型名称' }]}
        >
          <Select
            showSearch
            allowClear
            placeholder="选择或输入，如 text-embedding-3-small"
            options={modelOptions}
            filterOption={(input, option) =>
              (option?.value as string)?.toLowerCase().includes(input.toLowerCase())
            }
            notFoundContent={modelOptions.length === 0 ? '点击"获取可用模型"或直接输入' : '无匹配'}
            onSearch={(val) => {
              const exists = modelOptions.some((o) => o.value === val)
              if (val && !exists) {
                form.setFieldValue('model_name', val)
              }
            }}
          />
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
