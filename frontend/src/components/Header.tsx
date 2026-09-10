import React from 'react'
import { ShieldAlert, Cpu, Database, Award, UploadCloud, Layers, Activity, FileSpreadsheet, Network, Terminal } from 'lucide-react'

interface HeaderProps {
  currentTab: string
  setCurrentTab: (tab: string) => void
  executionMode: string
  setExecutionMode: (mode: string) => void
  onOpenUpload: () => void
  totalCases: number
}

export const Header: React.FC<HeaderProps> = ({
  currentTab,
  setCurrentTab,
  executionMode,
  setExecutionMode,
  onOpenUpload,
  totalCases
}) => {
  const tabs = [
    { id: 'cockpit', label: '审计指挥舱', icon: Activity },
    { id: 'reconcile', label: '三单勾稽穿透', icon: Layers },
    { id: 'topology', label: '资金体外拓扑', icon: Network },
    { id: 'cot', label: '思维链推演台', icon: Terminal },
    { id: 'benchmark', label: '28案例竞技场', icon: Award },
    { id: 'workpapers', label: '底稿与成果导出', icon: FileSpreadsheet },
  ]

  return (
    <header className="sticky top-0 z-50 backdrop-blur-xl bg-[#080C14]/85 border-b border-white/10 px-6 py-3 transition-all">
      <div className="max-w-[1720px] mx-auto flex items-center justify-between gap-4">
        {/* Brand & Competition Info */}
        <div className="flex items-center gap-4">
          <div className="relative flex items-center justify-center w-11 h-11 rounded-xl bg-gradient-to-br from-cyan-500/20 via-blue-600/30 to-purple-600/20 border border-cyan-500/40 shadow-lg shadow-cyan-500/20">
            <ShieldAlert className="w-6 h-6 text-cyan-400 animate-pulse" />
            <span className="absolute -top-1 -right-1 flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-cyan-500"></span>
            </span>
          </div>

          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold tracking-tight bg-gradient-to-r from-white via-slate-100 to-cyan-300 bg-clip-text text-transparent font-mono">
                DeepSeek-AuditMind
              </h1>
              <span className="px-2 py-0.5 text-[11px] font-semibold tracking-wider rounded-md bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 font-mono">
                v2.0 PRO
              </span>
            </div>
            <p className="text-xs text-slate-400 flex items-center gap-2">
              <span>2026年北京市大学生数智会计创新应用竞赛参赛作品</span>
              <span className="text-slate-600">|</span>
              <span className="text-emerald-400/90 font-mono">Cordis 微内核驱动</span>
            </p>
          </div>
        </div>

        {/* Center Tabs Navigation */}
        <nav className="flex items-center gap-1 bg-slate-900/80 p-1.5 rounded-xl border border-white/10 shadow-inner">
          {tabs.map((tab) => {
            const Icon = tab.icon
            const isActive = currentTab === tab.id
            return (
              <button
                key={tab.id}
                onClick={() => setCurrentTab(tab.id)}
                className={`relative flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all duration-200 ${
                  isActive
                    ? 'text-cyan-300 bg-gradient-to-r from-cyan-500/20 to-blue-600/20 border border-cyan-500/40 shadow-md shadow-cyan-500/10'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
                }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? 'text-cyan-400' : 'text-slate-400'}`} />
                <span>{tab.label}</span>
                {isActive && (
                  <span className="absolute bottom-0 left-1/2 -translate-x-1/2 w-1/2 h-[2px] bg-gradient-to-r from-cyan-400 to-blue-500 rounded-full" />
                )}
              </button>
            )
          })}
        </nav>

        {/* Right Controls: Mode Selector & Upload */}
        <div className="flex items-center gap-3">
          {/* Mode Switcher */}
          <div className="flex items-center gap-1.5 bg-slate-900/90 px-3 py-1.5 rounded-lg border border-white/10 text-xs">
            <Cpu className="w-3.5 h-3.5 text-purple-400" />
            <span className="text-slate-400">运行模式:</span>
            <select
              value={executionMode}
              onChange={(e) => setExecutionMode(e.target.value)}
              aria-label="选择运行模式"
              className="bg-transparent text-cyan-300 font-mono font-medium focus:outline-none cursor-pointer"
            >
              <option value="MOCK" className="bg-slate-900 text-slate-200">
                MOCK (离线确定性引擎)
              </option>
              <option value="ONLINE" className="bg-slate-900 text-slate-200">
                ONLINE (DeepSeek-V4.1 Flash 在线)
              </option>
              <option value="STRICT_ONLINE" className="bg-slate-900 text-slate-200">
                STRICT_ONLINE (严格在线)
              </option>
            </select>
          </div>

          {/* Upload Button */}
          <button
            onClick={onOpenUpload}
            className="flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-medium bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500 text-white shadow-lg shadow-cyan-500/20 transition-all active:scale-95 border border-cyan-400/30"
          >
            <UploadCloud className="w-4 h-4" />
            <span>导入账套</span>
          </button>

          {/* Database Counter Badge */}
          <div className="hidden xl:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-mono">
            <Database className="w-3.5 h-3.5" />
            <span>全量真实案例: {totalCases} 例</span>
          </div>
        </div>
      </div>
    </header>
  )
}
