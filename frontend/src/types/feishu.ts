export interface FeishuConfig {
  app_id: string | null
  has_app_secret: boolean
  bot_open_id: string | null
  default_push_chat_id: string | null
  ws_connected: boolean
  enabled: boolean
}

export interface FeishuConfigUpdate {
  app_id?: string
  app_secret?: string
  bot_open_id?: string
  default_push_chat_id?: string
  enabled?: boolean
}

export interface FeishuPushRequest {
  chat_id: string
  message: string
  receive_id_type?: string
}

export interface FeishuCreateGroupRequest {
  name: string
  user_open_ids: string[]
  description?: string
}
