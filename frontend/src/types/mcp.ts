export interface MCPTool {
  id: string
  name: string
  display_name: string | null
  description: string | null
  server_url: string
  transport: string
  tool_schema: string
  is_active: boolean
  timeout_secs: number
  created_at: string
  updated_at: string
}

export interface MCPToolCreate {
  name: string
  display_name?: string
  description?: string
  server_url: string
  transport?: string
  tool_schema?: string
  is_active?: boolean
  timeout_secs?: number
}

export interface MCPToolUpdate {
  display_name?: string
  description?: string
  server_url?: string
  transport?: string
  tool_schema?: string
  is_active?: boolean
  timeout_secs?: number
}
