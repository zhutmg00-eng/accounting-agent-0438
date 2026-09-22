import React, { useState, useEffect } from 'react'
import { Header } from './components/Header'
import { CaseSidebar } from './components/CaseSidebar'
import { AuditCockpit } from './components/AuditCockpit'
import { ReconciliationVisualizer } from './components/ReconciliationVisualizer'
import { FundTopologyGraph } from './components/FundTopologyGraph'
import { CoTConsole } from './components/CoTConsole'
import { BenchmarkArena } from './components/BenchmarkArena'
import { WorkpaperTable } from './components/WorkpaperTable'
import { CustomUploadModal } from './components/CustomUploadModal'
import { AgentWorkbench } from './components/AgentWorkbench'
import { ModelDetectionModal } from './components/ModelDetectionModal'
import { CaseListItem, AnalysisReportResult, DeepSeekModelsResponse } from './types'

export function App() {
  const [currentTab, setCurrentTab] = useState('cockpit')
  const [executionMode, setExecutionMode] = useState('MOCK')
  const [cases, setCases] = useState<CaseListItem[]>([])
  const [categories, setCategories] = useState<{ name: string; count: number }[]>([])
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
  const [selectedCaseId, setSelectedCaseId] = useState<string>('REAL_CSRC_001')
  const [currentCase, setCurrentCase] = useState<any>(null)

  const [report, setReport] = useState<AnalysisReportResult | null>(null)
  const [isRunning, setIsRunning] = useState(false)
  const [currentStage, setCurrentStage] = useState(1)
  const [stageLogs, setStageLogs] = useState<{ stage: number; title: string; status: string; detail: string }[]>([])
  const [cotStream, setCotStream] = useState('')

  const [isUploadOpen, setIsUploadOpen] = useState(false)
  const [modelInfo, setModelInfo] = useState<DeepSeekModelsResponse | null>(null)
  const [isModelModalOpen, setIsModelModalOpen] = useState(false)

  // Fetch model configuration & auto-detection profile
  const fetchModelInfo = () => {
    fetch('/api/deepseek/models')
      .then((r) => r.json())
      .then((data) => setModelInfo(data))
      .catch((err) => console.error('Failed to load DeepSeek models info', err))
  }

  const handleUpdateConfig = async (modelName: string, apiKey?: string, apiBase?: string) => {
    const resp = await fetch('/api/deepseek/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model_name: modelName,
        api_key: apiKey,
        api_base: apiBase
      })
    })
    if (!resp.ok) {
      const err = await resp.json()
      throw new Error(err.detail || '更新失败')
    }
    fetchModelInfo()
  }

  // 1. Fetch case list, categories, and model info
  useEffect(() => {
    fetchModelInfo()

    fetch('/api/cases')
      .then((r) => r.json())
      .then((data) => {
        const loadedCases: CaseListItem[] = data.cases || []
        const firstBenchmarkIndex = loadedCases.findIndex((item) => item.case_id === 'REAL_CSRC_001')
        const demoLabels = [
          { company_name: '贵州茅台酒股份有限公司', stock_code: '600519' },
          { company_name: '福耀玻璃工业集团股份有限公司', stock_code: '600660' },
          { company_name: '中国移动有限公司', stock_code: '600941' },
        ]
        if (firstBenchmarkIndex >= 3) {
          const firstDemoIndex = firstBenchmarkIndex - demoLabels.length
          demoLabels.forEach((label, offset) => {
            const item = loadedCases[firstDemoIndex + offset]
            if (item) {
              item.company_name = label.company_name
              item.stock_code = label.stock_code
              item.case_category = '真实资本市场合规对照组'
              item.penalty_decision_no = '演示合规账套（非原始监管材料）'
            }
          })
        }
        setCases(loadedCases)
      })
      .catch((err) => console.error('Failed to load cases', err))

    fetch('/api/categories')
      .then((r) => r.json())
      .then((data) => {
        setCategories(data.categories || [])
      })
      .catch((err) => console.error('Failed to load categories', err))
  }, [])

  // 2. Fetch selected case details
  useEffect(() => {
    if (!selectedCaseId) return
    fetch(`/api/cases/${selectedCaseId}`)
      .then((r) => r.json())
      .then((data) => {
        setCurrentCase(data)
        setReport(null)
        setCotStream('')
        setCurrentStage(1)
        setStageLogs([])
      })
      .catch((err) => console.error('Failed to load case detail', err))
  }, [selectedCaseId])

  // 3. Run Intelligent Audit via SSE Stream
  const handleRunAudit = () => {
    if (!selectedCaseId || isRunning) return
    setIsRunning(true)
    setCurrentStage(1)
    setStageLogs([])
    setCotStream('')

    const eventSource = new EventSource(
      `/api/audit/stream?case_id=${encodeURIComponent(selectedCaseId)}&mode=${executionMode}`
    )

    eventSource.onmessage = (event) => {
      if (event.data === '[DONE]') {
        eventSource.close()
        setIsRunning(false)
        return
      }

      try {
        const payload = JSON.parse(event.data)
        if (payload.stage !== undefined) {
          setCurrentStage(payload.stage)
          setStageLogs((prev) => [...prev, payload])
        } else if (payload.type === 'cot_token') {
          setCotStream((prev) => prev + payload.token)
        } else if (payload.type === 'final_report') {
          setReport(payload.report)
          if (payload.report.reasoning_content) {
            setCotStream(payload.report.reasoning_content)
          }
        } else if (payload.type === 'error') {
          console.error(`Audit failed [${payload.code}]`, payload.detail)
          setReport(null)
        }
      } catch (e) {
        console.error('Failed to parse SSE payload', e)
      }
    }

    eventSource.onerror = () => {
      eventSource.close()
      setIsRunning(false)
      // Retry only after a transport failure; server-sent business errors are handled above.
      fetch('/api/audit/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          case_id: selectedCaseId,
          plugin_id: 'audit_fraud_detection',
          mode: executionMode
        })
      })
        .then(async (r) => {
          const data = await r.json()
          if (!r.ok) throw new Error(data.detail || `审计失败 (${r.status})`)
          return data
        })
        .then((data) => {
          setReport(data)
          if (data.reasoning_content) {
            setCotStream(data.reasoning_content)
          }
          setCurrentStage(5)
        })
        .catch((e) => console.error('Fallback audit run failed', e))
    }
  }

  const handleCaseImported = (importedCase: any) => {
    setCurrentCase(importedCase)
    setSelectedCaseId(importedCase.case_id)
    setCases((prev) => [
      {
        case_id: importedCase.case_id,
        company_name: importedCase.company_name,
        stock_code: importedCase.stock_code,
        case_category: '自定义导入账套',
        penalty_decision_no: '实战核查账套',
        audit_period: '2025年度',
        industry: importedCase.industry,
        csrc_summary: '用户现场自定义导入的 Excel 记账凭证及 CSV 对账流水',
        voucher_count: importedCase.vouchers.length,
        invoice_count: importedCase.invoices.length,
        contract_count: importedCase.contracts.length,
        bank_flow_count: importedCase.bank_flows.length,
        ground_truth_count: 0,
        is_clean: false
      },
      ...prev
    ])
  }

  return (
    <div className="min-h-screen flex flex-col bg-[#080C14] bg-grid-pattern text-slate-100">
      {/* Top Header */}
      <Header
        currentTab={currentTab}
        setCurrentTab={setCurrentTab}
        executionMode={executionMode}
        setExecutionMode={setExecutionMode}
        onOpenUpload={() => setIsUploadOpen(true)}
        totalCases={cases.length}
        modelInfo={modelInfo}
        onOpenModelModal={() => setIsModelModalOpen(true)}
      />

      {/* Main Layout Body */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Sidebar */}
        <CaseSidebar
          cases={cases}
          selectedCaseId={selectedCaseId}
          onSelectCase={setSelectedCaseId}
          categories={categories}
          selectedCategory={selectedCategory}
          onSelectCategory={setSelectedCategory}
        />

        {/* Center Workspace Content Area */}
        <main className="flex-1 flex flex-col overflow-hidden bg-slate-950/40">
          {currentTab === 'cockpit' && (
            <AuditCockpit
              currentCase={currentCase}
              report={report}
              isRunning={isRunning}
              onRunAudit={handleRunAudit}
              currentStage={currentStage}
              stageLogs={stageLogs}
            />
          )}

          {currentTab === 'agent' && (
            <AgentWorkbench
              currentCase={currentCase}
              executionMode={executionMode}
              modelInfo={modelInfo}
              onOpenModelModal={() => setIsModelModalOpen(true)}
            />
          )}

          {currentTab === 'reconcile' && (
            <ReconciliationVisualizer
              currentCase={currentCase}
              reconData={report?.tool_outputs?.three_way_reconciliation || null}
            />
          )}

          {currentTab === 'topology' && (
            <FundTopologyGraph currentCase={currentCase} />
          )}

          {currentTab === 'cot' && (
            <CoTConsole
              currentCase={currentCase}
              reasoningContent={cotStream || report?.reasoning_content || ''}
              executionMode={executionMode}
              tokenUsage={report?.token_usage}
              executionTime={report?.execution_time_seconds}
            />
          )}

          {currentTab === 'benchmark' && (
            <BenchmarkArena cases={cases} />
          )}

          {currentTab === 'workpapers' && (
            <WorkpaperTable report={report} currentCase={currentCase} />
          )}
        </main>
      </div>

      {/* Custom Upload Modal */}
      <CustomUploadModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        onCaseImported={handleCaseImported}
      />

      {/* DeepSeek Model Detection & Diagnosis Modal */}
      <ModelDetectionModal
        isOpen={isModelModalOpen}
        onClose={() => setIsModelModalOpen(false)}
        modelInfo={modelInfo}
        onRefreshModels={fetchModelInfo}
        onUpdateConfig={handleUpdateConfig}
      />
    </div>
  )
}

export default App
