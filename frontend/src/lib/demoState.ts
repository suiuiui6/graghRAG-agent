import type { DemoResponse } from './api'

export type DemoState =
  | { kind: 'loading' }
  | { kind: 'empty' }
  | { kind: 'success'; demo: DemoResponse }
  | { kind: 'error'; detail: string }

export function mapDemoState(input: {
  loading: boolean
  demo: DemoResponse | null
  error: unknown
}): DemoState {
  if (input.loading) return { kind: 'loading' }
  if (input.error) {
    const detail = input.error instanceof Error ? input.error.message : String(input.error)
    return { kind: 'error', detail: detail || 'Offline demo is unavailable.' }
  }
  if (!input.demo) return { kind: 'empty' }
  return { kind: 'success', demo: input.demo }
}
