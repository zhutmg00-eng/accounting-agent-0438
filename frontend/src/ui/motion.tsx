import React, { useEffect, useRef, useState } from 'react'
import { cn } from './cn'

/* ===========================================================================
   Motion helpers.

   Rules (see DESIGN.md and taste-skill references/motion.md):
   * transform and opacity only;
   * one signature move per screen, not a fade on everything;
   * entrance is staggered 60-90ms per part, never one fade for a whole block;
   * content is never left hidden when the observer or the script fails;
   * every move degrades to "content present, no travel" under reduced motion.
   =========================================================================== */

const REVEAL_QUERY = '(prefers-reduced-motion: reduce)'

/** True when the visitor has asked the system to reduce motion. */
export function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false)

  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return
    const mql = window.matchMedia(REVEAL_QUERY)
    const update = () => setReduced(mql.matches)
    update()
    mql.addEventListener('change', update)
    return () => mql.removeEventListener('change', update)
  }, [])

  return reduced
}

/* One shared observer keeps scroll work off the main thread per component. */
let sharedObserver: IntersectionObserver | null = null
const observed = new WeakMap<Element, () => void>()

function observeOnce(el: Element, onEnter: () => void): () => void {
  if (typeof IntersectionObserver === 'undefined') {
    onEnter()
    return () => {}
  }
  sharedObserver ??= new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue
        observed.get(entry.target)?.()
        observed.delete(entry.target)
        sharedObserver?.unobserve(entry.target)
      }
    },
    { rootMargin: '0px 0px -8% 0px', threshold: 0.05 }
  )
  observed.set(el, onEnter)
  sharedObserver.observe(el)
  return () => {
    observed.delete(el)
    sharedObserver?.unobserve(el)
  }
}

interface RevealProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Stagger position. 0 renders immediately once the block is in view. */
  index?: number
  /** Milliseconds between siblings. 70 is the house step. */
  step?: number
  as?: 'div' | 'section' | 'li' | 'article' | 'header'
  children: React.ReactNode
}

/**
 * Enter once: rise 14px and fade in, delayed by its index.
 *
 * The element is visible by default and only hidden once the observer is
 * confirmed to be driving it, so a failed observer leaves content readable.
 */
export const Reveal: React.FC<RevealProps> = ({
  index = 0,
  step = 70,
  as = 'div',
  className,
  style,
  children,
  ...rest
}) => {
  const ref = useRef<HTMLElement | null>(null)
  const reduced = usePrefersReducedMotion()
  const [armed, setArmed] = useState(false)
  const [shown, setShown] = useState(false)

  useEffect(() => {
    if (reduced) {
      setShown(true)
      return
    }
    const el = ref.current
    if (!el) return
    setArmed(true)
    return observeOnce(el, () => setShown(true))
  }, [reduced])

  const Tag = as as React.ElementType

  return (
    <Tag
      ref={ref}
      className={cn(armed && !shown && 'reveal', shown && 'reveal is-in', className)}
      style={{ ...(style ?? {}), ['--reveal-delay' as string]: `${index * step}ms` }}
      {...rest}
    >
      {children}
    </Tag>
  )
}

/**
 * Count a figure up to its value once. Used for the verdict the whole screen
 * is about, and nowhere else - a number that counts on every panel is noise.
 */
export function useAnimatedNumber(target: number, durationMs = 700): number {
  const reduced = usePrefersReducedMotion()
  // Start at 0, not at `target`: initialising to the final value paints it for
  // one frame and then snaps back to 0 to count up, which reads as a flicker.
  const [value, setValue] = useState(() => (reduced ? target : 0))
  const fromRef = useRef(0)

  useEffect(() => {
    if (reduced || !Number.isFinite(target)) {
      setValue(target)
      return
    }
    const from = fromRef.current
    const start = performance.now()
    let frame = 0

    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / durationMs)
      // Ease out cubic: the number lands rather than stopping dead.
      const eased = 1 - Math.pow(1 - t, 3)
      setValue(from + (target - from) * eased)
      if (t < 1) frame = requestAnimationFrame(tick)
      else fromRef.current = target
    }

    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [target, durationMs, reduced])

  return value
}

/**
 * The signature move: an audit stage resolving.
 *
 * A stage that is running gets a sweeping rail; a stage that has resolved
 * stops moving and keeps its result. Purely decorative loops are banned here,
 * so the sweep only exists while work is genuinely in flight.
 */
export const StageRail: React.FC<{ state: 'pending' | 'running' | 'done' | 'failed' }> = ({
  state
}) => (
  <span aria-hidden className="block h-[3px] w-full overflow-hidden bg-field-raised3">
    {state === 'running' ? <span className="block h-full w-full origin-left animate-sweep bg-seal" /> : null}
    {state === 'done' ? <span className="block h-full w-full bg-risk-clear" /> : null}
    {state === 'failed' ? <span className="block h-full w-full bg-risk-critical" /> : null}
  </span>
)
