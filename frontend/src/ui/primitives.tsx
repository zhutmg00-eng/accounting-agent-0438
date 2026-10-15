import React from 'react'
import { cn } from './cn'

export { cn }

/* ===========================================================================
   AuditMind shared primitives.

   Everything visual in the app composes from these. The rules they encode come
   from DESIGN.md and are not negotiable per-screen:

   * Surfaces are separated by a step in tone. No hairlines, no shadows, no
     glass. `border` is reserved for real data tables and form fields.
   * Square corners. Emphasis comes from scale, weight and tone - not radius.
   * Text meant to be read is 13px or larger; running text is 16px.
   * One accent (seal). Status hues appear only on data marks, never as
     decoration or as a panel background.
   =========================================================================== */

export type Tone = 'critical' | 'high' | 'medium' | 'clear' | 'neutral'

export const toneText: Record<Tone, string> = {
  critical: 'text-risk-critical',
  high: 'text-risk-high',
  medium: 'text-risk-medium',
  clear: 'text-risk-clear',
  neutral: 'text-fg-muted'
}

export const toneFill: Record<Tone, string> = {
  critical: 'bg-risk-critical',
  high: 'bg-risk-high',
  medium: 'bg-risk-medium',
  clear: 'bg-risk-clear',
  neutral: 'bg-fg-faint'
}

/** Map a free-form verdict string from the backend onto a display tone. */
export function toneOfVerdict(verdict: unknown): Tone {
  const v = String(verdict ?? '').toLowerCase()
  if (v.includes('critical') || v.includes('high') || v.includes('fraud') || v.includes('舞弊')) {
    return 'critical'
  }
  if (v.includes('medium') || v.includes('warn') || v.includes('关注')) return 'medium'
  if (v.includes('low')) return 'high'
  if (v.includes('clear') || v.includes('pass') || v.includes('合规') || v.includes('正常')) {
    return 'clear'
  }
  return 'neutral'
}

/* -------------------------------------------------------------------------- */
/* Surfaces                                                                    */
/* -------------------------------------------------------------------------- */

interface SurfaceProps extends React.HTMLAttributes<HTMLDivElement> {
  /** `raised` is a panel; `flat` sits directly on the field. */
  level?: 'flat' | 'raised' | 'raised2'
  /** Paper is the lit artifact: use it where the product shows evidence. */
  paper?: boolean
}

export const Surface: React.FC<SurfaceProps> = ({
  level = 'raised',
  paper = false,
  className,
  children,
  ...rest
}) => (
  <div
    className={cn(
      'rounded-none',
      paper
        ? 'bg-paper text-ink'
        : level === 'flat'
          ? 'bg-transparent'
          : level === 'raised2'
            ? 'bg-field-raised2'
            : 'bg-field-raised',
      className
    )}
    {...rest}
  >
    {children}
  </div>
)

interface PanelHeaderProps {
  title: React.ReactNode
  /** One short sentence under the title. Optional - most panels need none. */
  note?: React.ReactNode
  /** Right-aligned controls, counts or state. */
  meta?: React.ReactNode
  className?: string
}

export const PanelHeader: React.FC<PanelHeaderProps> = ({ title, note, meta, className }) => (
  <div className={cn('flex items-start justify-between gap-6 px-5 pt-5 pb-4', className)}>
    <div className="min-w-0">
      <h2 className="text-title font-semibold text-fg">{title}</h2>
      {note ? <p className="mt-1 max-w-[60ch] text-small text-fg-muted">{note}</p> : null}
    </div>
    {meta ? <div className="flex shrink-0 items-center gap-3 text-small text-fg-muted">{meta}</div> : null}
  </div>
)

interface PanelProps extends Omit<SurfaceProps, 'title'> {
  title?: React.ReactNode
  note?: React.ReactNode
  meta?: React.ReactNode
  /** Drop the inner padding when the panel is a table or a full-bleed view. */
  bare?: boolean
}

