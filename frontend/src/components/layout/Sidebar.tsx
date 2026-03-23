import { Layout, Menu, Typography, Avatar } from 'antd'
import {
  MessageOutlined,
  BookOutlined,
  SettingOutlined,
  RobotOutlined,
} from '@ant-design/icons'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '../../store/authStore'

const { Sider } = Layout
const { Text } = Typography

const menuItems = [
  {
    key: '/chat',
    icon: <MessageOutlined />,
    label: '对话',
  },
  {
    key: '/knowledge',
    icon: <BookOutlined />,
    label: '知识库',
  },
  {
    key: '/settings',
    icon: <SettingOutlined />,
    label: '设置',
  },
]

export default function Sidebar() {
  const navigate = useNavigate()
  const location = useLocation()
  const { user } = useAuthStore()

  const activeKey = '/' + location.pathname.split('/')[1]

  return (
    <Sider
      width={200}
      style={{
        background: '#0f172a',
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        overflow: 'hidden',
      }}
    >
      {/* Logo */}
      <div
        style={{
          padding: '20px 16px 16px',
          borderBottom: '1px solid rgba(255,255,255,0.06)',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
        }}
      >
        <div
          style={{
            width: 36,
            height: 36,
            background: 'linear-gradient(135deg, #4f46e5, #7c3aed)',
            borderRadius: 10,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <RobotOutlined style={{ color: 'white', fontSize: 18 }} />
        </div>
        <div>
          <div style={{ color: 'white', fontWeight: 700, fontSize: 15, lineHeight: '1.2' }}>
            晓曼
          </div>
          <div style={{ color: 'rgba(255,255,255,0.4)', fontSize: 11 }}>AI Ops Assistant</div>
        </div>
      </div>

      {/* Navigation */}
      <Menu
        mode="inline"
        selectedKeys={[activeKey]}
        onClick={({ key }) => navigate(key)}
        style={{
          background: 'transparent',
          border: 'none',
          padding: '8px 0',
          flex: 1,
        }}
        theme="dark"
        items={menuItems.map((item) => ({
          ...item,
          style: {
            margin: '2px 8px',
            borderRadius: 8,
          },
        }))}
      />

      {/* User info */}
      <div
        style={{
          padding: '12px 16px',
          borderTop: '1px solid rgba(255,255,255,0.06)',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
        }}
      >
        <Avatar
          size={32}
          style={{ background: 'linear-gradient(135deg, #4f46e5, #7c3aed)', flexShrink: 0 }}
        >
          {user?.username?.[0]?.toUpperCase() || 'U'}
        </Avatar>
        <div style={{ overflow: 'hidden' }}>
          <Text
            style={{ color: 'rgba(255,255,255,0.85)', fontSize: 13, display: 'block' }}
            ellipsis
          >
            {user?.username}
          </Text>
          <Text style={{ color: 'rgba(255,255,255,0.4)', fontSize: 11 }}>
            {user?.role === 'admin' ? '管理员' : '成员'}
          </Text>
        </div>
      </div>
    </Sider>
  )
}
