import client from './client'
import type { User, UserCreate, UserUpdate } from '../types/user'

export const usersApi = {
  list: async () => {
    const res = await client.get<User[]>('/auth/users')
    return res.data
  },
  create: async (data: UserCreate) => {
    const res = await client.post<User>('/auth/users', data)
    return res.data
  },
  update: async (id: string, data: UserUpdate) => {
    const res = await client.patch<User>(`/auth/users/${id}`, data)
    return res.data
  },
  disable: async (id: string) => {
    await client.delete(`/auth/users/${id}`)
  },
}
