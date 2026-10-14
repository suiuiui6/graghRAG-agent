import { expect, it } from 'vitest'
import { useAppStore, useUploadStore } from '../src/stores/useAppStore'
it('stores document and user state and transitions stats failure to recovery', () => {
  const s = useAppStore.getState(); s.setDocuments([], 3); s.setStatsError('offline')
  expect(useAppStore.getState()).toMatchObject({ totalDocs: 3, statsLoading: false, statsError: 'offline' })
  s.setStats({ total_docs: 3, total_kg_nodes: 2, total_kg_edges: 1, queries_today: 0 }); s.setUser(null)
  expect(useAppStore.getState()).toMatchObject({ statsError: '', user: null, stats: { total_docs: 3 } })
})
it('upload transitions retain stage progress, completion result and explicit/fallback failures', () => {
  const s = useUploadStore.getState(); s.reset(); s.setFile(new File(['x'], 'a.pdf')); s.startUpload({ task_id: 't', estimated_duration_seconds: 25 } as never)
  expect(useUploadStore.getState()).toMatchObject({ status: 'indexing', taskId: 't', estimatedSeconds: 25 })
  s.updateFromStatus({ status: 'running', progress: { current_step: 2 } } as never)
  expect(useUploadStore.getState().stages.map(s => s.done)).toEqual([true, true, false, false, false])
  s.updateFromStatus({ status: 'done', result: { kg_nodes: 5 } } as never); expect(useUploadStore.getState()).toMatchObject({ status: 'done', result: { kg_nodes: 5 }, currentStage: 0 })
  s.updateFromStatus({ status: 'failed', error: { message: 'bad' } } as never); expect(useUploadStore.getState().error).toBe('bad')
  s.updateFromStatus({ status: 'failed' } as never); expect(useUploadStore.getState().error).toBe('Unknown error')
  s.fail('offline'); expect(useUploadStore.getState().error).toBe('offline'); s.reset(); expect(useUploadStore.getState()).toMatchObject({ file: null, status: 'idle', error: null, result: null })
})