export const Panel: React.FC<PanelProps> = ({
  title,
  note,
  meta,
  bare = false,
  className,
  children,
  ...rest
}) => (
  <Surface className={cn('overflow-hidden', className)} {...rest}>
    {title !== undefined ? <PanelHeader title={title} note={note} meta={meta} /> : null}
    <div className={bare ? '' : 'px-5 pb-5'}>{children}</div>
  </Surface>
)

/* -------------------------------------------------------------------------- */
/* Controls                                                                    */
/* -------------------------------------------------------------------------- */

interface BtnProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  /** `primary` is the one accent-filled action on a screen. */
  variant?: 'primary' | 'solid' | 'quiet' | 'ghost'
  size?: 'sm' | 'md' | 'lg'
  icon?: React.ReactNode
}

export const Btn: React.FC<BtnProps> = ({
  variant = 'quiet',
  size = 'md',
  icon,
  className,
  children,
  type = 'button',
  ...rest
}) => (
  <button
    type={type}
    className={cn(
      'press inline-flex items-center justify-center gap-2 rounded-none font-medium',
      'disabled:cursor-not-allowed disabled:opacity-40',
      size === 'sm' && 'min-h-[32px] px-3 text-label',
      size === 'md' && 'min-h-[40px] px-4 text-small',
      size === 'lg' && 'min-h-[48px] px-6 text-body',
      // White, not paper: on #D92B21 paper grey measures 4.2:1 and fails, white
      // measures 4.9:1 and passes. The label on the one accent is the one place
      // the extra half-stop of white is worth the small break from the ramp.
      variant === 'primary' && 'bg-seal text-white hover:bg-seal-deep',
      variant === 'solid' && 'bg-field-raised3 text-fg hover:bg-field-raised2',
      variant === 'quiet' && 'bg-field-raised2 text-fg hover:bg-field-raised3',
      variant === 'ghost' && 'bg-transparent text-fg-muted hover:bg-field-raised hover:text-fg',
      className
    )}
    {...rest}
  >
    {icon}
    {children}
  </button>
)

interface ChipProps extends React.HTMLAttributes<HTMLSpanElement> {
  tone?: Tone
  /** Filled chips carry more weight than outline-free tone steps. */
  filled?: boolean
}

export const Chip: React.FC<ChipProps> = ({
  tone = 'neutral',
  filled = false,
  className,
  children,
  ...rest
}) => (
  <span
    className={cn(
      'inline-flex items-center gap-1.5 rounded-none px-2 py-1 text-label font-medium whitespace-nowrap',
      filled
        ? cn(toneFill[tone], tone === 'neutral' ? 'text-fg' : 'text-field')
        : cn('bg-field-raised2', toneText[tone]),
      className
    )}
    {...rest}
  >
    {children}
  </span>
)

/** A small square data mark. Square, not a pulsing dot. */
export const StatusMark: React.FC<{ tone?: Tone; className?: string }> = ({
  tone = 'neutral',
  className
}) => <span aria-hidden className={cn('inline-block h-2 w-2 shrink-0', toneFill[tone], className)} />

interface StatusProps {
  tone?: Tone
  children: React.ReactNode
  className?: string
}

export const Status: React.FC<StatusProps> = ({ tone = 'neutral', children, className }) => (
  <span className={cn('inline-flex items-center gap-2 text-label font-medium', toneText[tone], className)}>
    <StatusMark tone={tone} />
    {children}
  </span>
)

/* -------------------------------------------------------------------------- */
/* Data                                                                        */
/* -------------------------------------------------------------------------- */

interface DataValueProps {
  label: React.ReactNode
  value: React.ReactNode
  /** Currency units, percentages and other qualifiers. */
  unit?: React.ReactNode
  tone?: Tone
  /** `display` for the single number a screen is about. */
  size?: 'body' | 'title' | 'display'
  className?: string
}

