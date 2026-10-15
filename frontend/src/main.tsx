import React, { Component, ErrorInfo, ReactNode } from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import './index.css'

interface Props {
  children?: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null
  }

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Uncaught error in AuditMind React Component:', error, errorInfo)
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-dvh flex-col items-center justify-center bg-field p-6 text-center">
          <div className="w-full max-w-lg space-y-4 bg-field-raised p-6">
            <div className="flex h-12 w-12 items-center justify-center bg-risk-critical/15 text-title font-semibold text-risk-critical">
              !
            </div>
            <h1 className="text-title font-semibold text-fg">界面渲染捕获异常</h1>
            <pre className="max-h-64 max-w-[70ch] overflow-auto whitespace-pre-wrap break-words bg-field-sunken p-3 text-left text-small text-fg-muted">
              {this.state.error?.message || '未知渲染错误'}
            </pre>
            <button
              onClick={() => {
                this.setState({ hasError: false, error: null })
                window.location.reload()
              }}
              className="press min-h-[40px] w-full bg-seal px-4 text-body font-medium text-paper transition-colors duration-150 hover:bg-seal-deep"
            >
              刷新并恢复页面
            </button>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>,
)
