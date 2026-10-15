/**
 * Number formatting for an audit product.
 *
 * Raw `toLocaleString()` on audit figures produces `¥29,944,000,000.00`, which
 * nobody reads at a glance. Auditors work in 亿元 and 万元, so every figure in
 * this app is scaled to the unit a human would say out loud, and the unit is
 * always shown next to the number rather than implied.
 */

const YI = 1e8
const WAN = 1e4

export interface MoneyParts {
  value: string
  unit: string
}

/** Split a yuan amount into a readable figure and its unit. */
export function moneyParts(input: unknown): MoneyParts {
  const n = Number(input)
  if (!Number.isFinite(n)) return { value: '—', unit: '' }
  const abs = Math.abs(n)
  if (abs >= YI) return { value: (n / YI).toFixed(2), unit: '亿元' }
  if (abs >= WAN) return { value: (n / WAN).toFixed(2), unit: '万元' }
  return {
    value: n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
    unit: '元'
  }
}

/** `299.44 亿元` */
export function money(input: unknown): string {
  const { value, unit } = moneyParts(input)
  return unit ? `${value} ${unit}` : value
}

/** `28.6%` — input is a ratio (0.286), which is how the API returns them. */
export function pct(input: unknown, digits = 1): string {
  const n = Number(input)
  if (!Number.isFinite(n)) return '—'
  return `${(n * 100).toFixed(digits)}%`
}

/** Thousands-separated integer, e.g. `29`. */
export function count(input: unknown): string {
  const n = Number(input)
  return Number.isFinite(n) ? n.toLocaleString('zh-CN') : '—'
}

/**
 * Period-over-period change as a ratio, or null when the prior period is
 * missing or zero - in which case the caller should render nothing rather than
 * a fake `+∞%`.
 */
export function growth(current: unknown, prior: unknown): number | null {
  const c = Number(current)
  const p = Number(prior)
  if (!Number.isFinite(c) || !Number.isFinite(p) || p === 0) return null
  return (c - p) / Math.abs(p)
}

/** `+53.8%` / `-12.0%` / `` when there is nothing honest to say. */
export function growthLabel(current: unknown, prior: unknown, digits = 1): string {
  const g = growth(current, prior)
  if (g === null) return ''
  return `${g >= 0 ? '+' : ''}${(g * 100).toFixed(digits)}%`
}

/** Seconds with the precision the report actually carries. */
export function seconds(input: unknown): string {
  const n = Number(input)
  return Number.isFinite(n) ? `${n.toFixed(3)} s` : '—'
}
