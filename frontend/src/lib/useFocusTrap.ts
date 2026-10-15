import { useEffect, useRef } from 'react'

/**
 * Element contract for the modal focus trap.
 *
 * `dialogRef` is the overlay `role="dialog"` panel (it must be focusable, i.e.
 * carry `tabIndex={-1}`) and `panelRef` is the element inside it whose Tab
 * cycle is wrapped - pass the same node for both in a single-panel dialog.
 */
export interface FocusTrapRefs {
  dialogRef: React.RefObject<HTMLElement | null>
  panelRef: React.RefObject<HTMLElement | null>
}

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

/**
 * The three things every overlay here owes a keyboard user: focus moves into
 * the dialog when it opens, `Escape` closes it, and focus returns to the
 * element that opened it. Tab is wrapped inside the panel so the page behind
 * the scrim stays out of reach.
 *
 * Behaviour-preserving on purpose: the only listener is on `document`, it runs
 * for as long as `isOpen` is true, and it stops nothing that was not already
 * keyboard-navigable.
 */
export function useFocusTrap(
  isOpen: boolean,
  onClose: () => void,
  { dialogRef, panelRef }: FocusTrapRefs,
  restoreFocus = true
): void {
  const onCloseRef = useRef(onClose)
  onCloseRef.current = onClose

  useEffect(() => {
    if (!isOpen) return

    const previous = restoreFocus ? (document.activeElement as HTMLElement | null) : null
    dialogRef.current?.focus()

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        onCloseRef.current()
        return
      }
      if (event.key !== 'Tab') return
      const panel = panelRef.current
      if (!panel) return
      const items = Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
        (el) => !el.hasAttribute('disabled')
      )
      if (items.length === 0) return
      const first = items[0]
      const last = items[items.length - 1]
      const active = document.activeElement as HTMLElement | null
      // The panel itself holds focus when the dialog opens, and focus can end
      // up back on it if the control that had focus is unmounted (a sign-off
      // button that retires on success). Both cases start the cycle at the top.
      if (active === panel) {
        event.preventDefault()
        ;(event.shiftKey ? last : first).focus()
        return
      }
      if (!active || !panel.contains(active) || !items.includes(active)) {
        event.preventDefault()
        first.focus()
        return
      }
      if (event.shiftKey && active === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && active === last) {
        event.preventDefault()
        first.focus()
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      previous?.focus?.()
    }
  }, [isOpen, restoreFocus, dialogRef, panelRef])
}
