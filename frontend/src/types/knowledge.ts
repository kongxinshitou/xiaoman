export interface KnowledgeBase {
  id: string
  name: string
  description: string | null
  owner_id: string
  embed_model: string
  embed_base_url: string | null
  has_embed_key: boolean
  embed_provider_id: string | null
  ocr_provider_id: string | null
  milvus_collection: string | null
  chunk_size: number
  chunk_overlap: number
  top_k: number
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
  embed_api_key?: string
  embed_base_url?: string
  embed_provider_id?: string | null
  ocr_provider_id?: string | null
  chunk_size?: number
  chunk_overlap?: number
  top_k?: number
}

export interface SearchResult {
  chunk_text: string
  score: number
  doc_id: string
  chunk_idx: number
  document_name: string | null
}
