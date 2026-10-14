import { beforeEach, expect, it, vi } from 'vitest'
import { act, fireEvent, screen } from '@testing-library/react'
import { UploadPage } from '../src/pages/UploadPage'
import { api, type IngestResponse, type StatusResponse } from '../src/lib/api'
import { useUploadStore } from '../src/stores/useAppStore'
import { deferred, mount } from './helpers'

beforeEach(() => { vi.useFakeTimers(); useUploadStore.getState().reset() })
const task = (id: string) => ({ task_id: id, estimated_duration_seconds: 10 } as IngestResponse)
it('ignores an ingest response after leaving without starting a hidden poller', async () => {
  const pending = deferred<IngestResponse>()
  vi.spyOn(api, 'ingest').mockReturnValue(pending.promise)
  const status = vi.spyOn(api, 'getStatus').mockResolvedValue({ status: 'running' } as StatusResponse)
  const view = mount(<UploadPage />)
  fireEvent.change(document.getElementById('fileInput')!, { target: { files: [new File(['x'], 'x.pdf')] } })
  fireEvent.click(screen.getByText('🚀 开始解析文档'))
  view.unmount()
  await act(async () => pending.resolve(task('old')))
  await act(async () => vi.advanceTimersByTimeAsync(6000))
  expect(status).not.toHaveBeenCalled()
  expect(useUploadStore.getState().taskId).toBeNull()
})
it.each(['success', 'error'])('old in-flight poll %s cannot overwrite a replacement task', async mode => {
  const old = deferred<StatusResponse>()
  useUploadStore.getState().startUpload(task('old'))
  const status = vi.spyOn(api, 'getStatus').mockReturnValueOnce(old.promise).mockResolvedValue({ status: 'running', progress: { current_step: 2 } } as StatusResponse)
  mount(<UploadPage />)
  await act(async () => vi.advanceTimersByTimeAsync(2000))
  await act(async () => useUploadStore.getState().startUpload(task('new')))
  await act(async () => mode === 'success' ? old.resolve({ status: 'done', result: { kg_nodes: 999 } } as StatusResponse) : old.reject(new Error('old offline')))
  await act(async () => vi.advanceTimersByTimeAsync(2000))
  expect(useUploadStore.getState().status).toBe('indexing')
  expect(useUploadStore.getState().result).toBeNull()
  expect(status).toHaveBeenLastCalledWith('new')
})

it.each(['success', 'error'])('unmounted in-flight poll %s leaves the shared task resumable', async mode => {
  const pending = deferred<StatusResponse>()
  useUploadStore.getState().startUpload(task('active'))
  const status = vi.spyOn(api, 'getStatus').mockReturnValueOnce(pending.promise).mockResolvedValue({ status: 'running' } as StatusResponse)
  const view = mount(<UploadPage />)
  await act(async () => vi.advanceTimersByTimeAsync(6000))
  expect(status).toHaveBeenCalledTimes(1) // Slow requests do not overlap.
  view.unmount()
  await act(async () => mode === 'success' ? pending.resolve({ status: 'done' } as StatusResponse) : pending.reject(new Error('offline')))
  expect(useUploadStore.getState().status).toBe('indexing')
  await act(async () => vi.advanceTimersByTimeAsync(4000))
  expect(status).toHaveBeenCalledTimes(1)
  mount(<UploadPage />)
  await act(async () => vi.advanceTimersByTimeAsync(2000))
  expect(status).toHaveBeenCalledTimes(2)
  expect(status).toHaveBeenLastCalledWith('active')
})

it.each(['success', 'error'])('reset invalidates old poll %s even before a new upload starts', async mode => {
  const pending = deferred<StatusResponse>()
  useUploadStore.getState().startUpload(task('old'))
  vi.spyOn(api, 'getStatus').mockReturnValue(pending.promise)
  mount(<UploadPage />)
  await act(async () => vi.advanceTimersByTimeAsync(2000))
  await act(async () => useUploadStore.getState().reset())
  await act(async () => mode === 'success' ? pending.resolve({ status: 'failed', error: { message: 'old failure' } } as StatusResponse) : pending.reject(new Error('old offline')))
  expect(useUploadStore.getState().status).toBe('idle')
  expect(useUploadStore.getState().error).toBeNull()
})

it.each(['success', 'error'])('late first ingest %s cannot replace the most recently submitted upload', async mode => {
  const first = deferred<IngestResponse>()
  const second = deferred<IngestResponse>()
  vi.spyOn(api, 'ingest').mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)
  vi.spyOn(api, 'getStatus').mockResolvedValue({ status: 'running' } as StatusResponse)
  mount(<UploadPage />)
  fireEvent.change(document.getElementById('fileInput')!, { target: { files: [new File(['x'], 'x.pdf')] } })
  fireEvent.click(screen.getByText('🚀 开始解析文档'))
  fireEvent.click(screen.getByText('🚀 开始解析文档'))
  await act(async () => second.resolve(task('new')))
  await act(async () => mode === 'success' ? first.resolve(task('old')) : first.reject(new Error('old upload failure')))
  expect(useUploadStore.getState().taskId).toBe('new')
  expect(useUploadStore.getState().error).toBeNull()
})

it('does not fail a replacement file when its previous ingest request rejects', async () => {
  const pending = deferred<IngestResponse>()
  vi.spyOn(api, 'ingest').mockReturnValue(pending.promise)
  mount(<UploadPage />)
  fireEvent.change(document.getElementById('fileInput')!, { target: { files: [new File(['x'], 'first.pdf')] } })
  fireEvent.click(screen.getByText('🚀 开始解析文档'))
  fireEvent.click(screen.getByText('移除'))
  await act(async () => pending.reject(new Error('late upload failure')))
  expect(useUploadStore.getState().status).toBe('idle')
  expect(useUploadStore.getState().error).toBeNull()
})
