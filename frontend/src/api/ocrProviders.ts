import client from './client'
import type { OCRProvider, OCRProviderCreate, OCRProviderUpdate } from '../types/ocr'

export const ocrProvidersApi = {
  create: async (data: OCRProviderCreate) => {
    const res = await client.post<OCRProvider>('/ocr-providers', data)
    return res.data
  },

  list: async () => {
    const res = await client.get<OCRProvider[]>('/ocr-providers')
    return res.data
  },

  get: async (id: string) => {
    const res = await client.get<OCRProvider>(`/ocr-providers/${id}`)
    return res.data
  },

  update: async (id: string, data: OCRProviderUpdate) => {
    const res = await client.patch<OCRProvider>(`/ocr-providers/${id}`, data)
    return res.data
  },

  delete: async (id: string) => {
    await client.delete(`/ocr-providers/${id}`)
  },

  test: async (id: string) => {
    const res = await client.post<{ status: string; message: string }>(`/ocr-providers/${id}/test`)
    return res.data
  },

  fetchModels: async (data: { provider_type: string; api_key: string; base_url?: string }) => {
    const res = await client.post<{ models: string[] }>('/ocr-providers/fetch-models', data)
    return res.data.models
  },
}
