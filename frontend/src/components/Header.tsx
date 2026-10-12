import React from 'react'
import {
  ShieldAlert,
  Cpu,
  Database,
  Award,
  UploadCloud,
  Layers,
  Activity,
  FileSpreadsheet,
  Network,
  Terminal,
  Bot,
  Sparkles
} from 'lucide-react'
import { DeepSeekModelsResponse } from '../types'

interface HeaderProps {
  currentTab: string
  setCurrentTab: (tab: string) => void
  executionMode: string
  setExecutionMode: (mode: string) => void
  onOpenUpload: () => void
  totalCases: number
  modelInfo?: DeepSeekModelsResponse | null
  onOpenModelModal?: () => void
  onOpenComplianceModal?: () => void
}

export const Header: React.FC<HeaderProps> = ({
  currentTab,
  setCurrentTab,
  executionMode,
  setExecutionMode,
  onOpenUpload,
  totalCases,
  modelInfo,
  onOpenModelModal,
  onOpenComplianceModal
}) => {
  const tabs = [
    { id: 'cockpit', label: '审计指挥舱', icon: Activity },
    { id: 'agent', label: '智能体工作台', icon: Bot },
    { id: 'reconcile', label: '三单勾稽穿透', icon: Layers },
    { id: 'topology', label: '资金体外拓扑', icon: Network },
    { id: 'cot', label: '思维链推演台', icon: Terminal },
    { id: 'benchmark', label: '28案例竞技场', icon: Award },
    { id: 'workpapers', label: '底稿与成果导出', icon: FileSpreadsheet },
  ]

  return (
    <header className="sticky top-0 z-50 backdrop-blur-xl bg-[#090D16]/90 border-b border-slate-800 px-6 py-2.5 transition-all">
      <div className="max-w-[1720px] mx-auto flex items-center justify-between gap-4">
        {/* Brand & Competition Info */}
        <div className="flex items-center gap-3.5">
          <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-blue-600/10 border border-blue-500/30 text-blue-400">
            <ShieldAlert className="w-5 h-5" />
          </div>

          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-base font-bold tracking-tight text-white font-mono">
                DeepSeek-AuditMind
              </h1>
              <span className="px-1.5 py-0.2 text-[10px] font-semibold tracking-wider rounded bg-blue-500/10 text-blue-300 border border-blue-500/30 font-mono">
                PRO 2.0
              </span>
            </div>
            <p className="text-[11px] text-slate-400 flex items-center gap-2">
              <span>数智会计创新应用竞赛决赛作品</span>
              <span className="text-slate-600">·</span>
              <span className="text-slate-300 font-mono">矛与盾团队</span>
            </p>
          </div>
        </div>

        {/* Center Tabs Navigation */}
        <nav className="flex items-center gap-1 bg-slate-900/90 p-1 rounded-xl border border-slate-800">
          {tabs.map((tab) => {
            const Icon = tab.icon
            const isActive = currentTab === tab.id
            return (
              <button
                key={tab.id}
                onClick={() => setCurrentTab(tab.id)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                  isActive
                    ? 'text-white bg-slate-800 border border-slate-700 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                }`}
              >
                <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-blue-400' : 'text-slate-500'}`} />
                <span>{tab.label}</span>
              </button>
            )
          })}
        </nav>

        {/* Right Controls: Mode Selector & Upload */}
        <div className="flex items-center gap-3">
          {/* DeepSeek Model Detection Badge */}
          <button
            onClick={onOpenModelModal}
            className="flex items-center gap-1.5 bg-slate-800/80 hover:bg-slate-800 px-2.5 py-1.5 rounded-lg border border-slate-700 text-xs text-slate-300 transition-colors cursor-pointer"
          >
            <Sparkles className="w-3.5 h-3.5 text-blue-400" />
            <span className="font-mono text-slate-200 font-medium truncate max-w-[130px]">
              {modelInfo?.active_model || 'deepseek-v4.1-flash'}
            </span>
            <span className="hidden md:inline px-1 py-0.2 text-[9px] font-mono rounded bg-slate-900 text-slate-400 border border-slate-700">
              自适应
            </span>
          </button>

          {/* Ethics & Compliance Button */}
          <button
            onClick={onOpenComplianceModal}
            title="点击查看数智会计伦理、合规与数据安全白皮书"
            className="flex items-center gap-1.5 bg-slate-800/80 hover:bg-slate-800 px-2.5 py-1.5 rounded-lg border border-slate-700 text-xs text-slate-300 transition-colors cursor-pointer"
          >
            <ShieldAlert className="w-3.5 h-3.5 text-emerald-400" />
            <span className="font-medium">伦理合规</span>
          </button>

          {/* Mode Switcher */}
          <div className="flex items-center gap-1.5 bg-slate-800/80 px-2.5 py-1.5 rounded-lg border border-slate-700 text-xs">
            <Cpu className="w-3.5 h-3.5 text-purple-400" />
            <span className="text-slate-400">运行模式:</span>
            <select
              value={executionMode}
              onChange={(e) => setExecutionMode(e.target.value)}
              aria-label="选择运行模式"
              className="bg-transparent text-slate-200 font-mono font-medium focus:outline-none cursor-pointer text-xs"
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
            className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-medium bg-blue-600 hover:bg-blue-500 text-white transition-colors border border-blue-500 shadow-sm"
          >
            <UploadCloud className="w-4 h-4" />
            <span>导入账套</span>
          </button>

          {/* Database Counter Badge */}
          <div className="hidden xl:flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-slate-800/60 border border-slate-700/60 text-slate-300 text-xs font-mono">
            <Database className="w-3.5 h-3.5" />
            <span>全量真实案例: {totalCases} 例</span>
          </div>
        </div>
      </div>
    </header>
  )
}
