import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import ts from 'typescript'

const testDirectory = path.dirname(fileURLToPath(import.meta.url))
const modulePath = path.resolve(testDirectory, '../src/lib/demoState.ts')

async function loadDemoStateModule() {
  assert.ok(existsSync(modulePath), 'the pure demo-state module must exist')
  const source = readFileSync(modulePath, 'utf8')
  const compiled = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 },
  }).outputText
  return import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`)
}

test('maps exactly loading, empty, success, and error demo states without losing evidence', async () => {
  const { mapDemoState } = await loadDemoStateModule()
  const sources = [{
    document_id: 'sample-handbook',
    page: 1,
    span: 'A release candidate must pass the offline smoke check before publication.',
    entity_ids: ['entity-release-candidate'],
  }]
  const demo = {
    mode: 'offline',
    document_id: 'sample-handbook',
    document: { id: 'sample-handbook', title: 'Sample Engineering Handbook', text: 'source text' },
    entities: [{ id: 'entity-release-candidate', type: 'concept', label: 'release candidate', grounding_status: 'grounded' }],
    relations: [{ source: 'entity-release-candidate', target: 'entity-offline-smoke-check', type: 'must-pass' }],
    questions: ['What must a release candidate pass before publication?'],
    answer: 'A release candidate must pass the offline smoke check before publication.',
    sources,
  }

  const states = [
    mapDemoState({ loading: true, demo: null, error: null }),
    mapDemoState({ loading: false, demo: null, error: null }),
    mapDemoState({ loading: false, demo, error: null }),
    mapDemoState({ loading: false, demo: null, error: new Error('Offline demo fixture is unavailable.') }),
  ]

  assert.deepEqual(states.map(state => state.kind), ['loading', 'empty', 'success', 'error'])
  assert.equal(states[3].detail, 'Offline demo fixture is unavailable.')
  assert.equal(states[2].demo.answer, demo.answer)
  assert.strictEqual(states[2].demo.sources, sources)
})

test('distinguishes supported demo modes and rejects unknown modes', async () => {
  const { describeDemoMode, mapDemoState } = await loadDemoStateModule()
  const baseDemo = {
    document_id: 'sample-handbook',
    document: { id: 'sample-handbook', title: 'Sample Engineering Handbook', text: 'source text' },
    entities: [],
    relations: [],
    questions: [],
    answer: 'A grounded answer.',
    sources: [],
  }

  const offline = mapDemoState({ loading: false, demo: { ...baseDemo, mode: 'offline' }, error: null })
  const provider = mapDemoState({ loading: false, demo: { ...baseDemo, mode: 'provider' }, error: null })
  const notRun = mapDemoState({ loading: false, demo: { ...baseDemo, mode: 'not-run' }, error: null })
  const unknown = mapDemoState({ loading: false, demo: { ...baseDemo, mode: 'preview' }, error: null })

  assert.equal(offline.kind, 'success')
  assert.equal(provider.kind, 'success')
  assert.equal(notRun.kind, 'success')
  assert.equal(describeDemoMode('offline').label, 'Offline demo ready')
  assert.equal(describeDemoMode('provider').label, 'Provider result')
  assert.equal(describeDemoMode('not-run').label, 'Provider run not performed')
  assert.deepEqual(unknown, { kind: 'error', detail: 'Unsupported demo mode: preview.' })
})

test('turns malformed demo payloads into visible errors', async () => {
  const { mapDemoState } = await loadDemoStateModule()
  const malformed = {
    mode: 'offline',
    document_id: 'sample-handbook',
    document: { id: 'sample-handbook', title: 'Sample Engineering Handbook' },
    entities: {},
    relations: [],
    questions: [],
    answer: null,
    sources: 'not-an-array',
  }

  assert.deepEqual(
    mapDemoState({ loading: false, demo: malformed, error: null }),
    { kind: 'error', detail: 'Offline demo payload is invalid.' },
  )
})
