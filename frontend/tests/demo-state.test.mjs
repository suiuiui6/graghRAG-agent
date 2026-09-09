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
