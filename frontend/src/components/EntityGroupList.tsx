import { useState, useMemo } from 'react'
import { TYPE_COLORS, TYPE_ICONS } from '../lib/constants'
import { EntityCard } from './EntityCard'

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

interface EntityGroupListProps {
  data: GraphData
  searchQuery: string
  onEntityClick?: (entity: any) => void
}

interface EntityGroup {
  type: string
  icon: string
  color: string
  count: number
  entities: any[]
}

export function EntityGroupList({ data, searchQuery, onEntityClick }: EntityGroupListProps) {
  // 默认展开前3个类型
  const defaultExpandedTypes = ['paper_metadata', 'claim', 'model_component']
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set(defaultExpandedTypes))

  // 按entity_type分组并过滤
  const entityGroups = useMemo(() => {
    const groups: Record<string, any[]> = {}

    // 构建节点ID到节点的映射
    const nodeMap = new Map(data.nodes.map(n => [n.id, n]))

    // 为每个节点添加neighbors信息
    const nodesWithNeighbors = data.nodes.map(node => {
      const neighbors: any[] = []

      // 查找所有相关的边
      data.edges.forEach(edge => {
        if (edge.from === node.id) {
          const targetNode = nodeMap.get(edge.to)
          if (targetNode) {
            neighbors.push({
              node_id: targetNode.id,
              label: targetNode.label || targetNode.id,
              entity_type: targetNode.entity_type,
              relation: edge.relation || 'connected'
            })
          }
        } else if (edge.to === node.id) {
          const sourceNode = nodeMap.get(edge.from)
          if (sourceNode) {
            neighbors.push({
              node_id: sourceNode.id,
              label: sourceNode.label || sourceNode.id,
              entity_type: sourceNode.entity_type,
              relation: edge.relation || 'connected'
            })
          }
        }
      })

      return { ...node, neighbors }
    })

    // 按类型分组
    nodesWithNeighbors.forEach(node => {
      if (!groups[node.entity_type]) {
        groups[node.entity_type] = []
      }
      groups[node.entity_type].push(node)
    })

    // 转换为数组并排序（按数量降序）
    const groupArray: EntityGroup[] = Object.entries(groups)
      .map(([type, entities]) => ({
        type,
        icon: TYPE_ICONS[type] || '?',
        color: TYPE_COLORS[type] || '#64748b',
        count: entities.length,
        entities
      }))
      .sort((a, b) => b.count - a.count)

    // 应用搜索过滤
    if (searchQuery.trim()) {
      const lowerQuery = searchQuery.toLowerCase()
      return groupArray
        .map(group => ({
          ...group,
          entities: group.entities.filter(e => {
            const labelMatch = e.label?.toLowerCase().includes(lowerQuery)
            const propsMatch = Object.values(e.properties || {}).some(v =>
              String(v).toLowerCase().includes(lowerQuery)
            )
            return labelMatch || propsMatch
          })
        }))
        .filter(group => group.entities.length > 0)
    }

    return groupArray
  }, [data.nodes, data.edges, searchQuery])

  const toggleGroup = (type: string) => {
    setExpandedGroups(prev => {
      const next = new Set(prev)
      if (next.has(type)) {
        next.delete(type)
      } else {
        next.add(type)
      }
      return next
    })
  }

  if (entityGroups.length === 0) {
    return (
      <div className="text-center py-20 text-text-muted">
        <div className="text-5xl mb-3">🔍</div>
        <p>未找到匹配的实体</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {entityGroups.map(group => {
        const isExpanded = expandedGroups.has(group.type)

        return (
          <div key={group.type} className="bg-surface border border-border rounded-card overflow-hidden">
            {/* Group Header */}
            <button
              onClick={() => toggleGroup(group.type)}
              className="w-full px-5 py-3.5 flex items-center gap-3 hover:bg-white/3 transition-colors"
            >
              <div
                className="w-3 h-3 rounded-full flex-shrink-0"
                style={{ backgroundColor: group.color }}
              />
              <span className="text-lg">{group.icon}</span>
              <span className="font-semibold text-sm">{group.type}</span>
              <span className="ml-auto text-xs text-text-muted bg-elevated px-2.5 py-1 rounded-full">
                {group.count}
              </span>
              <span className="text-text-muted text-sm">
                {isExpanded ? '▼' : '▶'}
              </span>
            </button>

            {/* Entity Cards */}
            {isExpanded && (
              <div className="px-5 pb-4 pt-2 grid grid-cols-1 md:grid-cols-2 gap-3">
                {group.entities.map(entity => (
                  <EntityCard
                    key={entity.id}
                    entity={entity}
                    color={group.color}
                    icon={group.icon}
                    onClick={() => onEntityClick?.(entity)}
                  />
                ))}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
