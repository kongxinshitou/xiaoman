import client from './client'
import type { EmbedProvider, EmbedProviderCreate, EmbedProviderUpdate } from '../types/embed'

export const embedProvidersApi = {
  create: async (data: EmbedProviderCreate) => {
    const res = await client.post<EmbedProvider>('/embed-providers', data)
    return res.data
  },

  list: async () => {
    const res = await client.get<EmbedProvider[]>('/embed-providers')
    return res.data
  },

  get: async (id: string) => {
    const res = await client.get<EmbedProvider>(`/embed-providers/${id}`)
    return res.data
  },

  update: async (id: string, data: EmbedProviderUpdate) => {
    const res = await client.patch<EmbedProvider>(`/embed-providers/${id}`, data)
    return res.data
  },

  delete: async (id: string) => {
    await client.delete(`/embed-providers/${id}`)
  },

  test: async (id: string) => {
    const res = await client.post<{ status: string; message: string }>(`/embed-providers/${id}/test`)
    return res.data
  },

  fetchModels: async (data: { provider_type: string; api_key: string; base_url?: string }) => {
    const res = await client.post<{ models: string[] }>('/embed-providers/fetch-models', data)
    return res.data.models
  },
}
