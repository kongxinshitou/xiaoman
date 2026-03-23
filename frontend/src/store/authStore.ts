import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import client from '../api/client'

interface User {
  id: string
  username: string
  email: string | null
  role: string
  is_active: boolean
}

interface AuthState {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  refreshUser: () => Promise<void>
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      isAuthenticated: false,

      login: async (username: string, password: string) => {
        const res = await client.post('/auth/login', { username, password })
        const { access_token, user_id, username: uname, role } = res.data
        localStorage.setItem('xiaoman_token', access_token)
        set({
          token: access_token,
          user: { id: user_id, username: uname, role, email: null, is_active: true },
          isAuthenticated: true,
        })
      },

      logout: () => {
        localStorage.removeItem('xiaoman_token')
        set({ user: null, token: null, isAuthenticated: false })
      },

      refreshUser: async () => {
        try {
          const res = await client.get('/auth/me')
          set({ user: res.data, isAuthenticated: true })
        } catch {
          set({ user: null, token: null, isAuthenticated: false })
        }
      },
    }),
    {
      name: 'xiaoman_auth',
    },
  ),
)
