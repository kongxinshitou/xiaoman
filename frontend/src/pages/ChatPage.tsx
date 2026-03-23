import { useEffect, useState } from 'react'
import { Button, Input, Typography, Popconfirm, Tooltip, Spin, Empty } from 'antd'
import {
  PlusOutlined,
  MessageOutlined,
  DeleteOutlined,
  EditOutlined,
  CheckOutlined,
  CloseOutlined,
} from '@ant-design/icons'
import { useChatStore } from '../store/chatStore'
import { useSettingsStore } from '../store/settingsStore'
import { chatApi } from '../api/chat'
import { llmProvidersApi } from '../api/llmProviders'
import { knowledgeApi } from '../api/knowledge'
import ChatWindow from '../components/chat/ChatWindow'
import dayjs from 'dayjs'

const { Text } = Typography

export default function ChatPage() {
  const { sessions, activeSessionId, setSessions, addSession, removeSession, setActiveSession, updateSession } =
    useChatStore()
  const { setProviders, setKnowledgeBases } = useSettingsStore()
  const [loading, setLoading] = useState(true)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editingTitle, setEditingTitle] = useState('')

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      setLoading(true)
      const [sessionList, providers, kbs] = await Promise.all([
        chatApi.listSessions(),
        llmProvidersApi.list(),
        knowledgeApi.listKBs(),
      ])
      setSessions(sessionList)
      setProviders(providers)
      setKnowledgeBases(kbs)
      if (sessionList.length > 0 && !activeSessionId) {
        setActiveSession(sessionList[0].id)
      }
    } catch (err) {
      console.error('Failed to load data:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleNewSession = async () => {
    try {
      const session = await chatApi.createSession()
      addSession(session)
      setActiveSession(session.id)
    } catch (err) {
      console.error('Failed to create session:', err)
    }
  }

  const handleDeleteSession = async (sessionId: string) => {
    try {
      await chatApi.deleteSession(sessionId)
      removeSession(sessionId)
      if (activeSessionId === sessionId) {
        const remaining = sessions.filter((s) => s.id !== sessionId)
        setActiveSession(remaining.length > 0 ? remaining[0].id : null)
      }
    } catch (err) {
      console.error('Failed to delete session:', err)
    }
  }

  const handleStartEdit = (session: { id: string; title: string }) => {
    setEditingId(session.id)
    setEditingTitle(session.title)
  }

  const handleSaveEdit = async (sessionId: string) => {
    if (!editingTitle.trim()) return
    try {
      const updated = await chatApi.updateSession(sessionId, { title: editingTitle })
      updateSession(updated)
    } catch (err) {
      console.error(err)
    } finally {
      setEditingId(null)
    }
  }

  return (
    <div style={{ display: 'flex', height: 'calc(100vh - 56px)', overflow: 'hidden' }}>
      {/* Sessions sidebar */}
      <div
        style={{
          width: 260,
          background: 'white',
          borderRight: '1px solid #f0f0f0',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: '14px 16px',
            borderBottom: '1px solid #f0f0f0',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <Text strong style={{ fontSize: 14 }}>
            对话记录
          </Text>
          <Button
            type="primary"
            size="small"
            icon={<PlusOutlined />}
            onClick={handleNewSession}
            style={{
              background: 'linear-gradient(135deg, #4f46e5, #6366f1)',
              border: 'none',
              borderRadius: 6,
            }}
          >
            新建
          </Button>
        </div>

        {/* Sessions list */}
        <div style={{ flex: 1, overflow: 'auto' }}>
          {loading ? (
            <div style={{ padding: 24, textAlign: 'center' }}>
              <Spin size="small" />
            </div>
          ) : sessions.length === 0 ? (
            <div style={{ padding: 24, textAlign: 'center' }}>
              <Empty
                description="暂无对话"
                image={Empty.PRESENTED_IMAGE_SIMPLE}
              >
                <Button size="small" onClick={handleNewSession} icon={<PlusOutlined />}>
                  开始对话
                </Button>
              </Empty>
            </div>
          ) : (
            sessions.map((session) => (
              <div
                key={session.id}
                onClick={() => setActiveSession(session.id)}
                style={{
                  padding: '10px 12px',
                  cursor: 'pointer',
                  background: activeSessionId === session.id ? '#eef2ff' : 'transparent',
                  borderLeft:
                    activeSessionId === session.id ? '3px solid #4f46e5' : '3px solid transparent',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  transition: 'all 0.15s',
                  group: 'session',
                }}
                onMouseEnter={(e) => {
                  if (activeSessionId !== session.id) {
                    ;(e.currentTarget as HTMLDivElement).style.background = '#f8fafc'
                  }
                }}
                onMouseLeave={(e) => {
                  if (activeSessionId !== session.id) {
                    ;(e.currentTarget as HTMLDivElement).style.background = 'transparent'
                  }
                }}
              >
                <MessageOutlined
                  style={{
                    color: activeSessionId === session.id ? '#4f46e5' : '#94a3b8',
                    flexShrink: 0,
                  }}
                />
                <div style={{ flex: 1, overflow: 'hidden', minWidth: 0 }}>
                  {editingId === session.id ? (
                    <div style={{ display: 'flex', gap: 4 }} onClick={(e) => e.stopPropagation()}>
                      <Input
                        size="small"
                        value={editingTitle}
                        onChange={(e) => setEditingTitle(e.target.value)}
                        onPressEnter={() => handleSaveEdit(session.id)}
                        autoFocus
                        style={{ fontSize: 12 }}
                      />
                      <Button
                        type="text"
                        size="small"
                        icon={<CheckOutlined />}
                        onClick={() => handleSaveEdit(session.id)}
                      />
                      <Button
                        type="text"
                        size="small"
                        icon={<CloseOutlined />}
                        onClick={() => setEditingId(null)}
                      />
                    </div>
                  ) : (
                    <>
                      <Text
                        ellipsis
                        style={{
                          fontSize: 13,
                          display: 'block',
                          color: activeSessionId === session.id ? '#4f46e5' : '#1e293b',
                        }}
                      >
                        {session.title}
                      </Text>
                      <Text type="secondary" style={{ fontSize: 11 }}>
                        {dayjs(session.updated_at).format('MM-DD HH:mm')}
                      </Text>
                    </>
                  )}
                </div>

                {editingId !== session.id && (
                  <div
                    style={{ display: 'flex', gap: 2, flexShrink: 0 }}
                    onClick={(e) => e.stopPropagation()}
                  >
                    <Tooltip title="重命名">
                      <Button
                        type="text"
                        size="small"
                        icon={<EditOutlined />}
                        onClick={() => handleStartEdit(session)}
                        style={{ padding: '0 4px', height: 20, width: 20, opacity: 0.6 }}
                      />
                    </Tooltip>
                    <Popconfirm
                      title="删除此对话？"
                      onConfirm={() => handleDeleteSession(session.id)}
                      okText="删除"
                      cancelText="取消"
                      okButtonProps={{ danger: true }}
                    >
                      <Button
                        type="text"
                        size="small"
                        danger
                        icon={<DeleteOutlined />}
                        style={{ padding: '0 4px', height: 20, width: 20 }}
                      />
                    </Popconfirm>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </div>

      {/* Chat area */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        {activeSessionId ? (
          <ChatWindow key={activeSessionId} sessionId={activeSessionId} />
        ) : (
          <div
            style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              background: '#f8fafc',
            }}
          >
            <div
              style={{
                width: 80,
                height: 80,
                background: 'linear-gradient(135deg, #4f46e5, #7c3aed)',
                borderRadius: 20,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                marginBottom: 20,
              }}
            >
              <MessageOutlined style={{ fontSize: 40, color: 'white' }} />
            </div>
            <Text style={{ fontSize: 16, color: '#64748b', marginBottom: 16 }}>
              选择或创建一个对话开始
            </Text>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={handleNewSession}
              style={{
                background: 'linear-gradient(135deg, #4f46e5, #6366f1)',
                border: 'none',
              }}
            >
              新建对话
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}
