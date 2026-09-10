import React, { useState } from 'react'
import { Search, Filter, AlertCircle, CheckCircle2, ChevronRight, Building2, Tag } from 'lucide-react'
import { CaseListItem } from '../types'

interface CaseSidebarProps {
  cases: CaseListItem[]
  selectedCaseId: string
  onSelectCase: (caseId: string) => void
  categories: { name: string; count: number }[]
  selectedCategory: string | null
  onSelectCategory: (cat: string | null) => void
}

export const CaseSidebar: React.FC<CaseSidebarProps> = ({
  cases,
  selectedCaseId,
  onSelectCase,
  categories,
  selectedCategory,
  onSelectCategory
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

  return (
    <aside className="w-84 xl:w-96 flex-shrink-0 flex flex-col h-[calc(100vh-65px)] border-r border-white/10 bg-[#0A0E1A]/95 overflow-hidden">
      {/* Top Search & Filter Area */}
      <div className="p-4 border-b border-white/10 space-y-3 bg-slate-900/40">
        {/* Search Bar */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            placeholder="搜索公司、股票代码、处罚文号..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3 py-2 text-xs rounded-lg bg-slate-800/80 border border-white/10 text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-500/60 focus:ring-1 focus:ring-cyan-500/40 font-mono transition-all"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200 text-xs"
            >
              ×
            </button>
          )}
        </div>

        {/* Category Pills (Horizontal scrolling or wrapped) */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-[11px] text-slate-400">
            <span className="flex items-center gap-1 font-medium">
              <Filter className="w-3 h-3 text-cyan-400" />
              <span>舞弊与合规分类 ({categories.length + 1})</span>
            </span>
            <span className="font-mono text-cyan-400/90">{filteredCases.length} 个结果</span>
          </div>

          <div className="flex items-center gap-1.5 overflow-x-auto pb-1.5 scrollbar-none no-scrollbar text-[11px]">
            <button
              onClick={() => onSelectCategory(null)}
              className={`flex-shrink-0 px-2.5 py-1 rounded-md transition-all font-medium ${
                selectedCategory === null
                  ? 'bg-cyan-500 text-black shadow-md shadow-cyan-500/30'
                  : 'bg-slate-800/60 text-slate-400 hover:bg-slate-800 hover:text-slate-200 border border-white/5'
              }`}
            >
              全部 ({cases.length})
            </button>
            {categories.map((cat) => (
              <button
                key={cat.name}
                onClick={() => onSelectCategory(cat.name === selectedCategory ? null : cat.name)}
                className={`flex-shrink-0 px-2.5 py-1 rounded-md transition-all font-medium flex items-center gap-1 ${
                  selectedCategory === cat.name
                    ? 'bg-cyan-500 text-black shadow-md shadow-cyan-500/30'
                    : 'bg-slate-800/60 text-slate-400 hover:bg-slate-800 hover:text-slate-200 border border-white/5'
                }`}
              >
                <span>{cat.name.length > 6 ? cat.name.slice(0, 6) + '...' : cat.name}</span>
                <span className="opacity-70 font-mono">({cat.count})</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Case List View */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2.5">
        {filteredCases.map((c) => {
          const isSelected = c.case_id === selectedCaseId
          return (
            <div
              key={c.case_id}
              onClick={() => onSelectCase(c.case_id)}
              className={`p-3 rounded-xl cursor-pointer transition-all duration-200 border relative group ${
                isSelected
                  ? 'bg-gradient-to-r from-cyan-950/40 via-slate-900/80 to-slate-900/90 border-cyan-500/60 shadow-lg shadow-cyan-500/15 ring-1 ring-cyan-500/30'
                  : 'bg-slate-900/40 hover:bg-slate-800/60 border-white/5 hover:border-white/15'
              }`}
            >
              {/* Active Indicator Line */}
              {isSelected && (
                <span className="absolute left-0 top-3 bottom-3 w-1 bg-gradient-to-b from-cyan-400 to-blue-500 rounded-r" />
              )}

              {/* Header: Company Name & Stock Code */}
              <div className="flex items-start justify-between gap-2 pl-1.5">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs font-mono font-bold text-cyan-400 bg-cyan-950/60 px-1.5 py-0.5 rounded border border-cyan-500/30">
                      {c.stock_code}
                    </span>
                    <h3 className="text-xs font-semibold text-slate-100 truncate group-hover:text-cyan-300 transition-colors">
                      {c.company_name}
                    </h3>
                  </div>
                  <p className="text-[11px] text-slate-400 mt-1 truncate font-mono">
                    {c.penalty_decision_no}
                  </p>
                </div>

                {/* Status Badge */}
                {c.is_clean ? (
                  <span className="flex-shrink-0 flex items-center gap-1 text-[10px] font-semibold text-emerald-400 bg-emerald-950/50 border border-emerald-500/30 px-2 py-0.5 rounded-full">
                    <CheckCircle2 className="w-3 h-3" />
                    合规
                  </span>
                ) : (
                  <span className="flex-shrink-0 flex items-center gap-1 text-[10px] font-semibold text-rose-400 bg-rose-950/50 border border-rose-500/30 px-2 py-0.5 rounded-full">
                    <AlertCircle className="w-3 h-3" />
                    舞弊
                  </span>
                )}
              </div>

              {/* Category and Metrics tags */}
              <div className="flex items-center justify-between text-[10px] text-slate-400 mt-2.5 pt-2 border-t border-white/5 pl-1.5 font-mono">
                <span className="text-slate-300 bg-white/5 px-2 py-0.5 rounded flex items-center gap-1">
                  <Tag className="w-2.5 h-2.5 text-cyan-400" />
                  {c.case_category}
                </span>

                <div className="flex items-center gap-2 text-slate-400">
                  <span>凭证 {c.voucher_count}</span>
                  <span>流水 {c.bank_flow_count}</span>
                </div>
              </div>
            </div>
          )
        })}

        {filteredCases.length === 0 && (
          <div className="text-center py-12 text-slate-500 text-xs">
            未检索到匹配的案例，请尝试重置筛选或更改关键词。
          </div>
        )}
      </div>
    </aside>
  )
}
