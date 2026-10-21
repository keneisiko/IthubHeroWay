import { useCallback, useEffect, useRef, useState } from 'react'

export function useModal(initial = false) {
  const [open, setOpen] = useState(initial)
  const ref = useRef<HTMLDivElement>(null)
  const openerRef = useRef<HTMLElement | null>(null)
  const show = useCallback(() => {
    openerRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null
    setOpen(true)
  }, [])
  const hide = useCallback(() => setOpen(false), [])

  useEffect(() => {
    if (!open) return
    const root = ref.current
    if (!root) return
    const opener = openerRef.current
    const controls = () => Array.from(root.querySelectorAll<HTMLElement>(
      'button:enabled, input:enabled:not([type="hidden"]), textarea:enabled, select:enabled, a[href], [tabindex]:not([tabindex="-1"])',
    )).filter((element) => element.getClientRects().length > 0)

    if (!root.contains(document.activeElement)) {
      const input = controls().find((element) => element.matches('input, textarea, select'))
      ;(input ?? controls()[0] ?? root).focus()
    }

    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        hide()
      } else if (event.key === 'Tab') {
        const items = controls()
        const first = items[0]
        const last = items[items.length - 1]
        if (!first) {
          event.preventDefault()
          root.focus()
        } else if (!root.contains(document.activeElement) || (event.shiftKey ? document.activeElement === first : document.activeElement === last)) {
          event.preventDefault()
          ;(event.shiftKey ? last : first).focus()
        }
      }
    }
    const onOutside = (event: MouseEvent) => {
      if (!root.contains(event.target as Node)) hide()
    }
    document.addEventListener('keydown', onKey)
    document.addEventListener('mousedown', onOutside)
    return () => {
      document.removeEventListener('keydown', onKey)
      document.removeEventListener('mousedown', onOutside)
      if (opener?.isConnected) opener.focus()
    }
  }, [open, hide])

  return { open, ref, show, hide }
}
