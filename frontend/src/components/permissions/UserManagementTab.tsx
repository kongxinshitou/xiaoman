import { useEffect, useState } from 'react'
import {
  Button, Table, Tag, Space, Form, Input, Select, Modal, Switch, Popconfirm, message, Typography,
} from 'antd'
import { PlusOutlined, EditOutlined, StopOutlined, KeyOutlined } from '@ant-design/icons'
import { usersApi } from '../../api/users'
import { departmentsApi } from '../../api/departments'
import type { User, UserCreate, UserUpdate, Department, UserRole } from '../../types/user'

const { Title } = Typography

const ROLE_OPTIONS: { value: UserRole; label: string }[] = [
  { value: 'admin', label: '管理员 (admin)' },
  { value: 'manager', label: '主管 (manager)' },
  { value: 'employee', label: '员工 (employee)' },
]

const ROLE_COLORS: Record<UserRole, string> = {
  admin: 'red',
  manager: 'gold',
  employee: 'blue',
}

interface FormState {
  open: boolean
  mode: 'create' | 'edit'
  target: User | null
}

export default function UserManagementTab() {
  const [users, setUsers] = useState<User[]>([])
  const [depts, setDepts] = useState<Department[]>([])
  const [loading, setLoading] = useState(false)
  const [formState, setFormState] = useState<FormState>({ open: false, mode: 'create', target: null })
  const [submitting, setSubmitting] = useState(false)
  const [form] = Form.useForm()

  // Password reset modal state
  const [pwdTarget, setPwdTarget] = useState<User | null>(null)
  const [pwdValue, setPwdValue] = useState('')
  const [pwdSaving, setPwdSaving] = useState(false)

  useEffect(() => {
    loadAll()
  }, [])

  const loadAll = async () => {
    setLoading(true)
    try {
      const [u, d] = await Promise.all([usersApi.list(), departmentsApi.list().catch(() => [])])
      setUsers(u)
      setDepts(d.filter((x) => x.enabled))
    } catch (err: unknown) {
      const e = err as { response?: { status?: number } }
      if (e.response?.status === 403) {
        message.error('需要管理员权限才能查看用户列表')
      } else {
        message.error('加载用户列表失败')
      }
    } finally {
      setLoading(false)
    }
  }

  const openCreate = () => {
    form.resetFields()
    form.setFieldsValue({ role: 'employee', is_active: true })
    setFormState({ open: true, mode: 'create', target: null })
  }

  const openEdit = (u: User) => {
    form.resetFields()
    form.setFieldsValue({
      username: u.username,
      email: u.email || '',
      role: u.role,
      dept: u.dept || undefined,
      is_active: u.is_active,
    })
    setFormState({ open: true, mode: 'edit', target: u })
  }

  const closeForm = () => {
    setFormState({ open: false, mode: 'create', target: null })
    form.resetFields()
  }

  const handleSubmit = async () => {
    const values = await form.validateFields()
    setSubmitting(true)
    try {
      if (formState.mode === 'create') {
        const payload: UserCreate = {
          username: values.username,
          password: values.password,
          email: values.email || null,
          role: values.role,
          dept: values.dept || null,
        }
        const created = await usersApi.create(payload)
        setUsers((prev) => [created, ...prev])
        message.success('用户已创建')
      } else if (formState.target) {
        const payload: UserUpdate = {
          email: values.email ?? null,
          role: values.role,
          dept: values.dept || null,
          is_active: values.is_active,
        }
        const updated = await usersApi.update(formState.target.id, payload)
        setUsers((prev) => prev.map((x) => (x.id === updated.id ? updated : x)))
        message.success('用户已更新')
      }
      closeForm()
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } }
      message.error(e?.response?.data?.detail || '操作失败')
    } finally {
      setSubmitting(false)
    }
  }

  const handleDisable = async (u: User) => {
    try {
      await usersApi.disable(u.id)
      setUsers((prev) => prev.map((x) => (x.id === u.id ? { ...x, is_active: false } : x)))
      message.success('已禁用')
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } }
      message.error(e?.response?.data?.detail || '操作失败')
    }
  }

  const handleReenable = async (u: User) => {
    try {
      const updated = await usersApi.update(u.id, { is_active: true })
      setUsers((prev) => prev.map((x) => (x.id === updated.id ? updated : x)))
      message.success('已恢复')
    } catch {
      message.error('操作失败')
    }
  }

  const handlePwdReset = async () => {
    if (!pwdTarget || !pwdValue) return
    setPwdSaving(true)
    try {
      await usersApi.update(pwdTarget.id, { password: pwdValue })
      message.success('密码已重置')
      setPwdTarget(null)
      setPwdValue('')
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } }
      message.error(e?.response?.data?.detail || '重置失败')
    } finally {
      setPwdSaving(false)
    }
  }

  const deptName = (code?: string | null) => {
    if (!code) return '—'
    return depts.find((d) => d.code === code)?.name || code
  }

  const columns = [
    { title: '用户名', dataIndex: 'username', key: 'username' },
    { title: '邮箱', dataIndex: 'email', key: 'email', render: (v?: string) => v || <span style={{ color: '#94a3b8' }}>—</span> },
    {
      title: '角色',
      dataIndex: 'role',
      key: 'role',
      width: 110,
      render: (v: UserRole) => <Tag color={ROLE_COLORS[v] || 'default'}>{v}</Tag>,
    },
    {
      title: '部门',
      dataIndex: 'dept',
      key: 'dept',
      width: 140,
      render: (v: string | null) => deptName(v),
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      width: 90,
      render: (v: boolean) => (
        <Tag color={v ? 'success' : 'default'}>{v ? '启用' : '已禁用'}</Tag>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 240,
      render: (_: unknown, u: User) => (
        <Space>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(u)}>编辑</Button>
          <Button size="small" icon={<KeyOutlined />} onClick={() => { setPwdTarget(u); setPwdValue('') }}>
            重置密码
          </Button>
          {u.is_active ? (
            <Popconfirm title={`禁用 ${u.username}？`} onConfirm={() => handleDisable(u)} okText="禁用" cancelText="取消" okButtonProps={{ danger: true }}>
              <Button size="small" danger icon={<StopOutlined />}>禁用</Button>
            </Popconfirm>
          ) : (
            <Button size="small" onClick={() => handleReenable(u)}>启用</Button>
          )}
        </Space>
      ),
    },
  ]

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={5} style={{ margin: 0 }}>用户管理</Title>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={openCreate}
          style={{ background: 'linear-gradient(135deg, #4f46e5, #6366f1)', border: 'none' }}
        >
          新建用户
        </Button>
      </div>

      <Table
        rowKey="id"
        size="small"
        columns={columns}
        dataSource={users}
        loading={loading}
        pagination={{ pageSize: 20, showSizeChanger: false }}
      />

      <Modal
        title={formState.mode === 'create' ? '新建用户' : `编辑用户 - ${formState.target?.username}`}
        open={formState.open}
        onOk={handleSubmit}
        onCancel={closeForm}
        confirmLoading={submitting}
        okText={formState.mode === 'create' ? '创建' : '保存'}
        cancelText="取消"
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            name="username"
            label="用户名"
            rules={[{ required: true, message: '请输入用户名' }, { min: 2, max: 64 }]}
          >
            <Input placeholder="登录用户名" disabled={formState.mode === 'edit'} />
          </Form.Item>
          {formState.mode === 'create' && (
            <Form.Item
              name="password"
              label="密码"
              rules={[{ required: true, message: '请输入密码' }, { min: 6, message: '至少 6 位' }]}
            >
              <Input.Password placeholder="初始密码" autoComplete="new-password" />
            </Form.Item>
          )}
          <Form.Item name="email" label="邮箱（可选）">
            <Input placeholder="user@example.com" />
          </Form.Item>
          <Form.Item name="role" label="角色" rules={[{ required: true }]}>
            <Select options={ROLE_OPTIONS} />
          </Form.Item>
          <Form.Item name="dept" label="部门（可选）">
            <Select
              allowClear
              placeholder="选择部门"
              options={depts.map((d) => ({ value: d.code, label: `${d.name} (${d.code})` }))}
              notFoundContent={depts.length === 0 ? '暂无部门，请先在「部门管理」添加' : undefined}
            />
          </Form.Item>
          {formState.mode === 'edit' && (
            <Form.Item name="is_active" label="启用" valuePropName="checked">
              <Switch />
            </Form.Item>
          )}
        </Form>
      </Modal>

      <Modal
        title={`重置密码 - ${pwdTarget?.username || ''}`}
        open={!!pwdTarget}
        onOk={handlePwdReset}
        onCancel={() => { setPwdTarget(null); setPwdValue('') }}
        confirmLoading={pwdSaving}
        okText="重置"
        cancelText="取消"
        okButtonProps={{ disabled: pwdValue.length < 6 }}
      >
        <Input.Password
          value={pwdValue}
          onChange={(e) => setPwdValue(e.target.value)}
          placeholder="新密码（至少 6 位）"
          autoComplete="new-password"
        />
      </Modal>
    </div>
  )
}
