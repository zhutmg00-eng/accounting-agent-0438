import clsx, { type ClassValue } from 'clsx'
import { extendTailwindMerge } from 'tailwind-merge'

/**
 * Merge conditional classes, letting later Tailwind utilities win.
 *
 * tailwind-merge only knows Tailwind's stock type scale. Ours is named
 * (label / small / body / title / display), so without the extension below it
 * classifies `text-display` as a text COLOUR and drops it the moment a real
 * colour class follows it - which silently flattens the whole type scale and
 * is very hard to see, because the class is still written in the source and
 * still present in the compiled CSS.
 *
 * Lives in its own module so `primitives` and `motion` can both use it without
 * importing each other - `primitives` re-exports the motion helpers, and a
 * cycle between the two would be fragile.
 */
const twMerge = extendTailwindMerge({
  extend: {
    classGroups: {
      'font-size': [{ text: ['label', 'small', 'body', 'title', 'display'] }]
    }
  }
})

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs))
}
