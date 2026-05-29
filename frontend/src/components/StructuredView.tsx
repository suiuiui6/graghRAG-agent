import { useState } from 'react'
import { EntityGroupList } from './EntityGroupList'
import { EntityDetailPanel } from './EntityDetailPanel'

interface GraphData {
  nodes: any[]
  edges: any[]
  stats: {
    total_nodes: number
    total_edges: number
    grounded_nodes: number
    entity_types: Record<string, number>
  }
}

interface StructuredViewProps {
  data: GraphData
  onViewInNetwork?: (nodeId: string) => void
}

export function StructuredView({ data, onViewInNetwork }: StructuredViewProps) {
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedEntity, setSelectedEntity] = useState<any>(null)

  return (
    <div className="w-full h-full flex flex-col">
      {/* Header */}
      <div className="flex-shrink-0 border-b border-border bg-surface/50 px-6 py-4">
        <div className="max-w-[1200px] mx-auto">
          <div className="flex items-center justify-between gap-4 mb-3">
            <div>
              <h2 className="text-xl font-bold">结构化知识图谱</h2>
              <p className="text-text-muted text-xs mt-1">
                {data.stats.total_nodes} 个实体 · {data.stats.total_edges} 条关系 · {Object.keys(data.stats.entity_types).length} 种类型
              </p>
            </div>
            <div className="flex-1 max-w-[400px]">
              <input
                type="text"
                placeholder="🔍 搜索实体..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-elevated border border-border rounded-full py-2 px-4 text-sm text-text-primary focus:outline-none focus:border-accent"
              />
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto px-6 py-6">
        <div className="max-w-[1200px] mx-auto">
          <EntityGroupList
            data={data}
            searchQuery={searchQuery}
            onEntityClick={setSelectedEntity}
          />
        </div>
      </div>

      {/* Detail Panel */}
      {selectedEntity && (
        <EntityDetailPanel
          entity={selectedEntity}
          neighbors={selectedEntity.neighbors || []}
          onClose={() => setSelectedEntity(null)}
          onViewInNetwork={(nodeId) => {
            setSelectedEntity(null)
            onViewInNetwork?.(nodeId)
          }}
        />
      )}
    </div>
  )
}
