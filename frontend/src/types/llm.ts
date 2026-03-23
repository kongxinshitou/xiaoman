export interface LLMProvider {
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

export interface LLMProviderCreate {
  name: string
  provider_type: string
  base_url?: string
  api_key: string
  model_name: string
  is_active?: boolean
  is_default?: boolean
}

export interface LLMProviderUpdate {
  name?: string
  provider_type?: string
  base_url?: string
  api_key?: string
  model_name?: string
  is_active?: boolean
  is_default?: boolean
}

export const PROVIDER_TYPES = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'anthropic', label: 'Anthropic Claude' },
  { value: 'qwen', label: '通义千问 (Qwen)' },
  { value: 'doubao', label: '豆包 (Doubao)' },
  { value: 'zhipu', label: '智谱 (ZhipuAI)' },
  { value: 'moonshot', label: 'Moonshot (Kimi)' },
  { value: 'deepseek', label: 'DeepSeek' },
  { value: 'minimax', label: 'MiniMax' },
  { value: 'baichuan', label: '百川 (Baichuan)' },
  { value: 'custom', label: '自定义 (Custom)' },
]
