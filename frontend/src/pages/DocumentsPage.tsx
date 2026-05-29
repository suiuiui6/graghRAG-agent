import { useState, useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { useAppStore } from '../stores/useAppStore'
import { api } from '../lib/api'
import type { DocumentItem } from '../lib/api'
import { ENTITY_TYPES, TYPE_COLORS, TYPE_ICONS } from '../lib/constants'

export function DocumentsPage() {
  const { documents, setDocuments } = useAppStore()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const failCountRef = useRef(0)

  const fetchDocs = () => {
    api.listDocuments()
      .then(data => { setDocuments(data.documents, data.total); setLoading(false); setError(''); failCountRef.current = 0 })
      .catch(e => { setError(e.message); setLoading(false); failCountRef.current++; if (failCountRef.current >= 5) setError('刷新文档列表失败，请手动刷新页面') })
  }

  useEffect(() => { fetchDocs(); const t = setInterval(() => { if (failCountRef.current < 5) fetchDocs() }, 5000); return () => clearInterval(t) }, [])

  const handleDelete = async (docId: string) => {
    try {
      await api.deleteDocument(docId)
      const data = await api.listDocuments()
      setDocuments(data.documents, data.total)
    } catch (e: any) { toast.error(e.message) }
  }

  return (
    <div className="p-8 max-md:p-4">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-[22px] font-extrabold">已索引文档</h2>
          <p className="text-text-muted text-sm mt-1">
            {loading ? '加载中...' : `共 ${documents.length} 篇文档`}
          </p>
        </div>
        <Link to="/upload" className="py-2.5 px-8 bg-accent text-white rounded-full text-sm font-semibold hover:bg-accent-light transition-all">+ 上传新文档</Link>
      </div>

      {error && <div className="p-4 bg-red/5 border border-red/30 rounded-card text-red text-sm mb-4">⚠ {error}</div>}

      {loading ? (
        <div className="text-center py-20 text-text-muted">⏳ 加载中...</div>
      ) : documents.length === 0 ? (
        <div className="text-center py-20">
          <div className="text-5xl mb-4">📭</div>
          <h3 className="text-lg font-semibold mb-2">暂无已索引文档</h3>
          <p className="text-text-muted text-sm mb-4">上传你的第一篇文档开始构建知识图谱</p>
          <Link to="/upload" className="py-2.5 px-10 bg-accent text-white rounded-full text-sm font-semibold">📤 上传文档</Link>
        </div>
      ) : (
        <div className="bg-surface border border-border rounded-card overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="text-left text-[10px] font-bold text-text-muted uppercase tracking-wider border-b border-border">
                <th className="p-3.5 pl-4">文档</th><th className="p-3.5">状态</th><th className="p-3.5">知识图谱</th><th className="p-3.5">页数</th><th className="p-3.5">索引时间</th><th className="p-3.5">操作</th>
              </tr>
            </thead>
            <tbody>
              {documents.map(doc => (
                <tr key={doc.document_id} className="border-b border-border/50 hover:bg-accent/5 transition-colors">
                  <td className="p-3.5 pl-4">
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded-lg bg-elevated flex items-center justify-center text-lg flex-shrink-0">📄</div>
                      <div>
                        <div className="text-sm font-bold">{doc.filename}</div>
                        <div className="text-[11px] text-text-muted">{doc.document_id} · {doc.file_size_mb} MB</div>
                      </div>
                    </div>
                  </td>
                  <td className="p-3.5">
                    <span className={`inline-flex items-center gap-1.5 py-1 px-2.5 rounded-full text-[11px] font-semibold
                      ${doc.status === 'indexed' ? 'bg-green/10 text-green' : 'bg-yellow/10 text-yellow'}`}>
                      <span className={`w-1.5 h-1.5 rounded-full ${doc.status === 'indexed' ? 'bg-green' : 'bg-yellow'}`} />{doc.status === 'indexed' ? '已索引' : doc.status}
                    </span>
                  </td>
                  <td className="p-3.5 text-[13px]">
                    {doc.kg_nodes != null ? <><b className="text-accent">{doc.kg_nodes}</b> 节点 · <b className="text-purple">{doc.kg_edges}</b> 边</> : <span className="text-text-muted">—</span>}
                  </td>
                  <td className="p-3.5 text-sm">{doc.pages ?? '—'}</td>
                  <td className="p-3.5 text-xs text-text-muted">{doc.indexed_at ? new Date(doc.indexed_at).toLocaleString() : '—'}</td>
                  <td className="p-3.5">
                    <div className="flex gap-1.5 flex-wrap">
                      <a href={`/api/v1/documents/${doc.document_id}/download`} className="py-1.5 px-3 border border-border rounded-full text-[11px] text-text-secondary hover:border-accent hover:text-accent transition-all" title="下载">📥</a>
                      <a href={`/api/v1/documents/${doc.document_id}/download`} target="_blank" className="py-1.5 px-3 border border-border rounded-full text-[11px] text-text-secondary hover:border-accent hover:text-accent transition-all" title="预览">👁</a>
                      <Link to={`/query/${doc.document_id}`} className="py-1.5 px-3 border border-border rounded-full text-[11px] text-text-secondary hover:border-accent hover:text-accent transition-all" title="问答">💬</Link>
                      <Link to={`/graph/${doc.document_id}`} className="py-1.5 px-3 border border-border rounded-full text-[11px] text-text-secondary hover:border-accent hover:text-accent transition-all" title="图谱">🔮</Link>
                      <button onClick={() => handleDelete(doc.document_id)} className="py-1.5 px-3 text-[11px] text-red hover:bg-red/10 rounded-full transition-all" title="删除">🗑</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h3 className="text-[11px] font-semibold text-text-muted uppercase tracking-wider mt-6 mb-3">实体类别参考 (示例数据)</h3>
      <div className="flex gap-2 flex-wrap">
        {ENTITY_TYPES.map(e => (
          <div key={e.type} className="flex-1 min-w-[120px] p-3 bg-elevated rounded-lg text-center">
            <div className="text-xl mb-1">{TYPE_ICONS[e.type] || '?'}</div>
            <div className="text-xl font-extrabold" style={{ color: TYPE_COLORS[e.type] }}>{e.count}</div>
            <div className="text-[11px] text-text-muted">{e.type}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
