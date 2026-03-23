export interface FeishuConfig {
  id: string
  app_id: string
  verify_token: string
  encrypt_key: string
  default_push_chat_id: string
  enabled: boolean
  has_app_secret: boolean
  updated_at: string
}

export interface FeishuConfigUpdate {
  app_id?: string
  app_secret?: string
  verify_token?: string
  encrypt_key?: string
  default_push_chat_id?: string
  enabled?: boolean
}

export interface FeishuPushRequest {
  title: string
  content: string
  chat_id?: string
}
