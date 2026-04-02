import { useState } from 'react'
import { Button, Typography, Popconfirm, Tooltip, Empty } from 'antd'
import {
  BookOutlined,
  DeleteOutlined,
  EditOutlined,
  PlusOutlined,
} from '@ant-design/icons'
import type { KnowledgeBase } from '../../types/knowledge'
import dayjs from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'
import 'dayjs/locale/zh-cn'

dayjs.extend(relativeTime)
dayjs.locale('zh-cn')

const { Text } = Typography

interface Props {
  kbs: KnowledgeBase[]
  selectedId: string | null
  onSelect: (kb: KnowledgeBase) => void
  onCreate: () => void
  onEdit: (kb: KnowledgeBase) => void
  onDelete: (kb: KnowledgeBase) => void
  loading?: boolean
}

export default function KnowledgeBaseList({
  kbs,
  selectedId,
  onSelect,
  onCreate,
  onEdit,
  onDelete,
  loading,
}: Props) {
  const [hoveredId, setHoveredId] = useState<string | null>(null)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div
        style={{
          padding: '16px',
          borderBottom: '1px solid #f0f0f0',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <Text strong style={{ fontSize: 15 }}>
          知识库列表
        </Text>
        <Button
          type="primary"
          size="small"
          icon={<PlusOutlined />}
          onClick={onCreate}
          style={{ background: 'linear-gradient(135deg, #4f46e5, #6366f1)', border: 'none' }}
        >
          新建
        </Button>
      </div>

      {kbs.length === 0 && !loading ? (
        <div style={{ padding: 24 }}>
          <Empty description="暂无知识库" image={Empty.PRESENTED_IMAGE_SIMPLE}>
            <Button type="primary" onClick={onCreate} icon={<PlusOutlined />}>
              创建知识库
            </Button>
          </Empty>
        </div>
      ) : (
        <div style={{ flex: 1, overflow: 'auto' }}>
          {kbs.map((kb) => {
            const isSelected = selectedId === kb.id
            const isHovered = hoveredId === kb.id
            return (
              <div
                key={kb.id}
                onClick={() => onSelect(kb)}
                onMouseEnter={() => setHoveredId(kb.id)}
                onMouseLeave={() => setHoveredId(null)}
                style={{
                  padding: '12px 14px',
                  cursor: 'pointer',
                  background: isSelected ? '#eef2ff' : isHovered ? '#f8fafc' : 'transparent',
                  borderLeft: isSelected ? '3px solid #4f46e5' : '3px solid transparent',
                  transition: 'all 0.15s',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                  <div
                    style={{
                      width: 36,
                      height: 36,
                      background: isSelected ? '#4f46e5' : '#e0e7ff',
                      borderRadius: 8,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0,
                    }}
                  >
                    <BookOutlined
                      style={{ color: isSelected ? 'white' : '#4f46e5', fontSize: 16 }}
                    />
                  </div>
                  <div style={{ flex: 1, overflow: 'hidden' }}>
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                      }}
                    >
                      <Text
                        strong
                        ellipsis
                        style={{ fontSize: 13, color: isSelected ? '#4f46e5' : '#1e293b' }}
                      >
                        {kb.name}
                      </Text>
                      <div style={{ display: 'flex', gap: 2, flexShrink: 0, marginLeft: 6 }}>
                        <Tooltip title="编辑">
                          <Button
                            type="text"
                            size="small"
                            icon={<EditOutlined />}
                            onClick={(e) => {
                              e.stopPropagation()
                              onEdit(kb)
                            }}
                            style={{
                              padding: 0,
                              height: 28,
                              width: 28,
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                            }}
                          />
                        </Tooltip>
                        <Popconfirm
                          title="确认删除此知识库？"
                          description="所有相关文档将被永久删除"
                          onConfirm={(e) => {
                            e?.stopPropagation()
                            onDelete(kb)
                          }}
                          onCancel={(e) => e?.stopPropagation()}
                          okText="删除"
                          cancelText="取消"
                          okButtonProps={{ danger: true }}
                        >
                          <Button
                            type="text"
                            size="small"
                            danger
                            icon={<DeleteOutlined />}
                            onClick={(e) => e.stopPropagation()}
                            style={{
                              padding: 0,
                              height: 28,
                              width: 28,
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                            }}
                          />
                        </Popconfirm>
                      </div>
                    </div>
                    {kb.description && (
                      <Text
                        type="secondary"
                        ellipsis
                        style={{ fontSize: 12, display: 'block', marginTop: 2 }}
                      >
                        {kb.description}
                      </Text>
                    )}
                    <div style={{ marginTop: 4 }}>
                      <Text type="secondary" style={{ fontSize: 11 }}>
                        {dayjs(kb.updated_at || kb.created_at).fromNow()}
                      </Text>
                    </div>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
