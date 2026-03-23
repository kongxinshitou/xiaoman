import { Layout, Dropdown, Avatar, Typography, Space, Badge } from 'antd'
import {
  LogoutOutlined,
  UserOutlined,
  BellOutlined,
  QuestionCircleOutlined,
} from '@ant-design/icons'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '../../store/authStore'

const { Header } = Layout
const { Text } = Typography

const PAGE_TITLES: Record<string, string> = {
  '/chat': '对话',
  '/knowledge': '知识库',
  '/settings': '系统设置',
}

export default function TopBar() {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, logout } = useAuthStore()

  const activeKey = '/' + location.pathname.split('/')[1]
  const title = PAGE_TITLES[activeKey] || '晓曼'

  const menuItems = [
    {
      key: 'profile',
      icon: <UserOutlined />,
      label: '个人信息',
    },
    {
      type: 'divider' as const,
    },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
      danger: true,
    },
  ]

  const handleMenuClick = ({ key }: { key: string }) => {
    if (key === 'logout') {
      logout()
      navigate('/login')
    }
  }

  return (
    <Header
      style={{
        background: 'white',
        padding: '0 24px',
        height: 56,
        lineHeight: '56px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        borderBottom: '1px solid #f0f0f0',
        boxShadow: '0 1px 4px rgba(0,21,41,0.06)',
      }}
    >
      <Text strong style={{ fontSize: 16 }}>
        {title}
      </Text>

      <Space size={16}>
        <Badge dot>
          <BellOutlined style={{ fontSize: 18, cursor: 'pointer', color: '#64748b' }} />
        </Badge>
        <QuestionCircleOutlined
          style={{ fontSize: 18, cursor: 'pointer', color: '#64748b' }}
        />
        <Dropdown menu={{ items: menuItems, onClick: handleMenuClick }} placement="bottomRight">
          <Space style={{ cursor: 'pointer' }}>
            <Avatar
              size={32}
              style={{ background: 'linear-gradient(135deg, #4f46e5, #7c3aed)' }}
            >
              {user?.username?.[0]?.toUpperCase() || 'U'}
            </Avatar>
            <Text style={{ fontSize: 13 }}>{user?.username}</Text>
          </Space>
        </Dropdown>
      </Space>
    </Header>
  )
}