export const DataValue: React.FC<DataValueProps> = ({
  label,
  value,
  unit,
  tone = 'neutral',
  size = 'title',
  className
}) => (
  <div className={cn('min-w-0', className)}>
    <div className="text-label text-fg-muted">{label}</div>
    <div
      className={cn(
        'tabular-nums font-semibold',
        size === 'display' && 'text-display',
        size === 'title' && 'text-title',
        size === 'body' && 'text-body',
        toneText[tone]
      )}
    >
      {value}
      {unit !== undefined ? (
        <span className="ml-1.5 text-small font-medium text-fg-muted">{unit}</span>
      ) : null}
    </div>
  </div>
)

/**
 * A row of figures separated by space and tone, not by card borders.
 * `items` are rendered in a single definition-row so the numbers share one
 * baseline and one left edge per column.
 */
export const StatRow: React.FC<{ children: React.ReactNode; className?: string }> = ({
  children,
  className
}) => (
  <div
    className={cn(
      'grid gap-px bg-field-raised2 sm:grid-cols-2 lg:grid-cols-4 [&>*]:bg-field-raised [&>*]:px-5 [&>*]:py-4',
      className
    )}
  >
    {children}
  </div>
)

/* -------------------------------------------------------------------------- */
/* States                                                                      */
/* -------------------------------------------------------------------------- */

interface EmptyStateProps {
  title: React.ReactNode
  /** Say what to do next in plain language. */
  body?: React.ReactNode
  action?: React.ReactNode
  className?: string
}

export const EmptyState: React.FC<EmptyStateProps> = ({ title, body, action, className }) => (
  <div className={cn('flex flex-col items-start gap-3 px-5 py-10', className)}>
    <h3 className="text-title font-semibold text-fg">{title}</h3>
    {body ? <p className="max-w-[60ch] text-body text-fg-muted">{body}</p> : null}
    {action}
  </div>
)

/**
 * A loading placeholder: a shape matching the content it stands in for, that
 * settles once when it appears and then holds still. No looping pulse.
 */
export const Skeleton: React.FC<{ className?: string }> = ({ className }) => (
  <div
    role="presentation"
    className={cn('animate-sweep rounded-none bg-field-raised2', className)}
  />
)

/** Skeleton shaped like the panel it stands in for, not a spinner. */
export const SkeletonRows: React.FC<{ rows?: number; className?: string }> = ({
  rows = 5,
  className
}) => (
  <div className={cn('space-y-2', className)}>
    {Array.from({ length: rows }).map((_, i) => (
      <Skeleton key={i} className="h-10 w-full" />
    ))}
  </div>
)

interface ErrorNoteProps {
  title: React.ReactNode
  detail?: React.ReactNode
  action?: React.ReactNode
}

/** Inline failure. Plain, specific, no "Oops". */
export const ErrorNote: React.FC<ErrorNoteProps> = ({ title, detail, action }) => (
  <div aria-live="polite" className="bg-field-raised2 px-5 py-4">
    <div className="flex items-center gap-2 text-body font-medium text-risk-critical">
      <StatusMark tone="critical" />
      {title}
    </div>
    {detail ? <p className="mt-2 max-w-[60ch] text-small text-fg-muted">{detail}</p> : null}
    {action ? <div className="mt-3">{action}</div> : null}
  </div>
)

/* -------------------------------------------------------------------------- */
/* The verdict - the lit artifact                                              */
/* -------------------------------------------------------------------------- */

interface VerdictProps {
  /** The conclusion in one plain sentence, e.g. "存在财务操纵迹象". */
  conclusion: React.ReactNode
  /** The number the conclusion rests on. */
  figure?: React.ReactNode
  figureLabel?: React.ReactNode
  tone?: Tone
  /** Supporting context: the rule, threshold or authority it is judged by. */
  basis?: React.ReactNode
  /** The one action this screen offers. */
  action?: React.ReactNode
  className?: string
}

/**
 * The single most important reading on a screen, set on paper. This is the
 * product's idea made literal: in a dark room, the finding is the lit thing.
 */
