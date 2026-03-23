export interface KnowledgeBase {
  id: string
  name: string
  description: string | null
  owner_id: string
  embed_model: string
  milvus_collection: string | null
  created_at: string
  updated_at: string
}

export interface Document {
  id: string
  kb_id: string
  filename: string
  file_type: string
  file_size: number
  status: 'pending' | 'processing' | 'ready' | 'error'
  chunk_count: number
  error_msg: string | null
  uploaded_by: string
  created_at: string
  updated_at: string
}

export interface KnowledgeBaseCreate {
  name: string
  description?: string
  embed_model?: string
}
