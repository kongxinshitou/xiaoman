import client from './client'
import type { LLMProvider, LLMProviderCreate, LLMProviderUpdate } from '../types/llm'

export const llmProvidersApi = {
  create: async (data: LLMProviderCreate) => {
    const res = await client.post<LLMProvider>('/llm-providers', data)
    return res.data
  },

  list: async () => {
    const res = await client.get<LLMProvider[]>('/llm-providers')
    return res.data
  },

  get: async (id: string) => {
    const res = await client.get<LLMProvider>(`/llm-providers/${id}`)
    return res.data
  },

  update: async (id: string, data: LLMProviderUpdate) => {
    const res = await client.patch<LLMProvider>(`/llm-providers/${id}`, data)
    return res.data
  },

  delete: async (id: string) => {
    await client.delete(`/llm-providers/${id}`)
  },

  test: async (id: string) => {
    const res = await client.post<{ status: string; message: string }>(`/llm-providers/${id}/test`)
    return res.data
  },

  fetchModels: async (data: { provider_type: string; api_key: string; base_url?: string }) => {
    const res = await client.post<{ models: string[] }>('/llm-providers/fetch-models', data)
    return res.data.models
  },
}
