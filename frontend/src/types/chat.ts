export interface ChatSession {
  id: string
  user_id: string
  title: string
  active_provider_id: string | null
  created_at: string
  updated_at: string
}

export interface ChatMessage {
  id: string
  session_id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  meta: string
  created_at: string
  // Local-only fields
  isStreaming?: boolean
  citations?: Citation[]
  toolCall?: ToolCallInfo
}

export interface Citation {
  doc_id: string
  text: string
  score: number
}

export interface ToolCallInfo {
  tool: string
  status: 'running' | 'done' | 'error'
  message: string
}

export interface ChatRequest {
  session_id: string
  message: string
  provider_id?: string
  kb_ids?: string[]
  stream?: boolean
}
