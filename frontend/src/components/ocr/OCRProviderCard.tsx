import { Card, Tag, Button, Popconfirm, Typography, Space, Tooltip } from 'antd'
import {
  DeleteOutlined,
  EditOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ExperimentOutlined,
  StarFilled,
  StarOutlined,
} from '@ant-design/icons'
import type { OCRProvider } from '../../types/ocr'
import { OCR_PROVIDER_TYPES } from '../../types/ocr'
import dayjs from 'dayjs'

const { Text } = Typography

interface Props {
  provider: OCRProvider
  onEdit: (p: OCRProvider) => void
  onDelete: (p: OCRProvider) => void
  onTest: (p: OCRProvider) => void
  onSetDefault: (p: OCRProvider) => void
  testing?: boolean
}

export default function OCRProviderCard({ provider, onEdit, onDelete, onTest, onSetDefault, testing }: Props) {
  const typeLabel = OCR_PROVIDER_TYPES.find((t) => t.value === provider.provider_type)?.label || provider.provider_type

  const statusIcon = {
    untested: <Tag color="default">未测试</Tag>,
    ok: <Tag color="success" icon={<CheckCircleOutlined />}>连接正常</Tag>,
    failed: <Tag color="error" icon={<CloseCircleOutlined />}>连接失败</Tag>,
  }[provider.last_test_status]

  return (
    <Card
      size="small"
      style={{
        marginBottom: 12,
        borderRadius: 10,
        border: provider.is_default ? '2px solid #d97706' : '1px solid #e2e8f0',
        boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
      }}
      styles={{ body: { padding: '14px 16px' } }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            <Text strong style={{ fontSize: 14 }}>{provider.name}</Text>
            {provider.is_default && (
              <Tag color="orange" style={{ fontSize: 11 }}>默认</Tag>
            )}
            {!provider.is_active && (
              <Tag color="default" style={{ fontSize: 11 }}>已禁用</Tag>
            )}
          </div>
          <Space size={8} wrap>
            <Tag color="blue">{typeLabel}</Tag>
            <Text type="secondary" style={{ fontSize: 12 }}>{provider.model_name}</Text>
          </Space>
          {provider.base_url && (
            <div style={{ marginTop: 4 }}>
              <Text type="secondary" style={{ fontSize: 11 }}>{provider.base_url}</Text>
            </div>
          )}
          <div style={{ marginTop: 8, display: 'flex', alignItems: 'center', gap: 8 }}>
            {statusIcon}
            {provider.last_tested_at && (
              <Text type="secondary" style={{ fontSize: 11 }}>
                {dayjs(provider.last_tested_at).format('MM-DD HH:mm')}
              </Text>
            )}
          </div>
        </div>

        <Space>
          <Tooltip title={provider.is_default ? '当前默认' : '设为默认'}>
            <Button
              type="text"
              size="small"
              icon={provider.is_default ? <StarFilled style={{ color: '#d97706' }} /> : <StarOutlined />}
              onClick={() => onSetDefault(provider)}
            />
          </Tooltip>
          <Tooltip title="测试连接">
            <Button
              type="text"
              size="small"
              icon={<ExperimentOutlined />}
              loading={testing}
              onClick={() => onTest(provider)}
            />
          </Tooltip>
          <Tooltip title="编辑">
            <Button type="text" size="small" icon={<EditOutlined />} onClick={() => onEdit(provider)} />
          </Tooltip>
          <Popconfirm
            title="确认删除此 OCR 提供商？"
            onConfirm={() => onDelete(provider)}
            okText="删除"
            cancelText="取消"
            okButtonProps={{ danger: true }}
          >
            <Button type="text" size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      </div>
    </Card>
  )
}
