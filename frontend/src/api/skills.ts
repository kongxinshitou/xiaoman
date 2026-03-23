import client from './client'
import type { Skill, SkillCreate, SkillUpdate } from '../types/skill'

export const skillsApi = {
  create: async (data: SkillCreate) => {
    const res = await client.post<Skill>('/skills', data)
    return res.data
  },

  list: async () => {
    const res = await client.get<Skill[]>('/skills')
    return res.data
  },

  get: async (id: string) => {
    const res = await client.get<Skill>(`/skills/${id}`)
    return res.data
  },

  update: async (id: string, data: SkillUpdate) => {
    const res = await client.patch<Skill>(`/skills/${id}`, data)
    return res.data
  },

  delete: async (id: string) => {
    await client.delete(`/skills/${id}`)
  },
}
