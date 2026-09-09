import type { DemoResponse } from '../lib/api'
import { describeDemoMode, mapDemoState, type DemoState as MappedDemoState } from '../lib/demoState'

export { mapDemoState }
export type { MappedDemoState as DemoRenderState }

interface DemoStateProps {
  loading: boolean
  demo: DemoResponse | null
  error: unknown
  onRetry?: () => void
  compact?: boolean
}

export function DemoState({ loading, demo, error, onRetry, compact = false }: DemoStateProps) {
  const state = mapDemoState({ loading, demo, error })
  const shell = compact ? 'p-3' : 'p-5'

  if (state.kind === 'loading') {
    return <div className={`rounded-card border border-border bg-surface ${shell} text-text-muted text-sm`} role="status">
      <span className="inline-block w-3 h-3 mr-2 border-2 border-accent border-t-transparent rounded-full animate-spin align-[-1px]" />
      Loading offline demo…
    </div>
  }

  if (state.kind === 'empty') {
    return <div className={`rounded-card border border-dashed border-border bg-surface ${shell} text-text-muted text-sm`} role="status">
      <div className="font-semibold text-text-secondary mb-1">Offline demo</div>
      No sample is available yet. Try again after starting the backend.
    </div>
  }

  if (state.kind === 'error') {
    return <div className={`rounded-card border border-red/30 bg-red/5 ${shell}`} role="alert">
      <div className="text-red font-semibold text-sm mb-1">Offline demo unavailable</div>
      <div className="text-text-muted text-xs mb-3">{state.detail}</div>
      {onRetry && <button onClick={onRetry} className="py-1.5 px-3 rounded-full bg-accent text-white text-xs hover:bg-accent-light transition-colors">Retry demo</button>}
    </div>
  }

  const mode = describeDemoMode(state.demo.mode)
  return <div className={`rounded-card border border-accent/30 bg-surface ${shell}`}>
    <div className="flex items-center gap-2 mb-2">
      <span className="text-green text-xs font-semibold">● {mode.label}</span>
      <span className="text-text-muted text-[11px]">{state.demo.document.title}</span>
    </div>
    <p className="text-text-muted text-[11px] mb-2">{mode.detail}</p>
    <p className="text-text-primary text-sm leading-relaxed mb-3">{state.demo.answer}</p>
    <div className="flex gap-2 flex-wrap text-[11px] text-text-muted mb-2">
      <span className="py-1 px-2 rounded-full bg-elevated">{state.demo.entities.length} entities</span>
      <span className="py-1 px-2 rounded-full bg-elevated">{state.demo.relations.length} relations</span>
    </div>
    <div className="text-[11px] text-text-muted">
      Sources: {state.demo.sources.length ? state.demo.sources.map(source => source.document_id).join(', ') : 'none'}
    </div>
  </div>
}
