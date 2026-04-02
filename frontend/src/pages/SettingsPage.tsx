import { useEffect, useState } from 'react'
import {
  Tabs,
  Button,
  message,
  Typography,
  Card,
  Table,
  Tag,
  Switch,
  Popconfirm,
  Space,
  Form,
  Input,
  InputNumber,
  Select,
  Modal,
  Row,
  Col,
  Statistic,
  Alert,
  Divider,
  Badge,
} from 'antd'
import {
  PlusOutlined,
  RobotOutlined,
  ThunderboltOutlined,
  AppstoreOutlined,
  BarChartOutlined,
  DatabaseOutlined,
  DeleteOutlined,
  EditOutlined,
  PlayCircleOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  CopyOutlined,
  SearchOutlined,
} from '@ant-design/icons'
import type { LLMProvider, LLMProviderCreate } from '../types/llm'
import type { EmbedProvider, EmbedProviderCreate } from '../types/embed'
import type { OCRProvider, OCRProviderCreate } from '../types/ocr'
import type { MCPTool, MCPToolCreate } from '../types/mcp'
import type { FeishuConfig } from '../types/feishu'
import { llmProvidersApi } from '../api/llmProviders'
import { embedProvidersApi } from '../api/embedProviders'
import { ocrProvidersApi } from '../api/ocrProviders'
import { mcpToolsApi } from '../api/mcpTools'
import { feishuApi } from '../api/feishu'
import ProviderCard from '../components/llm/ProviderCard'
import ProviderForm from '../components/llm/ProviderForm'
import EmbedProviderCard from '../components/embed/EmbedProviderCard'
import EmbedProviderForm from '../components/embed/EmbedProviderForm'
import OCRProviderCard from '../components/ocr/OCRProviderCard'
import OCRProviderForm from '../components/ocr/OCRProviderForm'
import client from '../api/client'

const { Title, Text } = Typography

interface SystemStats {
  knowledge_bases: number
  documents: number
  llm_providers: number
  chat_sessions: number
  chat_messages: number
  mcp_tools: number
}