export const Verdict: React.FC<VerdictProps> = ({
  conclusion,
  figure,
  figureLabel,
  tone = 'neutral',
  basis,
  action,
  className
}) => (
  <div className={cn('bg-paper px-6 py-6 text-ink', className)}>
    <div className="flex flex-wrap items-end justify-between gap-x-8 gap-y-4">
      {/* The sentence is a heading; only `figure` is allowed display size, so a
          screen never carries two competing focal numbers. */}
      <p className="min-w-0 max-w-[32ch] text-title font-semibold text-ink">{conclusion}</p>
      {figure !== undefined ? (
        <div className="text-right">
          {/* The label sits under the number it names, never above it: an
              eyebrow over a heading is the single most over-used device on the
              web, and a caption is simply the more honest position. */}
          <div
            className={cn(
              'tabular-nums text-display font-semibold',
              tone === 'critical' && 'text-risk-critical',
              tone === 'high' && 'text-risk-high',
              tone === 'medium' && 'text-risk-medium',
              tone === 'clear' && 'text-risk-clear',
              tone === 'neutral' && 'text-ink'
            )}
          >
            {figure}
          </div>
          {figureLabel ? (
            <div className="mt-1.5 text-label text-ink-muted">{figureLabel}</div>
          ) : null}
        </div>
      ) : null}
    </div>
    {basis ? (
      <p className="mt-5 max-w-[75ch] bg-paper-deep px-3 py-2.5 text-small text-ink-muted">
        {basis}
      </p>
    ) : null}
    {action ? <div className="mt-5 flex flex-wrap items-center gap-3">{action}</div> : null}
  </div>
)

/* -------------------------------------------------------------------------- */
/* Wide data - a real table keeps its rules                                    */
/* -------------------------------------------------------------------------- */

export const DataTable: React.FC<{ children: React.ReactNode; className?: string }> = ({
  children,
  className
}) => (
  <div className={cn('scroll-x w-full', className)}>
    <table data-ui className="w-full min-w-[720px] border-collapse text-left text-small">
      {children}
    </table>
  </div>
)

/**
 * A real table keeps its rules. The house style exempts genuine tables and
 * form fields from the no-thin-rule rule, because a ruled table is the reading
 * aid, not decoration.
 */
const HEAD_RULE = 'border-b border-white/[0.09]' // taste-skill-ignore real table rule
const CELL_RULE = 'border-b border-white/[0.05]' // taste-skill-ignore real table rule

export const Th: React.FC<React.ThHTMLAttributes<HTMLTableCellElement>> = ({
  className,
  children,
  ...rest
}) => (
  <th
    scope="col"
    className={cn(
      HEAD_RULE,
      'bg-field-raised px-4 py-2.5 text-label font-medium text-fg-muted',
      className
    )}
    {...rest}
  >
    {children}
  </th>
)

export const Td: React.FC<React.TdHTMLAttributes<HTMLTableCellElement>> = ({
  className,
  children,
  ...rest
}) => (
  <td className={cn(CELL_RULE, 'px-4 py-2.5 align-top text-fg', className)} {...rest}>
    {children}
  </td>
)

/** Right-aligned tabular figure cell. */
export const TdNum: React.FC<React.TdHTMLAttributes<HTMLTableCellElement>> = ({
  className,
  children,
  ...rest
}) => (
  <td
    className={cn(CELL_RULE, 'px-4 py-2.5 text-right align-top tabular-nums text-fg', className)}
    {...rest}
  >
    {children}
  </td>
)

/* -------------------------------------------------------------------------- */
/* Re-exports                                                                  */
/* -------------------------------------------------------------------------- */

/**
 * The motion helpers are re-exported here on purpose. There is exactly one
 * place a screen imports its UI from, and `Reveal` lives in `motion` only for
 * file-size reasons, not because it is a different layer. `motion` imports `cn`
 * from `./cn`, so this re-export does not create an import cycle.
 */
export { Reveal, StageRail, useAnimatedNumber, usePrefersReducedMotion } from './motion'
