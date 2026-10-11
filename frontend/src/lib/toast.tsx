import { createContext, useCallback, useContext, useState, type ReactNode } from 'react'
import { Toast } from '../components/ui'

type ToastState = { message: string; kind: 'success' | 'error' } | null

const ToastContext = createContext<(message: string, kind?: 'success' | 'error') => void>(() => {})

export const useToast = () => useContext(ToastContext)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toast, setToast] = useState<ToastState>(null)
  const show = useCallback((message: string, kind: 'success' | 'error' = 'success') => {
    setToast({ message, kind })
    window.setTimeout(() => setToast(null), 4200)
  }, [])
  return (
    <ToastContext.Provider value={show}>
      {children}
      <Toast message={toast?.message ?? null} kind={toast?.kind ?? 'success'} />
    </ToastContext.Provider>
  )
}