export default function SettingsPage() {
  const [providers, setProviders] = useState<LLMProvider[]>([])
  const [embedProviders, setEmbedProviders] = useState<EmbedProvider[]>([])
  const [ocrProviders, setOcrProviders] = useState<OCRProvider[]>([])
  const [mcpTools, setMcpTools] = useState<MCPTool[]>([])
  const [stats, setStats] = useState<SystemStats | null>(null)
  const [testingId, setTestingId] = useState<string | null>(null)
  const [embedTestingId, setEmbedTestingId] = useState<string | null>(null)
  const [ocrTestingId, setOcrTestingId] = useState<string | null>(null)
  // Embed provider form
  const [embedFormOpen, setEmbedFormOpen] = useState(false)
  const [editingEmbedProvider, setEditingEmbedProvider] = useState<EmbedProvider | null>(null)
  const [embedFormLoading, setEmbedFormLoading] = useState(false)
  // OCR provider form
  const [ocrFormOpen, setOcrFormOpen] = useState(false)
  const [editingOcrProvider, setEditingOcrProvider] = useState<OCRProvider | null>(null)
  const [ocrFormLoading, setOcrFormLoading] = useState(false)
  // Search config
  const [searchProvider, setSearchProvider] = useState<string>('duckduckgo')
  const [searchApiKey, setSearchApiKey] = useState<string>('')
  const [hasSearchApiKey, setHasSearchApiKey] = useState(false)
  const [searchConfigLoading, setSearchConfigLoading] = useState(false)
  // MCP execute test state
  const [execToolId, setExecToolId] = useState<string | null>(null)
  const [execParams, setExecParams] = useState('{}')
  const [execParamsError, setExecParamsError] = useState('')
  const [execOutput, setExecOutput] = useState('')
  const [execRunning, setExecRunning] = useState(false)

  // Provider form
  const [providerFormOpen, setProviderFormOpen] = useState(false)
  const [editingProvider, setEditingProvider] = useState<LLMProvider | null>(null)
  const [providerFormLoading, setProviderFormLoading] = useState(false)

  // Feishu integration
  const [feishuConfig, setFeishuConfig] = useState<FeishuConfig | null>(null)
  const [feishuForm] = Form.useForm()
  const [feishuSaving, setFeishuSaving] = useState(false)
  const [feishuTesting, setFeishuTesting] = useState(false)

  // MCP form
  const [mcpFormOpen, setMcpFormOpen] = useState(false)
  const [editingMcp, setEditingMcp] = useState<MCPTool | null>(null)
  const [mcpForm] = Form.useForm()
  const [mcpFormLoading, setMcpFormLoading] = useState(false)
  // MCP discover
  const [discoverOpen, setDiscoverOpen] = useState(false)
  const [discoverForm] = Form.useForm()
  const [discoverLoading, setDiscoverLoading] = useState(false)

  useEffect(() => {
    loadAll()
  }, [])

  const loadAll = async () => {
    try {
      const [pList, epList, ocrList, mList, statsData, sysConfig, fCfg] = await Promise.all([
        llmProvidersApi.list(),
        embedProvidersApi.list(),
        ocrProvidersApi.list(),
        mcpToolsApi.list(),
        client.get('/system/stats').then((r) => r.data),
        client.get('/system/config').then((r) => r.data).catch(() => ({ search_provider: 'duckduckgo', has_search_api_key: false })),
        feishuApi.getConfig().catch(() => null),
      ])
      setProviders(pList)
      setEmbedProviders(epList)
      setOcrProviders(ocrList)
      setMcpTools(mList)
      setStats(statsData)
      setSearchProvider(sysConfig.search_provider || 'duckduckgo')
      setHasSearchApiKey(sysConfig.has_search_api_key || false)
      if (fCfg) {
        setFeishuConfig(fCfg)
        feishuForm.setFieldsValue({
          app_id: fCfg.app_id || '',
          bot_open_id: fCfg.bot_open_id || '',
          default_push_chat_id: fCfg.default_push_chat_id || '',
          enabled: fCfg.enabled,
        })
      }
    } catch (err) {
      console.error(err)
    }
  }

  // ── MCP Execute Test ──
  const handleMcpExecute = async (tool: MCPTool) => {
    setExecParamsError('')
    let parsedParams: Record<string, unknown> = {}
    try {
      parsedParams = JSON.parse(execParams || '{}')
    } catch {
      setExecParamsError('参数格式错误，请输入合法的 JSON')
      return
    }
    setExecOutput('')
    setExecRunning(true)
    const token = localStorage.getItem('xiaoman_token')
    try {
      const response = await fetch(`/api/v1/mcp-tools/${tool.id}/execute`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({ params: parsedParams }),
      })
      const reader = response.body!.getReader()
      const decoder = new TextDecoder()
      let buf = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const lines = buf.split('\n')
        buf = lines.pop() || ''
        for (const line of lines) {
          if (line.startsWith('data:')) {
            try {
              const data = JSON.parse(line.slice(5).trim())
              if (data.output) setExecOutput((prev) => prev + data.output + '\n')
            } catch {}
          }
        }
      }
    } catch (e) {
      setExecOutput(`执行失败: ${e}`)
    } finally {
      setExecRunning(false)
    }
  }

  // ── MCP Discover ──
  const handleMcpDiscover = async () => {
    try {
      const values = await discoverForm.validateFields()
      setDiscoverLoading(true)
      const result = await mcpToolsApi.discover(values.server_url, values.transport || 'sse')
      message.success(`发现 ${result.discovered} 个工具，已保存 ${result.saved} 个`)
      setDiscoverOpen(false)
      discoverForm.resetFields()
      // Refresh tools list
      const mList = await mcpToolsApi.list()
      setMcpTools(mList)
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } }
      message.error(e?.response?.data?.detail || '发现工具失败')
    } finally {
      setDiscoverLoading(false)
    }
  }

  // ── Feishu handlers ──
  const handleFeishuSave = async () => {
    const values = feishuForm.getFieldsValue()
    setFeishuSaving(true)
    try {
      await feishuApi.updateConfig(values)
      message.success('飞书配置已保存')
      const updated = await feishuApi.getConfig()
      setFeishuConfig(updated)
    } catch {
      message.error('保存失败')
    } finally {
      setFeishuSaving(false)
    }
  }

  const handleFeishuTest = async () => {
    setFeishuTesting(true)
    try {
      const res = await feishuApi.testConnection()
      message.success(res.message)
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } }
      message.error(e?.response?.data?.detail || '连接测试失败')
    } finally {
      setFeishuTesting(false)
    }
  }

  // Provider actions
  const handleProviderSubmit = async (data: LLMProviderCreate) => {
    try {
      setProviderFormLoading(true)
      if (editingProvider) {
        const updated = await llmProvidersApi.update(editingProvider.id, data)
        setProviders((prev) => prev.map((p) => (p.id === updated.id ? updated : p)))
        message.success('提供商已更新')
      } else {
        const created = await llmProvidersApi.create(data)
        setProviders((prev) => [created, ...prev])
        message.success('提供商已添加')
      }
      setProviderFormOpen(false)
      setEditingProvider(null)
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } }
      message.error(e?.response?.data?.detail || '操作失败')
    } finally {
      setProviderFormLoading(false)
    }
  }

  const handleProviderDelete = async (p: LLMProvider) => {
    try {
      await llmProvidersApi.delete(p.id)
      setProviders((prev) => prev.filter((x) => x.id !== p.id))
      message.success('已删除')
    } catch {
      message.error('删除失败')
    }
  }

  const handleProviderTest = async (p: LLMProvider) => {
    setTestingId(p.id)
    try {
      const result = await llmProvidersApi.test(p.id)
      if (result.status === 'ok') {
        message.success(`${p.name} 连接成功!`)
      } else {
        message.error(`${p.name} 连接失败`)
      }
      const updated = await llmProvidersApi.get(p.id)
      setProviders((prev) => prev.map((x) => (x.id === updated.id ? updated : x)))
    } catch {
      message.error('测试失败')
    } finally {
      setTestingId(null)
    }
  }

  const handleSetDefault = async (p: LLMProvider) => {
    try {
      await llmProvidersApi.update(p.id, { is_default: true })
      const list = await llmProvidersApi.list()
      setProviders(list)
      message.success(`${p.name} 已设为默认`)
    } catch {
      message.error('操作失败')
    }
  }

  // Embed provider actions
  const handleEmbedProviderSubmit = async (data: EmbedProviderCreate) => {
    try {
      setEmbedFormLoading(true)
      if (editingEmbedProvider) {
        const updated = await embedProvidersApi.update(editingEmbedProvider.id, data)
        setEmbedProviders((prev) => prev.map((p) => (p.id === updated.id ? updated : p)))
        message.success('Embed 提供商已更新')
      } else {
        const created = await embedProvidersApi.create(data)
        setEmbedProviders((prev) => [created, ...prev])
        message.success('Embed 提供商已添加')
      }
      setEmbedFormOpen(false)
      setEditingEmbedProvider(null)
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } }
      message.error(e?.response?.data?.detail || '操作失败')
    } finally {
      setEmbedFormLoading(false)
    }
  }

  const handleEmbedProviderDelete = async (p: EmbedProvider) => {
    try {
      await embedProvidersApi.delete(p.id)
      setEmbedProviders((prev) => prev.filter((x) => x.id !== p.id))
      message.success('已删除')
    } catch {
      message.error('删除失败')
    }
  }

  const handleEmbedProviderTest = async (p: EmbedProvider) => {
    setEmbedTestingId(p.id)
    try {
      const result = await embedProvidersApi.test(p.id)
      if (result.status === 'ok') {
        message.success(`${p.name} 连接成功!`)
      } else {
        message.error(`${p.name} 连接失败`)
      }
      const updated = await embedProvidersApi.get(p.id)
      setEmbedProviders((prev) => prev.map((x) => (x.id === updated.id ? updated : x)))
    } catch {
      message.error('测试失败')
    } finally {
      setEmbedTestingId(null)
    }
  }

  const handleEmbedSetDefault = async (p: EmbedProvider) => {
    try {
      await embedProvidersApi.update(p.id, { is_default: true })
      const list = await embedProvidersApi.list()
      setEmbedProviders(list)
      message.success(`${p.name} 已设为默认`)
    } catch {
      message.error('操作失败')
    }
  }

  // OCR provider actions
  const handleOcrProviderSubmit = async (data: OCRProviderCreate) => {
    try {
      setOcrFormLoading(true)
      if (editingOcrProvider) {
        const updated = await ocrProvidersApi.update(editingOcrProvider.id, data)
        setOcrProviders((prev) => prev.map((p) => (p.id === updated.id ? updated : p)))
        message.success('OCR 提供商已更新')
      } else {
        const created = await ocrProvidersApi.create(data)
        setOcrProviders((prev) => [created, ...prev])
        message.success('OCR 提供商已添加')
      }
      setOcrFormOpen(false)
      setEditingOcrProvider(null)
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } }
      message.error(e?.response?.data?.detail || '操作失败')
    } finally {
      setOcrFormLoading(false)
    }
  }

  const handleOcrProviderDelete = async (p: OCRProvider) => {
    try {
      await ocrProvidersApi.delete(p.id)
      setOcrProviders((prev) => prev.filter((x) => x.id !== p.id))
      message.success('已删除')
    } catch {
      message.error('删除失败')
    }
  }

  const handleOcrProviderTest = async (p: OCRProvider) => {
    setOcrTestingId(p.id)
    try {
      const result = await ocrProvidersApi.test(p.id)
      if (result.status === 'ok') {
        message.success(`${p.name} 连接成功!`)
      } else {
        message.error(`${p.name} 连接失败: ${result.message || '未知错误'}`)
      }
      const updated = await ocrProvidersApi.get(p.id)
      setOcrProviders((prev) => prev.map((x) => (x.id === updated.id ? updated : x)))
    } catch {
      message.error('测试失败')
    } finally {
      setOcrTestingId(null)
    }
  }

  const handleOcrSetDefault = async (p: OCRProvider) => {
    try {
      await ocrProvidersApi.update(p.id, { is_default: true })
      const list = await ocrProvidersApi.list()
      setOcrProviders(list)
      message.success(`${p.name} 已设为默认`)
    } catch {
      message.error('操作失败')
    }
  }

  // Search config
  const handleSearchConfigSave = async () => {
    try {
      setSearchConfigLoading(true)
      const payload: Record<string, string> = { search_provider: searchProvider }
      if (searchApiKey) payload.search_api_key = searchApiKey
      await client.put('/system/config', payload)
      message.success('搜索配置已保存')
      setSearchApiKey('')
      const cfg = await client.get('/system/config').then((r) => r.data)
      setHasSearchApiKey(cfg.has_search_api_key)
    } catch {
      message.error('保存失败')
    } finally {
      setSearchConfigLoading(false)
    }
  }

  // MCP actions
  const handleMcpSubmit = async () => {
    const values = await mcpForm.validateFields()
    try {
      setMcpFormLoading(true)
      if (editingMcp) {
        const updated = await mcpToolsApi.update(editingMcp.id, values)
        setMcpTools((prev) => prev.map((t) => (t.id === updated.id ? updated : t)))
        message.success('工具已更新')
      } else {
        const created = await mcpToolsApi.create(values)
        setMcpTools((prev) => [created, ...prev])
        message.success('工具已添加')
      }
      setMcpFormOpen(false)
      setEditingMcp(null)
      mcpForm.resetFields()
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } }
      message.error(e?.response?.data?.detail || '操作失败')
    } finally {
      setMcpFormLoading(false)
    }
  }

  const handleMcpDelete = async (id: string) => {
    try {
      await mcpToolsApi.delete(id)
      setMcpTools((prev) => prev.filter((t) => t.id !== id))
      message.success('已删除')
    } catch {
      message.error('删除失败')
    }
  }

  const handleMcpPing = async (id: string, name: string) => {
    try {
      const result = await mcpToolsApi.ping(id)
      if (result.status === 'online') {
        message.success(`${name} 在线`)
      } else {
        message.warning(`${name} 离线`)
      }
    } catch {
      message.error('Ping 失败')
    }
  }

  const mcpColumns = [
    {
      title: '工具名称',
      dataIndex: 'name',
      key: 'name',
      render: (_: string, t: MCPTool) => (
        <div>
          <div style={{ fontWeight: 500 }}>{t.name}</div>
          {t.description && <div style={{ fontSize: 12, color: '#64748b', marginTop: 2 }}>{t.description}</div>}
        </div>
      ),
    },
    { title: '服务地址', dataIndex: 'server_url', key: 'server_url', ellipsis: true },
    { title: '协议', dataIndex: 'transport', key: 'transport', width: 70, render: (v: string) => <Tag>{v.toUpperCase()}</Tag> },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      width: 70,
      render: (v: boolean) => <Tag color={v ? 'success' : 'default'}>{v ? '启用' : '禁用'}</Tag>,
    },
    {
      title: '操作',
      key: 'action',
      render: (_: unknown, t: MCPTool) => (
        <Space>
          <Button size="small" onClick={() => handleMcpPing(t.id, t.display_name || t.name)}>Ping</Button>
          <Button size="small" icon={<PlayCircleOutlined />} type="primary" ghost
            onClick={() => {
              setExecToolId(t.id)
              setExecOutput('')
              setExecParamsError('')
              // Pre-populate with example params based on schema
              try {
                const schema = JSON.parse(t.tool_schema || '{}')
                const props = schema.properties || {}
                const example: Record<string, unknown> = {}
                for (const [k, v] of Object.entries(props as Record<string, Record<string, unknown>>)) {
                  if (v.type === 'integer' || v.type === 'number') example[k] = 0
                  else if (v.type === 'boolean') example[k] = false
                  else if (v.type === 'array') example[k] = []
                  else example[k] = ''
                }
                setExecParams(JSON.stringify(example, null, 2))
              } catch {
                setExecParams('{}')
              }
            }}>
            执行
          </Button>
          <Button size="small" icon={<EditOutlined />} onClick={() => {
            setEditingMcp(t)
            mcpForm.setFieldsValue(t)
            setMcpFormOpen(true)
          }} />
          <Popconfirm title="确认删除？" onConfirm={() => handleMcpDelete(t.id)} okText="删除" cancelText="取消" okButtonProps={{ danger: true }}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ]

  /** 解析 tool_schema 展示 parameters */
  const renderMcpParams = (tool: MCPTool) => {
    let schema: Record<string, unknown> = {}
    try { schema = JSON.parse(tool.tool_schema) } catch { /* ignore */ }
    const props = schema.properties as Record<string, { type?: string; description?: string }> | undefined
    const required = (schema.required as string[]) || []
    if (!props || Object.keys(props).length === 0) {
      return <Text type="secondary" style={{ fontSize: 12 }}>（无参数）</Text>
    }
    return (
      <table style={{ fontSize: 12, borderCollapse: 'collapse', width: '100%' }}>
        <thead>
          <tr style={{ background: '#f1f5f9' }}>
            <th style={{ padding: '4px 8px', textAlign: 'left', fontWeight: 600, width: 160 }}>参数名</th>
            <th style={{ padding: '4px 8px', textAlign: 'left', fontWeight: 600, width: 80 }}>类型</th>
            <th style={{ padding: '4px 8px', textAlign: 'left', fontWeight: 600 }}>描述</th>
            <th style={{ padding: '4px 8px', textAlign: 'left', fontWeight: 600, width: 60 }}>必填</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(props).map(([name, info]) => (
            <tr key={name} style={{ borderTop: '1px solid #e2e8f0' }}>
              <td style={{ padding: '4px 8px', fontFamily: 'monospace', color: '#4f46e5' }}>{name}</td>
              <td style={{ padding: '4px 8px', color: '#64748b' }}>{info.type || '—'}</td>
              <td style={{ padding: '4px 8px' }}>{info.description || '—'}</td>
              <td style={{ padding: '4px 8px' }}>
                {required.includes(name)
                  ? <Tag color="red" style={{ fontSize: 10 }}>必填</Tag>
                  : <Tag style={{ fontSize: 10 }}>可选</Tag>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    )
  }

  const tabItems = [
    {
      key: 'overview',
      label: (
        <span><BarChartOutlined /> 概览</span>
      ),
      children: (
        <div>
          <Row gutter={16} style={{ marginBottom: 24 }}>
            {stats && [
              { title: '知识库', value: stats.knowledge_bases, color: '#4f46e5' },
              { title: '文档', value: stats.documents, color: '#0891b2' },
              { title: 'LLM 提供商', value: stats.llm_providers, color: '#059669' },
              { title: '对话会话', value: stats.chat_sessions, color: '#d97706' },
              { title: '消息总数', value: stats.chat_messages, color: '#dc2626' },
              { title: 'MCP 工具', value: stats.mcp_tools, color: '#0f766e' },
            ].map((item) => (
              <Col span={24 / 4} key={item.title} style={{ marginBottom: 16 }}>
                <Card
                  style={{ borderRadius: 10, border: 'none', boxShadow: '0 1px 4px rgba(0,0,0,0.08)' }}
                  styles={{ body: { padding: '20px 24px' } }}
                >
                  <Statistic
                    title={item.title}
                    value={item.value}
                    valueStyle={{ color: item.color, fontWeight: 700 }}
                  />
                </Card>
              </Col>
            ))}
          </Row>
          <Card style={{ borderRadius: 10 }}>
            <Title level={5}>系统信息</Title>
            <Text type="secondary">晓曼 Xiaoman v1.0.0 - AI 智能运维助手</Text>
            <br />
            <Text type="secondary">Python FastAPI + React + LiteLLM</Text>
          </Card>
        </div>
      ),
    },
    {
      key: 'llm',
      label: (
        <span><RobotOutlined /> LLM 提供商</span>
      ),
      children: (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
            <Title level={5} style={{ margin: 0 }}>LLM 提供商管理</Title>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => {
                setEditingProvider(null)
                setProviderFormOpen(true)
              }}
              style={{ background: 'linear-gradient(135deg, #4f46e5, #6366f1)', border: 'none' }}
            >
              添加提供商
            </Button>
          </div>
          {providers.length === 0 ? (
            <Card style={{ textAlign: 'center', padding: 40 }}>
              <RobotOutlined style={{ fontSize: 48, color: '#e2e8f0', marginBottom: 16 }} />
              <br />
              <Text type="secondary">暂无 LLM 提供商，请添加</Text>
              <br />
              <Button
                type="primary"
                icon={<PlusOutlined />}
                style={{ marginTop: 12 }}
                onClick={() => setProviderFormOpen(true)}
              >
                添加第一个
              </Button>
            </Card>
          ) : (
            providers.map((p) => (
              <ProviderCard
                key={p.id}
                provider={p}
                onEdit={(p) => {
                  setEditingProvider(p)
                  setProviderFormOpen(true)
                }}
                onDelete={handleProviderDelete}
                onTest={handleProviderTest}
                onSetDefault={handleSetDefault}
                testing={testingId === p.id}
              />
            ))
          )}
        </div>
      ),
    },
    {
      key: 'embed',
      label: (
        <span><DatabaseOutlined /> Embed 模型</span>
      ),
      children: (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
            <Title level={5} style={{ margin: 0 }}>Embedding 提供商管理</Title>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => {
                setEditingEmbedProvider(null)
                setEmbedFormOpen(true)
              }}
              style={{ background: 'linear-gradient(135deg, #0891b2, #0e7490)', border: 'none' }}
            >
              添加提供商
            </Button>
          </div>
          {embedProviders.length === 0 ? (
            <Card style={{ textAlign: 'center', padding: 40 }}>
              <DatabaseOutlined style={{ fontSize: 48, color: '#e2e8f0', marginBottom: 16 }} />
              <br />
              <Text type="secondary">暂无 Embedding 提供商，请添加</Text>
              <br />
              <Button
                type="primary"
                icon={<PlusOutlined />}
                style={{ marginTop: 12 }}
                onClick={() => setEmbedFormOpen(true)}
              >
                添加第一个
              </Button>
            </Card>
          ) : (
            embedProviders.map((p) => (
              <EmbedProviderCard
                key={p.id}
                provider={p}
                onEdit={(p) => {
                  setEditingEmbedProvider(p)
                  setEmbedFormOpen(true)
                }}
                onDelete={handleEmbedProviderDelete}
                onTest={handleEmbedProviderTest}
                onSetDefault={handleEmbedSetDefault}
                testing={embedTestingId === p.id}
              />
            ))
          )}
        </div>
      ),
    },
    {
      key: 'ocr',
      label: (
        <span><AppstoreOutlined /> OCR 视觉模型</span>
      ),
      children: (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
            <Title level={5} style={{ margin: 0 }}>OCR 视觉模型管理</Title>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => {
                setEditingOcrProvider(null)
                setOcrFormOpen(true)
              }}
              style={{ background: 'linear-gradient(135deg, #d97706, #b45309)', border: 'none' }}
            >
              添加提供商
            </Button>
          </div>
          {ocrProviders.length === 0 ? (
            <Card style={{ textAlign: 'center', padding: 40 }}>
              <AppstoreOutlined style={{ fontSize: 48, color: '#e2e8f0', marginBottom: 16 }} />
              <br />
              <Text type="secondary">暂无 OCR 视觉提供商，请添加</Text>
              <br />
              <Button
                type="primary"
                icon={<PlusOutlined />}
                style={{ marginTop: 12 }}
                onClick={() => setOcrFormOpen(true)}
              >
                添加第一个
              </Button>
            </Card>
          ) : (
            ocrProviders.map((p) => (
              <OCRProviderCard
                key={p.id}
                provider={p}
                onEdit={(p) => {
                  setEditingOcrProvider(p)
                  setOcrFormOpen(true)
                }}
                onDelete={handleOcrProviderDelete}
                onTest={handleOcrProviderTest}
                onSetDefault={handleOcrSetDefault}
                testing={ocrTestingId === p.id}
              />
            ))
          )}
        </div>
      ),
    },
    {
      key: 'search',
      label: (
        <span><SearchOutlined /> 联网搜索</span>
      ),
      children: (
        <div>
          <Title level={5} style={{ marginBottom: 16 }}>联网搜索配置</Title>
          <Alert
            type="info"
            showIcon
            style={{ marginBottom: 20 }}
            message="说明"
            description={
              <div>
                <p style={{ margin: '4px 0' }}>默认使用 DuckDuckGo 免费搜索（在中国大陆可能被限制）。</p>
                <p style={{ margin: '4px 0' }}>推荐配置 Tavily API，稳定可靠，注册后可获得每月免费额度。</p>
              </div>
            }
          />
          <Form layout="vertical" style={{ maxWidth: 480 }}>
            <Form.Item label="搜索引擎">
              <Select
                value={searchProvider}
                onChange={setSearchProvider}
                options={[
                  { value: 'duckduckgo', label: 'DuckDuckGo（免费，国内可能受限）' },
                  { value: 'tavily', label: 'Tavily（推荐，需要 API Key）' },
                ]}
              />
            </Form.Item>
            {searchProvider === 'tavily' && (
              <Form.Item label={hasSearchApiKey ? 'Tavily API Key（留空保持不变）' : 'Tavily API Key'}>
                <Input.Password
                  value={searchApiKey}
                  onChange={(e) => setSearchApiKey(e.target.value)}
                  placeholder={hasSearchApiKey ? '已配置，留空不修改' : 'tvly-...'}
                />
              </Form.Item>
            )}
            <Button
              type="primary"
              loading={searchConfigLoading}
              onClick={handleSearchConfigSave}
              style={{ background: 'linear-gradient(135deg, #4f46e5, #6366f1)', border: 'none' }}
            >
              保存配置
            </Button>
          </Form>
        </div>
      ),
    },
    {
      key: 'mcp',
      label: (
        <span><ThunderboltOutlined /> MCP 工具</span>
      ),
      children: (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
            <Title level={5} style={{ margin: 0 }}>MCP 工具管理</Title>
            <Space>
              <Button
                icon={<SearchOutlined />}
                onClick={() => {
                  discoverForm.resetFields()
                  discoverForm.setFieldsValue({ transport: 'sse' })
                  setDiscoverOpen(true)
                }}
              >
                自动发现
              </Button>
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={() => {
                  setEditingMcp(null)
                  mcpForm.resetFields()
                  mcpForm.setFieldsValue({ transport: 'sse', timeout_secs: 30, is_active: true })
                  setMcpFormOpen(true)
                }}
                style={{ background: 'linear-gradient(135deg, #4f46e5, #6366f1)', border: 'none' }}
              >
                添加工具
              </Button>
            </Space>
          </div>
          <Table
            columns={mcpColumns}
            dataSource={mcpTools}
            rowKey="id"
            size="small"
            pagination={false}
            expandable={{
              expandedRowRender: (tool: MCPTool) => (
                <div style={{ padding: '8px 16px', background: '#f8fafc', borderRadius: 6 }}>
                  <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 6, fontWeight: 500 }}>
                    Parameters (inputSchema)
                  </div>
                  {renderMcpParams(tool)}
                </div>
              ),
              rowExpandable: () => true,
            }}
          />
        </div>
      ),
    },
    {
      key: 'feishu',
      label: <span>飞书集成</span>,
      children: (
        <div style={{ maxWidth: 560 }}>
          <Title level={5} style={{ marginBottom: 8 }}>飞书机器人配置（WebSocket 长连接）</Title>
          <Alert
            type={feishuConfig?.ws_connected ? 'success' : 'warning'}
            showIcon
            style={{ marginBottom: 16 }}
            message={feishuConfig?.ws_connected ? 'WebSocket 长连接已建立' : 'WebSocket 未连接'}
            description={feishuConfig?.ws_connected
              ? '机器人已主动连接飞书服务器，内网环境下正常工作'
              : '保存配置并启用后，服务重启时将自动建立 WebSocket 长连接'}
          />
          <Form form={feishuForm} layout="vertical">
            <Form.Item name="enabled" label="启用飞书集成" valuePropName="checked">
              <Switch />
            </Form.Item>
            <Form.Item name="app_id" label="App ID">
              <Input placeholder="cli_xxxxxxxxxx" />
            </Form.Item>
            <Form.Item name="app_secret" label="App Secret">
              <Input.Password
                placeholder={feishuConfig?.has_app_secret ? '已配置（留空则不修改）' : '请输入 App Secret'}
                autoComplete="new-password"
              />
            </Form.Item>
            <Form.Item name="bot_open_id" label="机器人 Open ID（群聊 @ 检测）">
              <Input placeholder="ou_xxxxxxxx，用于识别群内 @机器人" />
            </Form.Item>
            <Form.Item name="default_push_chat_id" label="默认推送 Chat ID（可选）">
              <Input placeholder="oc_xxxxxxxx，用于测试消息发送" />
            </Form.Item>
            <Space>
              <Button type="primary" onClick={handleFeishuSave} loading={feishuSaving}
                style={{ background: 'linear-gradient(135deg, #4f46e5, #6366f1)', border: 'none' }}>
                保存配置
              </Button>
              <Button onClick={handleFeishuTest} loading={feishuTesting}>
                测试连接
              </Button>
            </Space>
          </Form>
        </div>
      ),
    },
  ]

  return (
    <div style={{ padding: 24 }}>
      <Tabs items={tabItems} />

      {/* Provider Form */}
      <ProviderForm
        open={providerFormOpen}
        onClose={() => {
          setProviderFormOpen(false)
          setEditingProvider(null)
        }}
        onSubmit={handleProviderSubmit}
        initialValues={editingProvider}
        loading={providerFormLoading}
      />

      {/* Embed Provider Form */}
      <EmbedProviderForm
        open={embedFormOpen}
        onClose={() => {
          setEmbedFormOpen(false)
          setEditingEmbedProvider(null)
        }}
        onSubmit={handleEmbedProviderSubmit}
        initialValues={editingEmbedProvider}
        loading={embedFormLoading}
      />

      {/* OCR Provider Form */}
      <OCRProviderForm
        open={ocrFormOpen}
        onClose={() => {
          setOcrFormOpen(false)
          setEditingOcrProvider(null)
        }}
        onSubmit={handleOcrProviderSubmit}
        initialValues={editingOcrProvider}
        loading={ocrFormLoading}
      />

      {/* MCP Form */}
      <Modal
        title={editingMcp ? '编辑 MCP 工具' : '添加 MCP 工具'}
        open={mcpFormOpen}
        onOk={handleMcpSubmit}
        onCancel={() => {
          setMcpFormOpen(false)
          setEditingMcp(null)
        }}
        confirmLoading={mcpFormLoading}
        okText={editingMcp ? '保存' : '添加'}
        cancelText="取消"
      >
        <Form form={mcpForm} layout="vertical" style={{ marginTop: 16 }}>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="name" label="工具标识名" rules={[{ required: true }]}>
                <Input placeholder="例如: k8s_logs" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="display_name" label="显示名称">
                <Input placeholder="K8s 日志分析" />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="server_url" label="服务器地址" rules={[{ required: true }]}>
            <Input placeholder="http://localhost:8080/mcp" />
          </Form.Item>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="transport" label="传输协议" initialValue="sse">
                <Select options={[{ value: 'sse', label: 'SSE' }, { value: 'http', label: 'HTTP' }, { value: 'stdio', label: 'STDIO' }]} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="timeout_secs" label="超时(秒)" initialValue={30}>
                <InputNumber min={1} max={300} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="is_active" label="启用" valuePropName="checked" initialValue={true}>
            <Switch />
          </Form.Item>
        </Form>
      </Modal>

      {/* MCP Discover Modal */}
      <Modal
        title="自动发现 MCP 工具"
        open={discoverOpen}
        onOk={handleMcpDiscover}
        onCancel={() => { setDiscoverOpen(false); discoverForm.resetFields() }}
        confirmLoading={discoverLoading}
        okText="开始发现"
        cancelText="取消"
      >
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="连接 MCP 服务器，自动获取所有可用工具并保存到数据库。已存在的同名工具将更新 schema。"
        />
        <Form form={discoverForm} layout="vertical">
          <Form.Item name="server_url" label="MCP 服务器地址" rules={[{ required: true, message: '请输入服务器地址' }]}>
            <Input placeholder="http://localhost:8080/mcp" />
          </Form.Item>
          <Form.Item name="transport" label="传输协议" initialValue="sse">
            <Select options={[
              { value: 'sse', label: 'SSE（Server-Sent Events）' },
              { value: 'http', label: 'HTTP（JSON-RPC）' },
            ]} />
          </Form.Item>
        </Form>
      </Modal>

      {/* MCP Execute Test Modal */}
      <Modal
        title={`测试执行: ${mcpTools.find((t) => t.id === execToolId)?.display_name || execToolId}`}
        open={!!execToolId}
        onCancel={() => { setExecToolId(null); setExecOutput(''); setExecParams('{}'); setExecParamsError('') }}
        footer={[
          <Button key="close" onClick={() => { setExecToolId(null); setExecOutput(''); setExecParams('{}'); setExecParamsError('') }}>关闭</Button>,
          <Button key="run" type="primary" icon={<PlayCircleOutlined />}
            loading={execRunning}
            onClick={() => {
              const tool = mcpTools.find((t) => t.id === execToolId)
              if (tool) handleMcpExecute(tool)
            }}>
            执行
          </Button>,
        ]}
        width={640}
      >
        <div style={{ marginBottom: 12 }}>
          <div style={{ marginBottom: 4, color: '#64748b', fontSize: 13 }}>
            工具参数（JSON 格式）：
          </div>
          <Input.TextArea
            rows={4}
            placeholder='{"param1": "value1", "param2": 10}'
            value={execParams}
            onChange={(e) => { setExecParams(e.target.value); setExecParamsError('') }}
            style={{ fontFamily: 'monospace', fontSize: 13 }}
          />
          {execParamsError && <div style={{ color: '#ef4444', fontSize: 12, marginTop: 4 }}>{execParamsError}</div>}
        </div>
        {execOutput && (
          <div style={{
            background: '#0f172a', color: '#e2e8f0', borderRadius: 8,
            padding: '12px 16px', fontFamily: 'monospace', fontSize: 13,
            maxHeight: 320, overflowY: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-all',
          }}>
            {execOutput}
            {execRunning && <span style={{ color: '#60a5fa' }}>▋</span>}
          </div>
        )}
        {!execOutput && !execRunning && (
          <div style={{ textAlign: 'center', color: '#94a3b8', padding: 24 }}>
            点击「执行」按钮开始测试工具调用
          </div>
        )}
      </Modal>
    </div>
  )
}
