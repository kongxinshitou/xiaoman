import { create } from 'zustand'

type ModalType = 'newKb' | 'editKb' | 'newProvider' | 'editProvider' | 'newMcp' | 'editMcp' | 'newSkill' | 'editSkill' | null

interface UIState {
  activeModal: ModalType
  modalData: unknown
  globalLoading: boolean
  notification: { type: 'success' | 'error' | 'info' | 'warning'; message: string } | null

  openModal: (modal: ModalType, data?: unknown) => void
  closeModal: () => void
  setGlobalLoading: (loading: boolean) => void
  showNotification: (type: 'success' | 'error' | 'info' | 'warning', message: string) => void
  clearNotification: () => void
}

export const useUIStore = create<UIState>((set) => ({
  activeModal: null,
  modalData: null,
  globalLoading: false,
  notification: null,

  openModal: (modal, data = null) => set({ activeModal: modal, modalData: data }),
  closeModal: () => set({ activeModal: null, modalData: null }),
  setGlobalLoading: (loading) => set({ globalLoading: loading }),
  showNotification: (type, message) => set({ notification: { type, message } }),
  clearNotification: () => set({ notification: null }),
}))
