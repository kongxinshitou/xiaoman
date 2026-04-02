import client from './client'
import type { KnowledgeBase, Document, KnowledgeBaseCreate, SearchResult } from '../types/knowledge'

export const knowledgeApi = {
  createKB: async (data: KnowledgeBaseCreate) => {
    const res = await client.post<KnowledgeBase>('/knowledge', data)
    return res.data
  },

  listKBs: async () => {
    const res = await client.get<KnowledgeBase[]>('/knowledge')
    return res.data
  },

  getKB: async (id: string) => {
    const res = await client.get<KnowledgeBase>(`/knowledge/${id}`)
    return res.data
  },

  updateKB: async (id: string, data: Partial<KnowledgeBaseCreate>) => {
    const res = await client.patch<KnowledgeBase>(`/knowledge/${id}`, data)
    return res.data
  },

  deleteKB: async (id: string) => {
    await client.delete(`/knowledge/${id}`)
  },

  listDocuments: async (kbId: string) => {
    const res = await client.get<Document[]>(`/knowledge/${kbId}/documents`)
    return res.data
  },

  uploadDocument: async (kbId: string, file: File, onProgress?: (p: number) => void) => {
    const formData = new FormData()
    formData.append('file', file)
    const res = await client.post<Document>(`/knowledge/${kbId}/documents`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (e) => {
        if (onProgress && e.total) {
          onProgress(Math.round((e.loaded / e.total) * 100))
        }
      },
    })
    return res.data
  },

  deleteDocument: async (kbId: string, docId: string) => {
    await client.delete(`/knowledge/${kbId}/documents/${docId}`)
  },

  search: async (kbId: string, query: string, topK = 5) => {
    const res = await client.get<SearchResult[]>(`/knowledge/${kbId}/search`, {
      params: { q: query, top_k: topK },
    })
    return res.data
  },
}
