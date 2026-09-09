import type { DemoMode, DemoResponse } from './api'

const DEMO_MODES: DemoMode[] = ['offline', 'provider', 'not-run']

export type DemoState =
  | { kind: 'loading' }
  | { kind: 'empty' }
  | { kind: 'success'; demo: DemoResponse }
  | { kind: 'error'; detail: string }

export function describeDemoMode(mode: DemoMode): { label: string; detail: string } {
  switch (mode) {
    case 'offline':
      return { label: 'Offline demo ready', detail: 'Deterministic fixture; no provider was called.' }
    case 'provider':
      return { label: 'Provider result', detail: 'This result was produced with a configured provider.' }
    case 'not-run':
      return { label: 'Provider run not performed', detail: 'No provider execution was observed for this sample.' }
  }
}

function isSupportedDemoMode(value: unknown): value is DemoMode {
  return typeof value === 'string' && DEMO_MODES.includes(value as DemoMode)
}

function isDemoResponse(value: unknown): value is DemoResponse {
  if (!value || typeof value !== 'object') return false
  const demo = value as Record<string, unknown>
  const document = demo.document as Record<string, unknown> | null
  return isSupportedDemoMode(demo.mode)
    && typeof demo.document_id === 'string'
    && !!document
    && typeof document.id === 'string'
    && typeof document.title === 'string'
    && typeof document.text === 'string'
    && Array.isArray(demo.entities)
    && Array.isArray(demo.relations)
    && Array.isArray(demo.sources)
    && typeof demo.answer === 'string'
}

export function mapDemoState(input: {
  loading: boolean
  demo: unknown
  error: unknown
}): DemoState {
  if (input.loading) return { kind: 'loading' }
  if (input.error) {
    const detail = input.error instanceof Error ? input.error.message : String(input.error)
    return { kind: 'error', detail: detail || 'Offline demo is unavailable.' }
  }
  if (!input.demo) return { kind: 'empty' }
  if (!isDemoResponse(input.demo)) {
    const mode = typeof input.demo === 'object' && input.demo !== null
      ? (input.demo as Record<string, unknown>).mode
      : undefined
    if (typeof mode === 'string' && !isSupportedDemoMode(mode)) {
      return { kind: 'error', detail: `Unsupported demo mode: ${mode}.` }
    }
    return { kind: 'error', detail: 'Offline demo payload is invalid.' }
  }
  return { kind: 'success', demo: input.demo }
}
