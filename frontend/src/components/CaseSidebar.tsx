import React, { useState } from 'react'
import { Search, X } from 'lucide-react'
import { CaseListItem } from '../types'
import { Chip, cn, EmptyState } from '../ui/primitives'
import { Reveal } from '../ui/motion'

interface CaseSidebarProps {
  cases: CaseListItem[]
  selectedCaseId: string
  onSelectCase: (caseId: string) => void
  categories: { name: string; count: number }[]
  selectedCategory: string | null
  onSelectCategory: (cat: string | null) => void
  /** Present when the sidebar is rendered as a drawer below the lg breakpoint. */
  onClose?: () => void
  className?: string
}

/**
 * The case library.
 *
 * The rows carry the facts an auditor picks a case by - stock code, name, the
 * penalty decision it comes from, and how much evidence is attached - so the
 * list can be scanned without opening anything.
 */
export const CaseSidebar: React.FC<CaseSidebarProps> = ({
  cases,
  selectedCaseId,
  onSelectCase,
  categories,
  selectedCategory,
  onSelectCategory,
  onClose,
  className
}) => {
  const [searchQuery, setSearchQuery] = useState('')

  const filteredCases = cases.filter((c) => {
    const matchesCat = !selectedCategory || c.case_category === selectedCategory
    const q = searchQuery.toLowerCase()
    const matchesQuery =
      !searchQuery ||
      c.company_name.toLowerCase().includes(q) ||
      c.stock_code.toLowerCase().includes(q) ||
      c.case_id.toLowerCase().includes(q) ||
      c.penalty_decision_no.toLowerCase().includes(q)
    return matchesCat && matchesQuery
  })

  const filters: { key: string | null; label: string; count: number }[] = [
    { key: null, label: '全部', count: cases.length },
    ...categories.map((cat) => ({ key: cat.name, label: cat.name, count: cat.count }))
  ]

  return (
    <aside
      aria-label="案例库"
      className={cn(
        'flex h-full w-[320px] shrink-0 flex-col bg-field-sunken xl:w-[360px] max-lg:h-auto max-lg:max-h-[40svh] max-lg:w-full max-lg:overflow-y-auto',
        className
      )}
    >
      <div className="shrink-0 space-y-3 px-4 pb-4 pt-4">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-small font-semibold text-fg">案例库</h2>
          <div className="flex items-center gap-2">
            <span className="text-label text-fg-muted tabular-nums">
              {filteredCases.length} / {cases.length}
            </span>
            {onClose ? (
              <button
                type="button"
                onClick={onClose}
                aria-label="关闭案例库"
                className="press flex h-8 w-8 items-center justify-center text-fg-muted hover:bg-field-raised hover:text-fg lg:hidden"
              >
                <X className="h-4 w-4" />
              </button>
            ) : null}
          </div>
        </div>

        <div className="relative">
          <Search
            aria-hidden
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-fg-faint"
          />
          <input
            type="text"
            name="case-search"
            placeholder="搜索公司、代码或处罚文号…"
            aria-label="搜索案例"
            autoComplete="off"
            spellCheck={false}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="h-10 w-full bg-field-raised pl-9 pr-9 text-small text-fg outline-none placeholder:text-fg-faint focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-seal"
          />
          {searchQuery ? (
            <button
              type="button"
              onClick={() => setSearchQuery('')}
              aria-label="清空搜索"
              className="press absolute right-1 top-1/2 flex h-8 w-8 -translate-y-1/2 items-center justify-center text-fg-muted hover:text-fg"
            >
              <X className="h-4 w-4" />
            </button>
          ) : null}
        </div>

        {/* Full category names, no truncation - the strip scrolls instead. */}
        <div className="scroll-x -mx-4 flex gap-1.5 px-4 pb-1">
          {filters.map((f) => {
            const isActive = selectedCategory === f.key
            return (
              <button
                key={f.key ?? '__all__'}
                type="button"
                onClick={() => onSelectCategory(isActive && f.key !== null ? null : f.key)}
                className={cn(
                  'press flex shrink-0 items-center gap-1.5 whitespace-nowrap px-2.5 py-1.5 text-label',
                  isActive
                    ? 'bg-seal font-semibold text-paper'
                    : 'bg-field-raised text-fg-muted hover:bg-field-raised2 hover:text-fg'
                )}
              >
                {f.label}
                <span className={cn('tabular-nums', isActive ? 'text-paper/70' : 'text-fg-faint')}>
                  {f.count}
                </span>
              </button>
            )
          })}
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {filteredCases.length === 0 ? (
          <EmptyState
            title="没有符合条件的案例"
            body="试着换一个关键词，或者点上面的「全部」回到完整案例库。"
            action={
              selectedCategory !== null || searchQuery ? (
                <button
                  type="button"
                  onClick={() => {
                    setSearchQuery('')
                    onSelectCategory(null)
                  }}
                  className="press bg-field-raised px-3 py-2 text-label font-medium text-fg hover:bg-field-raised2"
                >
                  重置筛选
                </button>
              ) : undefined
            }
          />
        ) : (
          <ul className="pb-4">
            {filteredCases.map((c, i) => {
              const isSelected = c.case_id === selectedCaseId
              return (
                <li key={c.case_id}>
                  <Reveal index={Math.min(i, 10)} step={35}>
                    <button
                      type="button"
                      onClick={() => onSelectCase(c.case_id)}
                      aria-current={isSelected ? 'true' : undefined}
                      className={cn(
                        'row-hover block w-full px-4 py-3 text-left',
                        isSelected ? 'bg-field-raised' : 'hover:bg-field-raised/60'
                      )}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex min-w-0 items-baseline gap-2">
                          <span
                            className={cn(
                              'shrink-0 text-label tabular-nums',
                              isSelected ? 'text-seal-soft' : 'text-fg-faint'
                            )}
                          >
                            {c.stock_code}
                          </span>
                          <span className="truncate text-small font-medium text-fg" title={c.company_name}>
                            {c.company_name}
                          </span>
                        </div>
                        <Chip
                          tone={c.is_unlabeled ? 'neutral' : c.is_clean ? 'clear' : 'critical'}
                          className="shrink-0"
                        >
                          {c.is_unlabeled ? '待审' : c.is_clean ? '合规' : '舞弊'}
                        </Chip>
                      </div>

                      <p className="mt-1 truncate text-label text-fg-muted" title={c.penalty_decision_no}>
                        {c.penalty_decision_no}
                      </p>

                      <div className="mt-2 flex items-center justify-between gap-3 text-label text-fg-faint">
                        <span className="truncate" title={c.case_category}>
                          {c.case_category}
                        </span>
                        <span className="shrink-0 tabular-nums">
                          凭证 {c.voucher_count} · 流水 {c.bank_flow_count}
                        </span>
                      </div>
                    </button>
                  </Reveal>
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </aside>
  )
}
