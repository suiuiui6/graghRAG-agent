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

function isRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === 'object' && !Array.isArray(value)
}

function isSource(value: unknown): boolean {
  if (!isRecord(value)) return false
  return typeof value.document_id === 'string'
    && typeof value.start === 'number' && Number.isFinite(value.start)
    && typeof value.end === 'number' && Number.isFinite(value.end)
    && typeof value.span === 'string'
}

function isEntity(value: unknown): boolean {
  if (!isRecord(value)) return false
  return typeof value.id === 'string'
    && typeof value.type === 'string'
    // The checked-in fixture calls this display name `label`; accept `name`
    // for compatible fixtures while requiring one of the two identifiers.
    && (typeof value.name === 'string' || typeof value.label === 'string')
}

function isRelation(value: unknown): boolean {
  if (!isRecord(value)) return false
  return typeof value.source === 'string'
    && typeof value.target === 'string'
    && typeof value.type === 'string'
}

function isDemoResponse(value: unknown): value is DemoResponse {
  if (!isRecord(value)) return false
  const demo = value
  const document = demo.document
  return isSupportedDemoMode(demo.mode)
    && typeof demo.document_id === 'string'
    && isRecord(document)
    && typeof document.id === 'string'
    && typeof document.title === 'string'
    && typeof document.text === 'string'
    && Array.isArray(demo.entities)
    && demo.entities.every(isEntity)
    && Array.isArray(demo.relations)
    && demo.relations.every(isRelation)
    && Array.isArray(demo.sources)
    && demo.sources.every(isSource)
    && Array.isArray(demo.questions)
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
