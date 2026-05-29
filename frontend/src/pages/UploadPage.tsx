import { useRef, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useUploadStore } from '../stores/useAppStore'
import { api } from '../lib/api'
import { PIPELINE_STAGES, SUPPORTED_FORMATS } from '../lib/constants'

export function UploadPage() {
  const { file, status, currentStage, stages, result, error, taskId, setFile, startUpload, updateFromStatus, fail, reset } = useUploadStore()
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const navigate = useNavigate()

  // Auto-redirect to documents page when indexing completes (10s delay for user to see results)
  useEffect(() => {
    if (status === 'done') {
      const t = setTimeout(() => navigate('/documents'), 10000)
      return () => clearTimeout(t)
    }
  }, [status, navigate])

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    const f = e.dataTransfer.files[0]
    if (f) setFile(f)
  }

  const pollTask = (taskId: string) => {
    let failCount = 0
    pollingRef.current = setInterval(async () => {
      try {
        const s = await api.getStatus(taskId)
        failCount = 0
        updateFromStatus(s)
        if (s.status === 'done' || s.status === 'failed') {
          if (pollingRef.current) clearInterval(pollingRef.current)
        }
      } catch {
        failCount++
        if (failCount >= 10) {
          if (pollingRef.current) clearInterval(pollingRef.current)
          fail('轮询状态失败，网络可能已断开，请刷新页面重试')
        }
      }
    }, 2000)
  }

  // Resume polling if navigating back while task is still running
  useEffect(() => {
    const taskIdFromStore = useUploadStore.getState().taskId
    const statusFromStore = useUploadStore.getState().status
    if (statusFromStore === 'indexing' && taskIdFromStore) {
      pollTask(taskIdFromStore)
    }
  }, [])

  const handleUrlUpload = async () => {
    const url = (document.getElementById('urlInput') as HTMLInputElement)?.value?.trim()
    if (!url) return
    setFile({ name: url.split('/').pop() || 'document.pdf', size: 0 } as any)
    const fd = new FormData()
    fd.append('url', url)
    fd.append('language', 'en')
    fd.append('enable_formula', 'true')
    fd.append('enable_table', 'true')
    try {
      const resp = await api.ingest(fd)
      startUpload(resp)
      pollTask(resp.task_id)
    } catch (e: any) {
      fail(e.message || 'Upload failed')
    }
  }

  const handleUpload = async () => {
    if (!file) return
    const fd = new FormData()
    fd.append('file', file)
    fd.append('language', 'en')
    fd.append('enable_formula', 'true')
    fd.append('enable_table', 'true')
    try {
      const resp = await api.ingest(fd)
      startUpload(resp)
      pollTask(resp.task_id)
    } catch (e: any) {
      fail(e.message || 'Upload failed')
    }
  }

  return (
    <div className="max-w-[900px] mx-auto p-8 max-md:p-4">
      <div className="text-center mb-8">
        <h1 className="text-[28px] font-extrabold tracking-tight mb-2 bg-gradient-to-r from-text-primary to-accent-light bg-clip-text text-transparent">
          上传文档，构建知识图谱
        </h1>
        <p className="text-text-muted text-sm max-w-[500px] mx-auto">
          支持 {SUPPORTED_FORMATS.length} 种格式 · 自动解析 · 实体抽取 · 知识图谱构建 · 自然语言问答
        </p>
      </div>

      <div
        className={`relative border-2 border-dashed rounded-2xl p-14 text-center cursor-pointer transition-all overflow-hidden
          ${file ? 'border-accent bg-accent/5' : 'border-border hover:border-accent upload-gradient'}`}
        onDrop={handleDrop} onDragOver={e => e.preventDefault()}
        onClick={() => !file && document.getElementById('fileInput')?.click()}
      >
        <div className="w-16 h-16 mx-auto mb-4 bg-accent/8 rounded-2xl flex items-center justify-center text-3xl">
          {file ? '📄' : '📁'}
        </div>
        {file ? (
          <>
            <h3 className="text-lg font-semibold mb-1">{file.name}</h3>
            <p className="text-text-muted text-sm">{(file.size / 1024).toFixed(0)} KB</p>
            <div className="flex justify-center mt-4 gap-2">
              <span className="text-[10px] py-1 px-3 bg-green/10 text-green rounded-full font-semibold">✓ 文件就绪</span>
              <button className="text-[10px] py-1 px-3 bg-elevated rounded-full text-text-muted" onClick={(e) => { e.stopPropagation(); reset() }}>移除</button>
            </div>
          </>
        ) : (
          <>
            <h3 className="text-[17px] font-semibold mb-1">拖拽文件到此处，或点击选择文件</h3>
            <p className="text-text-muted text-sm">单个文件最大 200MB · 最多 600 页</p>
            <div className="flex gap-1.5 justify-center flex-wrap mt-4">
              {SUPPORTED_FORMATS.map(f => (
                <span key={f} className="text-[10px] py-1 px-2.5 bg-elevated rounded-md text-text-muted font-medium tracking-wide">{f}</span>
              ))}
            </div>
          </>
        )}
        <input id="fileInput" type="file" accept=".pdf,.docx,.doc,.pptx,.ppt,.xlsx,.png,.jpg,.jpeg,.epub,.html" className="hidden"
          onChange={e => e.target.files?.[0] && setFile(e.target.files[0])} />
      </div>

      {status === 'idle' && (
        <>
          {file && (
            <div className="text-center mt-7">
              <button onClick={handleUpload}
                className="py-3.5 px-14 bg-accent text-white rounded-full text-[15px] font-semibold transition-all hover:bg-accent-light hover:-translate-y-0.5 hover:shadow-lg hover:shadow-accent/30"
              >🚀 开始解析文档</button>
            </div>
          )}

          {/* URL 输入（备用方式） */}
          <div className="mt-6 p-4 bg-surface/50 border border-border/50 rounded-card">
            <div className="text-[11px] font-semibold text-text-muted uppercase tracking-wider mb-2">⚡ 或使用公网链接（备用方式）</div>
            <div className="flex gap-3">
              <input
                id="urlInput"
                type="url"
                placeholder="https://arxiv.org/pdf/1706.03762v7.pdf"
                className="flex-1 bg-elevated border border-border rounded-full py-2.5 px-4 text-text-primary text-[13px] focus:outline-none focus:border-accent"
              />
              <button onClick={handleUrlUpload}
                className="py-2.5 px-8 bg-surface border border-border text-text-secondary rounded-full text-sm font-semibold hover:border-accent hover:text-accent transition-all flex-shrink-0"
              >解析链接</button>
            </div>
          </div>
        </>
      )}

      {status === 'indexing' && (
        <div className="mt-7">
          <h3 className="text-[11px] font-semibold text-text-muted uppercase tracking-wider mb-4">解析进度</h3>
          <div className="bg-surface border border-border rounded-card p-6">
            <div className="flex gap-0 items-start">
              {stages.map((st, i) => (
                <div key={st.id} className="flex-1 text-center relative">
                  {i < stages.length - 1 && (
                    <div className={`absolute top-[14px] left-[calc(50%+16px)] w-[calc(100%-32px)] h-0.5 ${st.done ? 'bg-green' : 'bg-border'}`} />
                  )}
                  <div className={`w-7 h-7 rounded-full mx-auto mb-2 flex items-center justify-center text-xs font-bold
                    ${st.done ? 'bg-green text-white' : currentStage === st.id ? 'bg-accent text-white animate-pulse-ring' : 'bg-border text-text-muted'}`}>
                    {st.done ? '✓' : st.id}
                  </div>
                  <div className="text-[11px] font-semibold">{PIPELINE_STAGES[i].name}</div>
                  <div className="text-[10px] text-text-muted">{st.done ? '已完成' : '等待中'}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {status === 'done' && result && (
        <div className="mt-7">
          <h3 className="text-[11px] font-semibold text-text-muted uppercase tracking-wider mb-4">解析结果</h3>
          <div className="grid grid-cols-4 gap-3 max-md:grid-cols-2">
            <StatBox val={result.kg_nodes ?? '—'} label="知识图谱节点" sub={`${result.grounded_entities ?? '—'} 已接地`} color="text-accent" />
            <StatBox val={result.kg_edges ?? '—'} label="关系边" sub="3 种关系类型" color="text-purple" />
            <StatBox val={result.entity_types ?? '—'} label="实体类别" sub="metadata·metric·..." color="text-orange" />
            <StatBox val="✅" label="索引完成" sub={`${result.pages_parsed ?? '—'} 页已解析`} color="text-green" />
          </div>
          <p className="text-center text-text-muted text-xs mt-3">10 秒后自动跳转到文档列表</p>
          <div className="flex justify-center gap-3 mt-4">
            <Link to="/documents" className="py-2.5 px-10 bg-accent text-white rounded-full text-sm font-semibold hover:bg-accent-light transition-all">📄 查看文档列表</Link>
            <Link to="/query" className="py-2.5 px-10 border border-border rounded-full text-sm text-text-secondary hover:border-accent hover:text-accent transition-all">💬 知识问答</Link>
            <Link to="/graph" className="py-2.5 px-10 border border-border rounded-full text-sm text-text-secondary hover:border-accent hover:text-accent transition-all">🔮 知识图谱</Link>
            <button onClick={reset} className="py-2.5 px-10 bg-accent text-white rounded-full text-sm font-semibold hover:bg-accent-light transition-all">📤 继续上传</button>
          </div>
        </div>
      )}

      {status === 'failed' && (
        <div className="mt-7 p-6 bg-red/5 border border-red/30 rounded-card text-center">
          <p className="text-red font-semibold mb-2">解析失败</p>
          <p className="text-text-muted text-sm mb-3">{error}</p>
          <div className="flex justify-center gap-3">
            <button onClick={reset} className="py-2 px-6 bg-accent text-white rounded-full text-sm font-semibold">重试</button>
            <button onClick={reset} className="py-2 px-6 border border-border rounded-full text-sm text-text-secondary hover:border-accent hover:text-accent transition-all">上传其他文件</button>
          </div>
        </div>
      )}
    </div>
  )
}

function StatBox({ val, label, sub, color }: { val: string | number; label: string; sub: string; color: string }) {
  return (
    <div className="bg-surface border border-border rounded-card p-5">
      <div className={`text-[30px] font-extrabold tracking-tight ${color}`}>{val}</div>
      <div className="text-[11px] text-text-muted uppercase tracking-wider mt-1">{label}</div>
      <div className="text-[10px] text-text-muted mt-2">{sub}</div>
    </div>
  )
}
