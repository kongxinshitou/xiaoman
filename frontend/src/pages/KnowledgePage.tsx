import { useEffect, useState } from 'react'
import { message, Typography, Spin, Input, List, Tag, Divider, Empty, Tabs, Badge } from 'antd'
import { BookOutlined, SearchOutlined } from '@ant-design/icons'
import type { KnowledgeBase, Document, KnowledgeBaseCreate, SearchResult } from '../types/knowledge'
import type { EmbedProvider } from '../types/embed'
import type { OCRProvider } from '../types/ocr'
import { knowledgeApi } from '../api/knowledge'
import { embedProvidersApi } from '../api/embedProviders'
import { ocrProvidersApi } from '../api/ocrProviders'
import KnowledgeBaseList from '../components/knowledge/KnowledgeBaseList'
import KnowledgeBaseForm from '../components/knowledge/KnowledgeBaseForm'
import DocumentUploader from '../components/knowledge/DocumentUploader'
import DocumentTable from '../components/knowledge/DocumentTable'

const { Title, Text } = Typography
const { Search } = Input

export default function KnowledgePage() {
  const [kbs, setKbs] = useState<KnowledgeBase[]>([])
  const [selectedKb, setSelectedKb] = useState<KnowledgeBase | null>(null)
  const [documents, setDocuments] = useState<Document[]>([])
  const [loadingKbs, setLoadingKbs] = useState(true)
  const [loadingDocs, setLoadingDocs] = useState(false)
  const [formOpen, setFormOpen] = useState(false)
  const [editingKb, setEditingKb] = useState<KnowledgeBase | null>(null)
  const [formLoading, setFormLoading] = useState(false)
  const [searchResults, setSearchResults] = useState<SearchResult[] | null>(null)
  const [searching, setSearching] = useState(false)
  const [embedProviders, setEmbedProviders] = useState<EmbedProvider[]>([])
  const [ocrProviders, setOcrProviders] = useState<OCRProvider[]>([])
  const [activeTab, setActiveTab] = useState<'docs' | 'search'>('docs')

  useEffect(() => {
    loadKbs()
    embedProvidersApi.list().then(setEmbedProviders).catch(() => {})
    ocrProvidersApi.list().then(setOcrProviders).catch(() => {})
  }, [])

  useEffect(() => {
    if (selectedKb) {
      loadDocuments(selectedKb.id)
      setSearchResults(null)
      setActiveTab('docs')
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
        setSearchResults(null)
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

  const handleSearch = async (query: string) => {
    if (!selectedKb || !query.trim()) return
    try {
      setSearching(true)
      const results = await knowledgeApi.search(selectedKb.id, query)
      setSearchResults(results)
    } catch {
      message.error('检索失败')
    } finally {
      setSearching(false)
    }
  }

  const searchTabLabel = (
    <span>
      知识检索
      {searchResults !== null && searchResults.length > 0 && (
        <Badge
          count={searchResults.length}
          size="small"
          style={{ marginLeft: 6, backgroundColor: '#4f46e5' }}
        />
      )}
    </span>
  )

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
            {/* KB header */}
            <div style={{ marginBottom: 4 }}>
              <Title level={4} style={{ margin: 0 }}>
                {selectedKb.name}
              </Title>
              {selectedKb.description && (
                <Text type="secondary" style={{ fontSize: 13 }}>
                  {selectedKb.description}
                </Text>
              )}
              <div style={{ marginTop: 4 }}>
                {selectedKb.embed_provider_id
                  ? <Tag color="cyan" style={{ fontSize: 11 }}>Embed 提供商</Tag>
                  : <Tag color="blue" style={{ fontSize: 11 }}>{selectedKb.embed_model}</Tag>
                }
                {selectedKb.has_embed_key && (
                  <Tag color="green" style={{ fontSize: 11 }}>语义检索</Tag>
                )}
              </div>
            </div>

            {/* Tabs */}
            <Tabs
              activeKey={activeTab}
              onChange={(key) => setActiveTab(key as 'docs' | 'search')}
              items={[
                {
                  key: 'docs',
                  label: '文档管理',
                  children: (
                    <>
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
                  ),
                },
                {
                  key: 'search',
                  label: searchTabLabel,
                  children: (
                    <div>
                      <Search
                        placeholder="检索知识库内容..."
                        allowClear
                        enterButton={
                          <span>
                            <SearchOutlined /> 检索
                          </span>
                        }
                        loading={searching}
                        style={{ width: '100%', maxWidth: 560, marginBottom: 16 }}
                        onSearch={handleSearch}
                        onChange={(e) => {
                          if (!e.target.value) setSearchResults(null)
                        }}
                      />
                      {searchResults === null ? (
                        <Empty
                          description="输入关键词检索知识库内容"
                          image={Empty.PRESENTED_IMAGE_SIMPLE}
                        />
                      ) : searchResults.length === 0 ? (
                        <Empty
                          description="未找到相关内容"
                          image={Empty.PRESENTED_IMAGE_SIMPLE}
                        />
                      ) : (
                        <>
                          <Divider orientation="left" style={{ fontSize: 13 }}>
                            检索结果（{searchResults.length} 条）
                          </Divider>
                          <List
                            dataSource={searchResults}
                            renderItem={(item) => (
                              <List.Item
                                style={{ padding: '10px 0', alignItems: 'flex-start' }}
                              >
                                <div style={{ width: '100%' }}>
                                  <div style={{ display: 'flex', gap: 8, marginBottom: 6 }}>
                                    <Tag color="purple" style={{ fontSize: 11 }}>
                                      {item.document_name || item.doc_id}
                                    </Tag>
                                    <Tag color="cyan" style={{ fontSize: 11 }}>
                                      相关度 {(item.score * 100).toFixed(1)}%
                                    </Tag>
                                  </div>
                                  <div
                                    style={{
                                      background: '#f8fafc',
                                      border: '1px solid #e2e8f0',
                                      borderRadius: 8,
                                      padding: '8px 12px',
                                      fontSize: 13,
                                      color: '#374151',
                                      lineHeight: 1.6,
                                      maxHeight: 120,
                                      overflow: 'auto',
                                      whiteSpace: 'pre-wrap',
                                      wordBreak: 'break-word',
                                    }}
                                  >
                                    {item.chunk_text}
                                  </div>
                                </div>
                              </List.Item>
                            )}
                          />
                        </>
                      )}
                    </div>
                  ),
                },
              ]}
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
        embedProviders={embedProviders}
        ocrProviders={ocrProviders}
      />
    </div>
  )
}
