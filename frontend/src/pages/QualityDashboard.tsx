import { useState, useEffect } from 'react'
import { api } from '../lib/api'
import type { QualityReport } from '../lib/types'

export function QualityDashboard() {
  const [report, setReport] = useState<QualityReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    api.qualityReport()
      .then(data => { setReport(data); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [])

  if (loading) return <div className="text-center py-20 text-text-muted">⏳ 计算质量指标...</div>
  if (error) return <div className="p-8 text-center text-red">⚠ 加载失败: {error}</div>
  if (!report) return null

  const eq = report.extraction_quality
  const fq = report.feedback_quality
  const df = report.data_freshness

  return (
    <div className="p-8 max-w-[1100px] max-md:p-4">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-[22px] font-extrabold mb-1">数据质量监控</h2>
          <p className="text-text-muted text-sm">生成于 {new Date(report.generated_at).toLocaleString()}</p>
        </div>
        <div className="text-center">
          <div className={`text-4xl font-extrabold ${report.overall_score >= 70 ? 'text-green' : report.overall_score >= 40 ? 'text-amber-400' : 'text-red'}`}>
            {report.overall_score}
          </div>
          <div className="text-[11px] text-text-muted">综合评分 / 100</div>
        </div>
      </div>

      {/* Alerts */}
      {report.alerts.length > 0 && (
        <div className="mb-6 space-y-2">
          {report.alerts.map((a, i) => (
            <div key={i} className={`flex items-center gap-3 p-3 rounded-lg text-xs font-medium ${
              a.severity === 'critical' ? 'bg-red/10 text-red border border-red/20' : 'bg-amber-400/10 text-amber-400 border border-amber-400/20'
            }`}>
              <span>{a.severity === 'critical' ? '🔴' : '🟡'}</span>
              <span>{a.metric}: {typeof a.value === 'number' ? a.value.toFixed(2) : a.value}</span>
              <span className="text-text-muted">阈值: {a.threshold}</span>
            </div>
          ))}
        </div>
      )}

      {/* 4 Quality Dimensions */}
      <div className="grid grid-cols-2 gap-6 max-md:grid-cols-1 mb-6">
        {/* Extraction Quality */}
        <DimensionCard title="📄 抽取质量" score={eq.grounding_rate * 100} target={80}>
          <DimRow label="实体接地率" value={`${(eq.grounding_rate * 100).toFixed(1)}%`} ok={eq.grounding_rate >= 0.5} />
          <DimRow label="平均置信度" value={eq.confidence_avg.toFixed(2)} ok={eq.confidence_avg >= 0.7} />
          <DimRow label="抽取错误率" value={`${(eq.extraction_error_rate * 100).toFixed(1)}%`} ok={eq.extraction_error_rate <= 0.05} />
          <DimRow label="实体总数" value={String(eq.total_entities)} ok={true} />
          <DimRow label="已接地" value={String(eq.grounded_entities)} ok={true} />
        </DimensionCard>

        {/* Feedback Quality */}
        <DimensionCard title="📝 反馈质量" score={fq.positive_ratio * 100} target={70}>
          <DimRow label="好评率" value={`${(fq.positive_ratio * 100).toFixed(1)}%`} ok={fq.positive_ratio >= 0.7} />
          <DimRow label="好评数" value={String(fq.positive)} ok={true} />
          <DimRow label="差评数" value={String(fq.negative)} ok={fq.negative < fq.positive} />
          {fq.negative_clusters.length > 0 && (
            <div className="mt-2 pt-2 border-t border-border/50">
              <div className="text-[10px] text-text-muted mb-1">差评问题聚类:</div>
              {fq.negative_clusters.slice(0, 3).map((q, i) => (
                <div key={i} className="text-[10px] text-red truncate">{q}</div>
              ))}
            </div>
          )}
        </DimensionCard>

        {/* Retrieval Quality */}
        <DimensionCard title="🔍 检索质量" score={60} target={60}>
          <DimRow label="检索路径覆盖" value={String(report.retrieval_quality?.path_covers_avg ?? '--')} ok={true} />
          <DimRow label="零结果查询" value={String(report.retrieval_quality?.zero_result_total ?? 0)} ok={true} />
        </DimensionCard>

        {/* Data Freshness */}
        <DimensionCard title="🕐 数据新鲜度" score={Math.max(0, 100 - df.days_since_last_ingest * 2)} target={80}>
          <DimRow label="距上次索引" value={df.days_since_last_ingest >= 999 ? '从未' : `${df.days_since_last_ingest} 天`}
            ok={df.days_since_last_ingest <= 30} />
          <DimRow label="过期实体" value={String(df.stale_entities)} ok={df.stale_entities < 100} />
          <DimRow label="今日活跃会话" value={String(df.conversation_active_today)} ok={true} />
        </DimensionCard>
      </div>
    </div>
  )
}

function DimensionCard({ title, score, target, children }: {
  title: string; score: number; target: number; children: React.ReactNode
}) {
  const ok = score >= target
  return (
    <div className="bg-surface border border-border rounded-card p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-bold">{title}</h3>
        <div className="flex items-center gap-2">
          <div className={`text-lg font-extrabold ${ok ? 'text-green' : 'text-red'}`}>
            {score.toFixed(0)}
          </div>
          <div className="text-[10px] text-text-muted">/ 目标 {target}</div>
        </div>
      </div>
      <div className="space-y-2">{children}</div>
    </div>
  )
}

function DimRow({ label, value, ok }: { label: string; value: string; ok: boolean }) {
  return (
    <div className="flex justify-between text-xs">
      <span className="text-text-muted">{label}</span>
      <span className={`font-semibold ${ok ? 'text-text-primary' : 'text-red'}`}>{value}</span>
    </div>
  )
}
