import { useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { message } from 'antd'

export function useAuth() {
  const navigate = useNavigate()
  const { user, token, isAuthenticated, login, logout, refreshUser } = useAuthStore()

  const handleLogin = useCallback(
    async (username: string, password: string) => {
      await login(username, password)
      navigate('/chat')
    },
    [login, navigate],
  )

  const handleLogout = useCallback(() => {
    logout()
    message.success('已退出登录')
    navigate('/login')
  }, [logout, navigate])

  return {
    user,
    token,
    isAuthenticated,
    login: handleLogin,
    logout: handleLogout,
    refreshUser,
  }
}
