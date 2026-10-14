import { create } from 'zustand'
import type { IngestResponse, StatusResponse, DocumentItem } from '../lib/api'
import type { SystemStats } from '../lib/types'

export interface UserInfo {
  user_id: string; username: string; email: string; display_name: string;
  roles: string[]; department: string | null; last_login: string | null;
}

interface AppState {
  documents: DocumentItem[]
  totalDocs: number
  stats: SystemStats | null
  statsLoading: boolean
  statsError: string
  user: UserInfo | null
  setDocuments: (docs: DocumentItem[], total: number) => void
  setStats: (stats: SystemStats) => void
  setStatsError: (err: string) => void
  setUser: (user: UserInfo | null) => void
}

export const useAppStore = create<AppState>((set) => ({
  documents: [],
  totalDocs: 0,
  stats: null,
  statsLoading: true,
  statsError: '',
  user: null,
  setDocuments: (docs, total) => set({ documents: docs, totalDocs: total }),
  setStats: (stats) => set({ stats, statsLoading: false, statsError: '' }),
  setStatsError: (err) => set({ statsError: err, statsLoading: false }),
  setUser: (user) => set({ user }),
}))

// Upload store — drives real pipeline
interface UploadState {
  file: File | null; taskId: string | null; status: 'idle' | 'uploading' | 'indexing' | 'done' | 'failed'
  currentStage: number; stages: { id: number; done: boolean }[]
  result: StatusResponse['result'] | null; error: string | null; estimatedSeconds: number

  setFile: (f: File | null) => void
  startUpload: (resp: IngestResponse) => void
  updateFromStatus: (resp: StatusResponse) => void
  fail: (err: string) => void
  reset: () => void
}

export const useUploadStore = create<UploadState>((set) => ({
  file: null, taskId: null, status: 'idle', currentStage: 0,
  stages: [1, 2, 3, 4, 5].map(id => ({ id, done: false })),
  result: null, error: null, estimatedSeconds: 60,

  setFile: (f) => set({ file: f, status: 'idle', error: null }),
  startUpload: (resp) => set({ status: 'indexing', taskId: resp.task_id, currentStage: 0, estimatedSeconds: resp.estimated_duration_seconds }),
  updateFromStatus: (resp) => {
    const detailMap: Record<string, number> = { mineru: 1, bridge: 2, extraction: 3, grounding: 4, kg_build: 5 }
    const step = resp.progress?.current_step ?? 0
    set(s => ({
      currentStage: step,
      stages: s.stages.map(st => ({ ...st, done: st.id <= step })),
      ...(resp.status === 'done' ? { status: 'done' as const, result: resp.result } : {}),
      ...(resp.status === 'failed' ? { status: 'failed' as const, error: resp.error?.message || 'Unknown error' } : {}),
    }))
  },
  fail: (err) => set({ status: 'failed', error: err }),
  reset: () => set({ file: null, taskId: null, status: 'idle', currentStage: 0,
    stages: [1, 2, 3, 4, 5].map(id => ({ id, done: false })), result: null, error: null }),
}))
