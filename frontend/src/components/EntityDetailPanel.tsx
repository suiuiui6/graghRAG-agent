import { TYPE_COLORS, TYPE_ICONS } from '../lib/constants'

interface Neighbor {
  node_id: string
  label: string
  entity_type: string
  relation: string
}

interface EntityDetailPanelProps {
  entity: any
  neighbors: Neighbor[]
  onClose: () => void
  onViewInNetwork: (nodeId: string) => void
}

export function EntityDetailPanel({ entity, neighbors, onClose, onViewInNetwork }: EntityDetailPanelProps) {
  const color = TYPE_COLORS[entity.entity_type] || '#64748b'
  const icon = TYPE_ICONS[entity.entity_type] || '?'

  return (
    <div className="fixed inset-y-0 right-0 w-[400px] bg-surface border-l border-border shadow-2xl z-50 flex flex-col animate-slide-in">
      {/* Header */}
      <div className="flex-shrink-0 px-5 py-4 border-b border-border">
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-2">
            <div
              className="w-3 h-3 rounded-full flex-shrink-0"
              style={{ backgroundColor: color }}
            />
            <span className="text-lg">{icon}</span>
            <span className="text-xs font-semibold text-text-muted uppercase tracking-wider">
              {entity.entity_type}
            </span>
          </div>
          <button
            onClick={onClose}
            className="text-text-muted hover:text-text-primary transition-colors text-xl leading-none"
          >
            ✕
          </button>
        </div>
        <h3 className="text-base font-bold text-text-primary leading-snug">
          {entity.label || entity.id}
        </h3>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
        {/* Properties */}
        {entity.properties && Object.keys(entity.properties).length > 0 && (
          <div>
            <h4 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2">
              属性
            </h4>
            <div className="space-y-2">
              {Object.entries(entity.properties).map(([key, value]) => (
                <div key={key} className="flex justify-between text-xs border-b border-border/50 pb-2">
                  <span className="text-text-muted">{key}</span>
                  <span className="text-text-primary font-medium text-right max-w-[60%] break-words">
                    {String(value)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Grounding Info */}
        <div>
          <h4 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2">
            溯源信息
          </h4>
          <div className="space-y-2">
            {entity.page_idx != null && (
              <div className="flex justify-between text-xs">
                <span className="text-text-muted">PDF 页码</span>
                <span className="text-accent font-semibold">📍 Page {entity.page_idx}</span>
              </div>
            )}
            {entity.bbox_norm && Array.isArray(entity.bbox_norm) && (
              <div className="flex justify-between text-xs">
                <span className="text-text-muted">包围框</span>
                <span className="text-green font-mono text-[10px]">
                  [{entity.bbox_norm.map((n: number) => Math.round(n)).join(', ')}]
                </span>
              </div>
            )}
            <div className="flex justify-between text-xs">
              <span className="text-text-muted">溯源状态</span>
              <span className={`font-semibold ${entity.grounding_status === 'grounded' ? 'text-green' : 'text-red'}`}>
                {entity.grounding_status === 'grounded' ? '✓ 已溯源' : '✗ 未溯源'}
              </span>
            </div>
          </div>
        </div>

        {/* Relationships */}
        {neighbors.length > 0 && (
          <div>
            <h4 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2">
              关系 ({neighbors.length})
            </h4>
            <div className="space-y-2">
              {neighbors.map((neighbor, idx) => (
                <div
                  key={idx}
                  className="bg-elevated border border-border rounded-lg p-3 text-xs hover:border-accent/50 transition-colors"
                >
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-base">{TYPE_ICONS[neighbor.entity_type] || '?'}</span>
                    <span className="font-semibold text-text-primary truncate">
                      {neighbor.label}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-[10px] text-text-muted">
                    <span className="px-2 py-0.5 bg-accent/10 text-accent rounded-full">
                      {neighbor.relation}
                    </span>
                    <span className="truncate">{neighbor.entity_type}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {neighbors.length === 0 && (
          <div className="text-center py-8 text-text-muted text-xs">
            <div className="text-3xl mb-2">🔗</div>
            <p>暂无关系节点</p>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="flex-shrink-0 px-5 py-4 border-t border-border">
        <button
          onClick={() => onViewInNetwork(entity.id)}
          className="w-full py-2.5 bg-accent text-white rounded-full text-sm font-semibold hover:bg-accent-light transition-all"
        >
          🔮 在网络图谱中查看
        </button>
      </div>
    </div>
  )
}
