import client from './client'
import type { FeishuConfig, FeishuConfigUpdate, FeishuPushRequest } from '../types/feishu'

export const feishuApi = {
  getConfig: (): Promise<FeishuConfig> =>
    client.get('/feishu/config').then((r) => r.data),

  updateConfig: (data: FeishuConfigUpdate): Promise<FeishuConfig> =>
    client.patch('/feishu/config', data).then((r) => r.data),

  testConnection: (): Promise<{ status: string; message: string }> =>
    client.post('/feishu/test').then((r) => r.data),

  pushMessage: (data: FeishuPushRequest): Promise<{ message: string }> =>
    client.post('/feishu/push', data).then((r) => r.data),
}
