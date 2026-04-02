export interface OCRProvider {
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
  updated_at: string
}

export interface OCRProviderCreate {
  name: string
  provider_type: string
  base_url?: string
  api_key: string
  model_name: string
  is_active?: boolean
  is_default?: boolean
}

export interface OCRProviderUpdate {
  name?: string
  provider_type?: string
  base_url?: string
  api_key?: string
  model_name?: string
  is_active?: boolean
  is_default?: boolean
}

export const OCR_PROVIDER_TYPES = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'qwen', label: '通义千问 (Qwen)' },
  { value: 'zhipu', label: '智谱 GLM (Zhipu)' },
  { value: 'custom', label: '自定义 (OpenAI 兼容)' },
]

export const OCR_BASE_URL_MAP: Record<string, string> = {
  qwen: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
  zhipu: 'https://open.bigmodel.cn/api/paas/v4',
  custom: '',
}
