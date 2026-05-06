import { useEffect, useState } from 'react'
import {
  Button, Table, Tag, Space, Form, Input, Modal, Switch, Popconfirm, message, Typography, Alert,
} from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons'
import { departmentsApi } from '../../api/departments'
import type { Department } from '../../types/user'

const { Title } = Typography

interface FormState {
  open: boolean
  mode: 'create' | 'edit'
  target: Department | null
}

export default function DepartmentManagementTab() {
  const [depts, setDepts] = useState<Department[]>([])
  const [loading, setLoading] = useState(false)
  const [formState, setFormState] = useState<FormState>({ open: false, mode: 'create', target: null })
  const [submitting, setSubmitting] = useState(false)
  const [form] = Form.useForm()

  useEffect(() => {
    load()
  }, [])

  const load = async () => {
    setLoading(true)
    try {
      const list = await departmentsApi.list()
      setDepts(list)
    } catch (err: unknown) {
      const e = err as { response?: { status?: number } }
      if (e.response?.status === 403) {
        message.error('需要管理员权限')
      } else {
        message.error('加载部门失败')
      }
    } finally {
      setLoading(false)
    }
  }

  const openCreate = () => {
    form.resetFields()
    setFormState({ open: true, mode: 'create', target: null })
  }

  const openEdit = (d: Department) => {
    form.resetFields()
    form.setFieldsValue({ code: d.code, name: d.name, enabled: d.enabled })
    setFormState({ open: true, mode: 'edit', target: d })
  }

  const handleSubmit = async () => {
    const values = await form.validateFields()
    setSubmitting(true)
    try {
      if (formState.mode === 'create') {
        const created = await departmentsApi.create(values.code, values.name)
        setDepts((prev) => [...prev, created])
        message.success('部门已创建')
      } else if (formState.target) {
        const updated = await departmentsApi.update(formState.target.code, {
          name: values.name,
          enabled: values.enabled,
        })
        setDepts((prev) => prev.map((x) => (x.code === updated.code ? updated : x)))
        message.success('部门已更新')
      }
      setFormState({ open: false, mode: 'create', target: null })
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: { message?: string } | string } } }
      const detail = e?.response?.data?.detail
      const msg = typeof detail === 'string' ? detail : detail?.message
      message.error(msg || '操作失败')
    } finally {
      setSubmitting(false)
    }
  }

  const handleDelete = async (d: Department) => {
    try {
      await departmentsApi.remove(d.code)
      setDepts((prev) => prev.map((x) => (x.code === d.code ? { ...x, enabled: false } : x)))
      message.success('部门已停用')
    } catch {
      message.error('操作失败')
    }
  }

  const columns = [
    { title: '部门编码', dataIndex: 'code', key: 'code', width: 160, render: (v: string) => <code>{v}</code> },
    { title: '部门名称', dataIndex: 'name', key: 'name' },
    {
      title: '状态', dataIndex: 'enabled', key: 'enabled', width: 100,
      render: (v: boolean) => <Tag color={v ? 'success' : 'default'}>{v ? '启用' : '停用'}</Tag>,
    },
    {
      title: '操作', key: 'action', width: 180,
      render: (_: unknown, d: Department) => (
        <Space>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(d)}>编辑</Button>
          {d.enabled && (
            <Popconfirm title={`停用部门「${d.name}」？`} onConfirm={() => handleDelete(d)} okText="停用" cancelText="取消" okButtonProps={{ danger: true }}>
              <Button size="small" danger icon={<DeleteOutlined />}>停用</Button>
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ]

  return (
    <div>
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="部门用于权限策略中的 allow_dept 配置；编码（如 finance/hr/rd）建议保持稳定"
      />
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={5} style={{ margin: 0 }}>部门管理</Title>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={openCreate}
          style={{ background: 'linear-gradient(135deg, #4f46e5, #6366f1)', border: 'none' }}
        >
          新建部门
        </Button>
      </div>

      <Table
        rowKey="code"
        size="small"
        columns={columns}
        dataSource={depts}
        loading={loading}
        pagination={false}
      />

      <Modal
        title={formState.mode === 'create' ? '新建部门' : `编辑部门 - ${formState.target?.code}`}
        open={formState.open}
        onOk={handleSubmit}
        onCancel={() => setFormState({ open: false, mode: 'create', target: null })}
        confirmLoading={submitting}
        okText={formState.mode === 'create' ? '创建' : '保存'}
        cancelText="取消"
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            name="code"
            label="部门编码"
            rules={[
              { required: true, message: '请输入编码' },
              { pattern: /^[a-z0-9_-]{2,32}$/, message: '只能用小写字母/数字/下划线，2–32 位' },
            ]}
          >
            <Input placeholder="例如: finance" disabled={formState.mode === 'edit'} />
          </Form.Item>
          <Form.Item
            name="name"
            label="部门名称"
            rules={[{ required: true, message: '请输入名称' }]}
          >
            <Input placeholder="例如: 财务部" />
          </Form.Item>
          {formState.mode === 'edit' && (
            <Form.Item name="enabled" label="启用" valuePropName="checked">
              <Switch />
            </Form.Item>
          )}
        </Form>
      </Modal>
    </div>
  )
}
