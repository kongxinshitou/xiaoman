import { useEffect, useState } from 'react'
import { message, Typography, Spin } from 'antd'
import { BookOutlined } from '@ant-design/icons'
import type { KnowledgeBase, Document, KnowledgeBaseCreate } from '../types/knowledge'
import { knowledgeApi } from '../api/knowledge'
import KnowledgeBaseList from '../components/knowledge/KnowledgeBaseList'
import KnowledgeBaseForm from '../components/knowledge/KnowledgeBaseForm'
import DocumentUploader from '../components/knowledge/DocumentUploader'
import DocumentTable from '../components/knowledge/DocumentTable'

const { Title, Text } = Typography

export default function KnowledgePage() {
  const [kbs, setKbs] = useState<KnowledgeBase[]>([])
  const [selectedKb, setSelectedKb] = useState<KnowledgeBase | null>(null)
  const [documents, setDocuments] = useState<Document[]>([])
  const [loadingKbs, setLoadingKbs] = useState(true)
  const [loadingDocs, setLoadingDocs] = useState(false)
  const [formOpen, setFormOpen] = useState(false)
  const [editingKb, setEditingKb] = useState<KnowledgeBase | null>(null)
  const [formLoading, setFormLoading] = useState(false)

  useEffect(() => {
    loadKbs()
  }, [])

  useEffect(() => {
    if (selectedKb) {
      loadDocuments(selectedKb.id)
    }
  }, [selectedKb?.id])

  const loadKbs = async () => {
    try {
      setLoadingKbs(true)
      const list = await knowledgeApi.listKBs()
      setKbs(list)
      if (list.length > 0 && !selectedKb) {
        setSelectedKb(list[0])
      }
    } finally {
      setLoadingKbs(false)
    }
  }

  const loadDocuments = async (kbId: string) => {
    try {
      setLoadingDocs(true)
      const docs = await knowledgeApi.listDocuments(kbId)
      setDocuments(docs)
    } finally {
      setLoadingDocs(false)
    }
  }

  const handleCreate = async (data: KnowledgeBaseCreate) => {
    try {
      setFormLoading(true)
      const kb = await knowledgeApi.createKB(data)
      setKbs((prev) => [kb, ...prev])
      setSelectedKb(kb)
      setFormOpen(false)
      setEditingKb(null)
      message.success('知识库创建成功')
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } }
      message.error(e?.response?.data?.detail || '创建失败')
    } finally {
      setFormLoading(false)
    }
  }

  const handleUpdate = async (data: KnowledgeBaseCreate) => {
    if (!editingKb) return
    try {
      setFormLoading(true)
      const updated = await knowledgeApi.updateKB(editingKb.id, data)
      setKbs((prev) => prev.map((kb) => (kb.id === updated.id ? updated : kb)))
      if (selectedKb?.id === updated.id) setSelectedKb(updated)
      setFormOpen(false)
      setEditingKb(null)
      message.success('知识库已更新')
    } catch {
      message.error('更新失败')
    } finally {
      setFormLoading(false)
    }
  }

  const handleDelete = async (kb: KnowledgeBase) => {
    try {
      await knowledgeApi.deleteKB(kb.id)
      setKbs((prev) => prev.filter((k) => k.id !== kb.id))
      if (selectedKb?.id === kb.id) {
        const remaining = kbs.filter((k) => k.id !== kb.id)
        setSelectedKb(remaining.length > 0 ? remaining[0] : null)
        setDocuments([])
      }
      message.success('知识库已删除')
    } catch {
      message.error('删除失败')
    }
  }

  const handleDeleteDoc = async (doc: Document) => {
    if (!selectedKb) return
    try {
      await knowledgeApi.deleteDocument(selectedKb.id, doc.id)
      setDocuments((prev) => prev.filter((d) => d.id !== doc.id))
      message.success('文档已删除')
    } catch {
      message.error('删除失败')
    }
  }

  return (
    <div style={{ display: 'flex', height: 'calc(100vh - 56px)', overflow: 'hidden' }}>
      {/* KB List panel */}
      <div
        style={{
          width: 280,
          background: 'white',
          borderRight: '1px solid #f0f0f0',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        {loadingKbs ? (
          <div style={{ padding: 24, textAlign: 'center' }}>
            <Spin />
          </div>
        ) : (
          <KnowledgeBaseList
            kbs={kbs}
            selectedId={selectedKb?.id || null}
            onSelect={setSelectedKb}
            onCreate={() => {
              setEditingKb(null)
              setFormOpen(true)
            }}
            onEdit={(kb) => {
              setEditingKb(kb)
              setFormOpen(true)
            }}
            onDelete={handleDelete}
          />
        )}
      </div>

      {/* Document panel */}
      <div style={{ flex: 1, overflow: 'auto', padding: 24 }}>
        {!selectedKb ? (
          <div
            style={{
              height: '100%',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <div
              style={{
                width: 72,
                height: 72,
                background: '#e0e7ff',
                borderRadius: 20,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                marginBottom: 16,
              }}
            >
              <BookOutlined style={{ fontSize: 32, color: '#4f46e5' }} />
            </div>
            <Title level={4} style={{ color: '#64748b', margin: 0 }}>
              请选择或创建知识库
            </Title>
            <Text type="secondary">从左侧选择知识库以管理文档</Text>
          </div>
        ) : (
          <>
            <div style={{ marginBottom: 20 }}>
              <Title level={4} style={{ margin: 0 }}>
                {selectedKb.name}
              </Title>
              {selectedKb.description && (
                <Text type="secondary" style={{ fontSize: 13 }}>
                  {selectedKb.description}
                </Text>
              )}
            </div>

            <DocumentUploader
              kbId={selectedKb.id}
              onUploadComplete={() => loadDocuments(selectedKb.id)}
            />

            <DocumentTable
              documents={documents}
              loading={loadingDocs}
              onDelete={handleDeleteDoc}
              onRefresh={() => loadDocuments(selectedKb.id)}
            />
          </>
        )}
      </div>

      {/* KB Form Modal */}
      <KnowledgeBaseForm
        open={formOpen}
        onClose={() => {
          setFormOpen(false)
          setEditingKb(null)
        }}
        onSubmit={editingKb ? handleUpdate : handleCreate}
        initialValues={editingKb}
        loading={formLoading}
      />
    </div>
  )
}
