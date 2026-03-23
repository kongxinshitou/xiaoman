import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { LLMProvider } from '../types/llm'
import type { KnowledgeBase } from '../types/knowledge'

interface SettingsState {
  selectedProviderId: string | null
  selectedKbIds: string[]
  providers: LLMProvider[]
  knowledgeBases: KnowledgeBase[]
  sidebarCollapsed: boolean

  setSelectedProvider: (id: string | null) => void
  toggleKbSelection: (id: string) => void
  setSelectedKbIds: (ids: string[]) => void
  setProviders: (providers: LLMProvider[]) => void
  setKnowledgeBases: (kbs: KnowledgeBase[]) => void
  setSidebarCollapsed: (collapsed: boolean) => void
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      selectedProviderId: null,
      selectedKbIds: [],
      providers: [],
      knowledgeBases: [],
      sidebarCollapsed: false,

      setSelectedProvider: (id) => set({ selectedProviderId: id }),
      toggleKbSelection: (id) =>
        set((s) => ({
          selectedKbIds: s.selectedKbIds.includes(id)
            ? s.selectedKbIds.filter((k) => k !== id)
            : [...s.selectedKbIds, id],
        })),
      setSelectedKbIds: (ids) => set({ selectedKbIds: ids }),
      setProviders: (providers) => set({ providers }),
      setKnowledgeBases: (kbs) => set({ knowledgeBases: kbs }),
      setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
    }),
    {
      name: 'xiaoman_settings',
    },
  ),
)
