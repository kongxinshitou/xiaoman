export interface EmbedProvider {
  id: string
  name: string
  provider_type: string
  base_url: string | null
  model_name: string
  is_active: boolean
  is_default: boolean
  last_test_status: 'untested' | 'ok' | 'failed'
  last_tested_at: string | null
  created_at: string
}

export interface EmbedProviderCreate {
  name: string
  provider_type: string
  base_url?: string
  api_key: string
  model_name: string
  is_active?: boolean
  is_default?: boolean
}

export interface EmbedProviderUpdate {
  name?: string
  provider_type?: string
  base_url?: string
  api_key?: string
  model_name?: string
  is_active?: boolean
  is_default?: boolean
}

export const EMBED_PROVIDER_TYPES = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'qwen', label: '通义千问 (Qwen)' },
  { value: 'zhipu', label: '智谱 (ZhipuAI)' },
  { value: 'baichuan', label: '百川 (Baichuan)' },
  { value: 'custom', label: '自定义 (Custom)' },
]

export const EMBED_BASE_URL_MAP: Record<string, string> = {
  qwen: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
  zhipu: 'https://open.bigmodel.cn/api/paas/v4/',
  baichuan: 'https://api.baichuan-ai.com/v1',
}
