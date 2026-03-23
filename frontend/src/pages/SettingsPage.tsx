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
  DeleteOutlined,
  EditOutlined,
  WechatOutlined,
  PlayCircleOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  CopyOutlined,
} from '@ant-design/icons'
import type { LLMProvider, LLMProviderCreate } from '../types/llm'
import type { MCPTool, MCPToolCreate } from '../types/mcp'
import type { Skill } from '../types/skill'
import type { FeishuConfig } from '../types/feishu'
import { llmProvidersApi } from '../api/llmProviders'
import { mcpToolsApi } from '../api/mcpTools'
import { skillsApi } from '../api/skills'
import { feishuApi } from '../api/feishu'
import ProviderCard from '../components/llm/ProviderCard'
import ProviderForm from '../components/llm/ProviderForm'
import client from '../api/client'

const { Title, Text } = Typography

interface SystemStats {
  knowledge_bases: number
  documents: number
  llm_providers: number
  chat_sessions: number
  chat_messages: number
  skills: number
  mcp_tools: number
}

export default function SettingsPage() {
  const [providers, setProviders] = useState<LLMProvider[]>([])
  const [mcpTools, setMcpTools] = useState<MCPTool[]>([])
  const [skills, setSkills] = useState<Skill[]>([])
  const [stats, setStats] = useState<SystemStats | null>(null)
  const [testingId, setTestingId] = useState<string | null>(null)
  // Feishu state
  const [feishuConfig, setFeishuConfig] = useState<FeishuConfig | null>(null)
  const [feishuForm] = Form.useForm()
  const [feishuLoading, setFeishuLoading] = useState(false)
  const [feishuTesting, setFeishuTesting] = useState(false)
  const [feishuTestStatus, setFeishuTestStatus] = useState<'ok' | 'fail' | null>(null)
  // MCP execute test state
  const [execToolId, setExecToolId] = useState<string | null>(null)
  const [execQuery, setExecQuery] = useState('')
  const [execOutput, setExecOutput] = useState('')
  const [execRunning, setExecRunning] = useState(false)

  // Provider form
  const [providerFormOpen, setProviderFormOpen] = useState(false)
  const [editingProvider, setEditingProvider] = useState<LLMProvider | null>(null)
  const [providerFormLoading, setProviderFormLoading] = useState(false)

  // MCP form
  const [mcpFormOpen, setMcpFormOpen] = useState(false)
  const [editingMcp, setEditingMcp] = useState<MCPTool | null>(null)
  const [mcpForm] = Form.useForm()
  const [mcpFormLoading, setMcpFormLoading] = useState(false)

  // Skill form
  const [skillFormOpen, setSkillFormOpen] = useState(false)
  const [editingSkill, setEditingSkill] = useState<Skill | null>(null)
  const [skillForm] = Form.useForm()
  const [skillFormLoading, setSkillFormLoading] = useState(false)

  useEffect(() => {
    loadAll()
  }, [])

  const loadAll = async () => {
    try {
      const [pList, mList, sList, statsData, fsConfig] = await Promise.all([
        llmProvidersApi.list(),
        mcpToolsApi.list(),
        skillsApi.list(),
        client.get('/system/stats').then((r) => r.data),
        feishuApi.getConfig().catch(() => null),
      ])
      setProviders(pList)
      setMcpTools(mList)
      setSkills(sList)
      setStats(statsData)
      if (fsConfig) {
        setFeishuConfig(fsConfig)
        feishuForm.setFieldsValue({
          app_id: fsConfig.app_id,
          verify_token: fsConfig.verify_token,
          encrypt_key: fsConfig.encrypt_key,
          default_push_chat_id: fsConfig.default_push_chat_id,
          enabled: fsConfig.enabled,
        })
      }
    } catch (err) {
      console.error(err)
    }
  }

  // ── Feishu actions ──
  const handleFeishuSave = async () => {
    const values = await feishuForm.validateFields()
    try {
      setFeishuLoading(true)
      const updated = await feishuApi.updateConfig(values)
      setFeishuConfig(updated)
      message.success('飞书配置已保存')
    } catch {
      message.error('保存失败')
    } finally {
      setFeishuLoading(false)
    }
  }

  const handleFeishuTest = async () => {
    setFeishuTesting(true)
    setFeishuTestStatus(null)
    try {
      const res = await feishuApi.testConnection()
      setFeishuTestStatus(res.status === 'ok' ? 'ok' : 'fail')
      if (res.status === 'ok') message.success(res.message)
      else message.error(res.message)
    } catch {
      setFeishuTestStatus('fail')
      message.error('测试失败')
    } finally {
      setFeishuTesting(false)
    }
  }

  // ── MCP Execute Test ──
  const handleMcpExecute = async (tool: MCPTool) => {
    setExecToolId(tool.id)
    setExecOutput('')
    setExecRunning(true)
    const token = localStorage.getItem('token')
    try {
      const response = await fetch(`/api/v1/mcp-tools/${tool.id}/execute`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({ query: execQuery || '测试执行' }),
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

  // Skill actions
  const handleSkillSubmit = async () => {
    const values = await skillForm.validateFields()
    try {
      setSkillFormLoading(true)
      if (editingSkill) {
        const updated = await skillsApi.update(editingSkill.id, values)
        setSkills((prev) => prev.map((s) => (s.id === updated.id ? updated : s)))
        message.success('技能已更新')
      } else {
        const created = await skillsApi.create(values)
        setSkills((prev) => [...prev, created])
        message.success('技能已添加')
      }
      setSkillFormOpen(false)
      setEditingSkill(null)
      skillForm.resetFields()
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } }
      message.error(e?.response?.data?.detail || '操作失败')
    } finally {
      setSkillFormLoading(false)
    }
  }

  const handleSkillToggle = async (skill: Skill, active: boolean) => {
    try {
      const updated = await skillsApi.update(skill.id, { is_active: active })
      setSkills((prev) => prev.map((s) => (s.id === updated.id ? updated : s)))
    } catch {
      message.error('操作失败')
    }
  }

  const mcpColumns = [
    { title: '名称', dataIndex: 'name', key: 'name', render: (_: string, t: MCPTool) => t.display_name || t.name },
    { title: '服务地址', dataIndex: 'server_url', key: 'server_url', ellipsis: true },
    { title: '传输协议', dataIndex: 'transport', key: 'transport', render: (v: string) => <Tag>{v.toUpperCase()}</Tag> },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (v: boolean) => <Tag color={v ? 'success' : 'default'}>{v ? '启用' : '禁用'}</Tag>,
    },
    {
      title: '操作',
      key: 'action',
      render: (_: unknown, t: MCPTool) => (
        <Space>
          <Button size="small" onClick={() => handleMcpPing(t.id, t.display_name || t.name)}>Ping</Button>
          <Button size="small" icon={<PlayCircleOutlined />} type="primary" ghost
            onClick={() => { setExecToolId(t.id); setExecOutput(''); setExecQuery(''); }}>
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

  const skillColumns = [
    { title: '名称', dataIndex: 'display_name', key: 'display_name', render: (v: string, s: Skill) => v || s.name },
    { title: '类型', dataIndex: 'skill_type', key: 'skill_type', render: (v: string) => <Tag color="blue">{v.toUpperCase()}</Tag> },
    { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
    { title: '优先级', dataIndex: 'priority', key: 'priority' },
    {
      title: '启用',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (v: boolean, s: Skill) => (
        <Switch size="small" checked={v} onChange={(checked) => handleSkillToggle(s, checked)} />
      ),
    },
    {
      title: '操作',
      key: 'action',
      render: (_: unknown, s: Skill) => (
        <Space>
          <Button size="small" icon={<EditOutlined />} onClick={() => {
            setEditingSkill(s)
            skillForm.setFieldsValue(s)
            setSkillFormOpen(true)
          }} />
          <Popconfirm title="确认删除？" onConfirm={async () => {
            await skillsApi.delete(s.id)
            setSkills((prev) => prev.filter((x) => x.id !== s.id))
            message.success('已删除')
          }} okText="删除" cancelText="取消" okButtonProps={{ danger: true }}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ]

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
              { title: '技能', value: stats.skills, color: '#7c3aed' },
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
      key: 'mcp',
      label: (
        <span><ThunderboltOutlined /> MCP 工具</span>
      ),
      children: (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
            <Title level={5} style={{ margin: 0 }}>MCP 工具管理</Title>
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
          </div>
          <Table
            columns={mcpColumns}
            dataSource={mcpTools}
            rowKey="id"
            size="small"
            pagination={false}
          />
        </div>
      ),
    },
    {
      key: 'skills',
      label: (
        <span><AppstoreOutlined /> 技能管理</span>
      ),
      children: (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
            <Title level={5} style={{ margin: 0 }}>技能管理</Title>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => {
                setEditingSkill(null)
                skillForm.resetFields()
                skillForm.setFieldsValue({ skill_type: 'llm', is_active: true, priority: 100 })
                setSkillFormOpen(true)
              }}
              style={{ background: 'linear-gradient(135deg, #4f46e5, #6366f1)', border: 'none' }}
            >
              添加技能
            </Button>
          </div>
          <Table
            columns={skillColumns}
            dataSource={skills}
            rowKey="id"
            size="small"
            pagination={false}
          />
        </div>
      ),
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    {
      key: 'feishu',
      label: <span><WechatOutlined /> 飞书集成</span>,
      children: (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <Title level={5} style={{ margin: 0 }}>飞书机器人集成</Title>
            {feishuConfig && (
              <Badge
                status={feishuConfig.enabled ? 'success' : 'default'}
                text={feishuConfig.enabled ? '已启用' : '未启用'}
              />
            )}
          </div>

          <Alert
            type="info"
            showIcon
            style={{ marginBottom: 20 }}
            message="配置说明"
            description={
              <div>
                <p style={{ margin: '4px 0' }}>1. 在飞书开放平台创建企业自建应用，获取 App ID 和 App Secret</p>
                <p style={{ margin: '4px 0' }}>2. 开通「机器人」能力，在「事件订阅」中填写以下 Webhook 地址：</p>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, margin: '8px 0' }}>
                  <code style={{ background: '#f1f5f9', padding: '2px 8px', borderRadius: 4, flex: 1 }}>
                    {window.location.origin}/api/v1/feishu/webhook
                  </code>
                  <Button size="small" icon={<CopyOutlined />}
                    onClick={() => { navigator.clipboard.writeText(`${window.location.origin}/api/v1/feishu/webhook`); message.success('已复制') }}>
                    复制
                  </Button>
                </div>
                <p style={{ margin: '4px 0' }}>3. 订阅事件：<code>im.message.receive_v1</code></p>
                <p style={{ margin: '4px 0' }}>4. 填写下方配置并保存，然后点击「测试连接」验证</p>
              </div>
            }
          />

          <Form form={feishuForm} layout="vertical">
            <Row gutter={16}>
              <Col span={12}>
                <Form.Item name="app_id" label="App ID" rules={[{ required: false }]}>
                  <Input placeholder="cli_xxxxxxxxxx" />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item name="app_secret" label="App Secret">
                  <Input.Password placeholder={feishuConfig?.has_app_secret ? '已配置（留空不修改）' : '请输入 App Secret'} />
                </Form.Item>
              </Col>
            </Row>
            <Row gutter={16}>
              <Col span={12}>
                <Form.Item name="verify_token" label="Verification Token（事件验证）">
                  <Input placeholder="事件订阅页面中的 Verification Token" />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item name="encrypt_key" label="Encrypt Key（可选）">
                  <Input placeholder="开启加密时填写" />
                </Form.Item>
              </Col>
            </Row>
            <Form.Item name="default_push_chat_id" label="默认推送群 Chat ID（告警推送目标）">
              <Input placeholder="oc_xxxxxxxxxx（在飞书群中查看群信息可获取）" />
            </Form.Item>
            <Form.Item name="enabled" label="启用飞书集成" valuePropName="checked">
              <Switch />
            </Form.Item>

            <Divider />

            <Space>
              <Button type="primary" loading={feishuLoading} onClick={handleFeishuSave}
                style={{ background: 'linear-gradient(135deg, #4f46e5, #6366f1)', border: 'none' }}>
                保存配置
              </Button>
              <Button
                loading={feishuTesting}
                onClick={handleFeishuTest}
                icon={feishuTestStatus === 'ok' ? <CheckCircleOutlined style={{ color: '#22c55e' }} /> :
                  feishuTestStatus === 'fail' ? <CloseCircleOutlined style={{ color: '#ef4444' }} /> : undefined}
              >
                测试连接
              </Button>
            </Space>
          </Form>

          <Divider>手动推送测试</Divider>
          <FeishuPushPanel />
        </div>
      ),
    },
  ]

  function FeishuPushPanel() {
    const [pushForm] = Form.useForm()
    const [pushing, setPushing] = useState(false)
    const doPush = async () => {
      const vals = await pushForm.validateFields()
      setPushing(true)
      try {
        await feishuApi.pushMessage(vals)
        message.success('推送成功')
        pushForm.resetFields()
      } catch (e: unknown) {
        const err = e as { response?: { data?: { detail?: string } } }
        message.error(err?.response?.data?.detail || '推送失败')
      } finally {
        setPushing(false)
      }
    }
    return (
      <Form form={pushForm} layout="vertical" style={{ maxWidth: 480 }}>
        <Form.Item name="title" label="消息标题" rules={[{ required: true }]}>
          <Input placeholder="告警标题" />
        </Form.Item>
        <Form.Item name="content" label="消息内容" rules={[{ required: true }]}>
          <Input.TextArea rows={3} placeholder="支持 Markdown 格式" />
        </Form.Item>
        <Form.Item name="chat_id" label="目标 Chat ID（留空使用默认群）">
          <Input placeholder="oc_xxxxxxxxxx" />
        </Form.Item>
        <Button type="default" loading={pushing} onClick={doPush}>发送测试消息</Button>
      </Form>
    )
  }

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

      {/* Skill Form */}
      <Modal
        title={editingSkill ? '编辑技能' : '添加技能'}
        open={skillFormOpen}
        onOk={handleSkillSubmit}
        onCancel={() => {
          setSkillFormOpen(false)
          setEditingSkill(null)
        }}
        confirmLoading={skillFormLoading}
        okText={editingSkill ? '保存' : '添加'}
        cancelText="取消"
      >
        <Form form={skillForm} layout="vertical" style={{ marginTop: 16 }}>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="name" label="技能标识名" rules={[{ required: true }]}>
                <Input placeholder="例如: my_skill" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="display_name" label="显示名称">
                <Input placeholder="我的技能" />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="skill_type" label="技能类型" initialValue="llm">
                <Select options={[
                  { value: 'llm', label: '直接对话 (LLM)' },
                  { value: 'rag', label: 'RAG 知识检索' },
                  { value: 'mcp', label: 'MCP 工具调用' },
                ]} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="priority" label="优先级" initialValue={100}>
                <InputNumber min={1} max={999} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="trigger_keywords" label="触发关键词 (JSON数组)" initialValue="[]">
            <Input.TextArea rows={2} placeholder='["关键词1", "关键词2"]' />
          </Form.Item>
          <Form.Item name="trigger_keywords" label="触发关键词 (JSON数组, 可覆盖默认)" initialValue="[]">
            <Input.TextArea rows={2} placeholder='["执行", "run", "deploy"]' />
          </Form.Item>
          <Form.Item name="config" label="技能配置 (JSON)" initialValue="{}">
            <Input.TextArea rows={2} placeholder='{"tool_name": "k8s_logs"} 或 {"kb_ids": []}' />
          </Form.Item>
          <Form.Item name="is_active" label="启用" valuePropName="checked" initialValue={true}>
            <Switch />
          </Form.Item>
        </Form>
      </Modal>

      {/* MCP Execute Test Modal */}
      <Modal
        title={`测试执行: ${mcpTools.find((t) => t.id === execToolId)?.display_name || execToolId}`}
        open={!!execToolId}
        onCancel={() => { setExecToolId(null); setExecOutput(''); }}
        footer={[
          <Button key="close" onClick={() => { setExecToolId(null); setExecOutput(''); }}>关闭</Button>,
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
          <Input
            placeholder="输入查询/命令（留空则发送默认测试）"
            value={execQuery}
            onChange={(e) => setExecQuery(e.target.value)}
            onPressEnter={() => {
              const tool = mcpTools.find((t) => t.id === execToolId)
              if (tool) handleMcpExecute(tool)
            }}
          />
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
