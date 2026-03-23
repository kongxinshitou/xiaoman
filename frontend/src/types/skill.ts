export interface Skill {
  id: string
  name: string
  display_name: string | null
  description: string | null
  skill_type: 'llm' | 'rag' | 'mcp'
  config: string
  trigger_keywords: string
  is_active: boolean
  priority: number
  created_at: string
  updated_at: string
}

export interface SkillCreate {
  name: string
  display_name?: string
  description?: string
  skill_type?: string
  config?: string
  trigger_keywords?: string
  is_active?: boolean
  priority?: number
}

export interface SkillUpdate {
  display_name?: string
  description?: string
  skill_type?: string
  config?: string
  trigger_keywords?: string
  is_active?: boolean
  priority?: number
}
