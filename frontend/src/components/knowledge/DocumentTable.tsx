import { Table, Tag, Button, Popconfirm, Tooltip, Typography } from 'antd'
import { DeleteOutlined, ReloadOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import type { Document } from '../../types/knowledge'
import dayjs from 'dayjs'

const { Text } = Typography

interface Props {
  documents: Document[]
  loading?: boolean
  onDelete: (doc: Document) => void
  onRefresh: () => void
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

const STATUS_MAP = {
  pending: { color: 'default', text: '待处理' },
  processing: { color: 'processing', text: '处理中' },
  ready: { color: 'success', text: '就绪' },
  error: { color: 'error', text: '错误' },
} as const

export default function DocumentTable({ documents, loading, onDelete, onRefresh }: Props) {
  const columns: ColumnsType<Document> = [
    {
      title: '文件名',
      dataIndex: 'filename',
      key: 'filename',
      ellipsis: true,
      render: (text) => <Text ellipsis style={{ maxWidth: 240 }}>{text}</Text>,
    },
    {
      title: '类型',
      dataIndex: 'file_type',
      key: 'file_type',
      width: 70,
      render: (type) => <Tag>{type.toUpperCase()}</Tag>,
    },
    {
      title: '大小',
      dataIndex: 'file_size',
      key: 'file_size',
      width: 90,
      render: (size) => formatFileSize(size),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 90,
      render: (status: keyof typeof STATUS_MAP) => {
        const s = STATUS_MAP[status] || { color: 'default', text: status }
        return <Tag color={s.color}>{s.text}</Tag>
      },
    },
    {
      title: '分片数',
      dataIndex: 'chunk_count',
      key: 'chunk_count',
      width: 80,
      render: (count) => <Text type="secondary">{count}</Text>,
    },
    {
      title: '上传时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 130,
      render: (t) => dayjs(t).format('MM-DD HH:mm'),
    },
    {
      title: '操作',
      key: 'action',
      width: 70,
      render: (_, doc) => (
        <Popconfirm
          title="确认删除此文档？"
          description="相关分片数据将被清除"
          onConfirm={() => onDelete(doc)}
          okText="删除"
          cancelText="取消"
          okButtonProps={{ danger: true }}
        >
          <Button type="text" size="small" danger icon={<DeleteOutlined />} />
        </Popconfirm>
      ),
    },
  ]

  return (
    <Table
      columns={columns}
      dataSource={documents}
      rowKey="id"
      loading={loading}
      size="small"
      pagination={{ pageSize: 10, showTotal: (total) => `共 ${total} 个文档` }}
      title={() => (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Text strong>文档列表</Text>
          <Button size="small" icon={<ReloadOutlined />} onClick={onRefresh}>
            刷新
          </Button>
        </div>
      )}
    />
  )
}
