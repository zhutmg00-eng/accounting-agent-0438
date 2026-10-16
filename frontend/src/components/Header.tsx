import React from 'react'
import { ShieldAlert, Menu, UploadCloud } from 'lucide-react'
import { DeepSeekModelsResponse } from '../types'
import { Btn, Chip, cn } from '../ui/primitives'

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
  /** Opens the case drawer below the lg breakpoint. */
  onToggleSidebar?: () => void
}

/** The seven working views, in the order an audit moves through them. */
const TABS = [
  { id: 'cockpit', label: '审计指挥舱' },
  { id: 'agent', label: '智能体工作台' },
  { id: 'reconcile', label: '三单勾稽穿透' },
  { id: 'topology', label: '资金体外拓扑' },
  { id: 'cot', label: '思维链推演台' },
  { id: 'benchmark', label: '28案例竞技场' },
  { id: 'workpapers', label: '底稿与成果导出' }
]

export const Header: React.FC<HeaderProps> = ({
  currentTab,
  setCurrentTab,
  executionMode,
  setExecutionMode,
  onOpenUpload,
  totalCases,
  modelInfo,
  onOpenModelModal,
  onOpenComplianceModal,
  onToggleSidebar
}) => (
  <header className="sticky top-0 z-sticky shrink-0 bg-field-sunken">
    {/* Row 1 - identity and the controls that are not navigation. The tabs get
        their own row so seven Chinese labels never have to wrap into columns. */}
    <div className="flex flex-wrap items-center gap-x-6 gap-y-3 px-4 py-3 sm:px-6">
      <div className="flex min-w-0 items-center gap-3">
        {onToggleSidebar ? (
          <Btn
            variant="ghost"
            size="sm"
            className="lg:hidden"
            aria-label="打开案例库"
            onClick={onToggleSidebar}
          >
            <Menu className="h-4 w-4" />
          </Btn>
        ) : null}

        <span aria-hidden className="h-8 w-[3px] shrink-0 bg-seal" />

        <div className="min-w-0">
          <h1 className="truncate text-body font-semibold tracking-tight text-fg">
            DeepSeek-AuditMind
          </h1>
          <p className="truncate text-label text-fg-muted">
            数智会计创新应用竞赛决赛作品 · 矛与盾团队
          </p>
        </div>
      </div>

      <div className="ml-auto flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={onOpenModelModal}
          className="press flex min-h-[40px] max-w-[240px] items-center gap-2 bg-field-raised px-3 text-label text-fg-muted hover:bg-field-raised2 hover:text-fg"
        >
          <span className="text-fg-faint">模型</span>
          <span className="truncate font-medium text-fg">
            {modelInfo?.active_model || 'deepseek-flash'}
          </span>
        </button>

        <button
          type="button"
          onClick={onOpenComplianceModal}
          title="查看数智会计伦理、合规与数据安全白皮书"
          className="press flex min-h-[40px] items-center gap-2 bg-field-raised px-3 text-label text-fg-muted hover:bg-field-raised2 hover:text-fg"
        >
          <ShieldAlert className="h-4 w-4" />
          <span className="font-medium">伦理合规</span>
        </button>

        <label className="flex min-h-[40px] items-center gap-2 bg-field-raised px-3 text-label">
          <span className="text-fg-faint">运行模式</span>
          <select
            name="execution-mode"
            value={executionMode}
            onChange={(e) => setExecutionMode(e.target.value)}
            aria-label="选择运行模式"
            className="cursor-pointer bg-transparent text-label font-medium text-fg"
          >
            <option value="MOCK" className="bg-field-raised text-fg">
              MOCK 离线确定性引擎
            </option>
            <option value="ONLINE" className="bg-field-raised text-fg">
              ONLINE DeepSeek-V4.1 Flash
            </option>
            <option value="STRICT_ONLINE" className="bg-field-raised text-fg">
              STRICT_ONLINE 严格在线
            </option>
          </select>
        </label>

        <Btn variant="primary" onClick={onOpenUpload} icon={<UploadCloud className="h-4 w-4" />}>
          导入账套
        </Btn>

        <span className="hidden items-center gap-2 px-1 text-label text-fg-muted xl:flex">
          <span className="tabular-nums font-semibold text-fg">{totalCases}</span>
          例真实案例
        </span>
      </div>
    </div>

    {/* Row 2 - the navigation. One flat strip; the active view is the one that
        opens into the workspace tone instead of sitting on the recessed chrome. */}
    <nav
      aria-label="主导航"
      className="scroll-x flex flex-wrap items-stretch gap-px px-4 sm:px-6 lg:flex-nowrap"
    >
      {TABS.map((tab) => {
        const isActive = currentTab === tab.id
        return (
          <button
            key={tab.id}
            type="button"
            onClick={() => setCurrentTab(tab.id)}
            aria-current={isActive ? 'page' : undefined}
            className={cn(
              'press shrink-0 whitespace-nowrap px-4 pb-3 pt-2 text-small',
              isActive
                ? 'bg-field font-semibold text-fg'
                : 'text-fg-muted hover:bg-field-raised hover:text-fg'
            )}
          >
            {tab.label}
          </button>
        )
      })}

      <span className="ml-auto hidden shrink-0 items-center gap-3 pr-1 text-label text-fg-faint lg:flex">
        {modelInfo?.is_mock ? <Chip tone="medium">模拟引擎</Chip> : null}
        {typeof modelInfo?.latency_ms === 'number' ? (
          <span className="tabular-nums">模型探测 {modelInfo.latency_ms} ms</span>
        ) : null}
      </span>
    </nav>
  </header>
)
