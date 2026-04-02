import client from './client'
import type { MCPTool, MCPToolCreate, MCPToolUpdate } from '../types/mcp'

export const mcpToolsApi = {
  create: async (data: MCPToolCreate) => {
    const res = await client.post<MCPTool>('/mcp-tools', data)
    return res.data
  },

  list: async () => {
    const res = await client.get<MCPTool[]>('/mcp-tools')
    return res.data
  },

  get: async (id: string) => {
    const res = await client.get<MCPTool>(`/mcp-tools/${id}`)
    return res.data
  },

  update: async (id: string, data: MCPToolUpdate) => {
    const res = await client.patch<MCPTool>(`/mcp-tools/${id}`, data)
    return res.data
  },

  delete: async (id: string) => {
    await client.delete(`/mcp-tools/${id}`)
  },

  ping: async (id: string) => {
    const res = await client.post<{ status: string }>(`/mcp-tools/${id}/ping`)
    return res.data
  },

  discover: async (serverUrl: string, transport: string = 'sse') => {
    const res = await client.post<{
      discovered: number
      saved: number
      tools: { name: string; description: string }[]
    }>('/mcp-tools/discover', { server_url: serverUrl, transport })
    return res.data
  },
}
