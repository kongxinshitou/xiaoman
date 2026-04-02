import client from './client'
import type { FeishuConfig, FeishuConfigUpdate, FeishuPushRequest, FeishuCreateGroupRequest } from '../types/feishu'

export const feishuApi = {
  getConfig: async (): Promise<FeishuConfig> => {
    const res = await client.get<FeishuConfig>('/feishu/config')
    return res.data
  },

  updateConfig: async (data: FeishuConfigUpdate): Promise<{ message: string }> => {
    const res = await client.patch('/feishu/config', data)
    return res.data
  },

  testConnection: async (): Promise<{ message: string }> => {
    const res = await client.post('/feishu/test')
    return res.data
  },

  push: async (data: FeishuPushRequest): Promise<{ message: string }> => {
    const res = await client.post('/feishu/push', data)
    return res.data
  },

  createGroup: async (data: FeishuCreateGroupRequest): Promise<{ chat_id: string; name: string }> => {
    const res = await client.post('/feishu/create-group', data)
    return res.data
  },
}
