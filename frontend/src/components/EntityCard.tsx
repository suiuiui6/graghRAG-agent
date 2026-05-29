interface EntityCardProps {
  entity: any
  color: string
  icon: string
  onClick?: () => void
}

export function EntityCard({ entity, color, icon, onClick }: EntityCardProps) {
  return (
    <div
      onClick={onClick}
      className="bg-elevated border border-border rounded-lg p-4 hover:border-accent/50 transition-all cursor-pointer group"
      style={{ borderLeftWidth: '3px', borderLeftColor: color }}
    >
      {/* Header */}
      <div className="flex items-start gap-2 mb-2">
        <span className="text-base flex-shrink-0">{icon}</span>
        <div className="flex-1 min-w-0">
          <h4 className="font-semibold text-sm text-text-primary truncate group-hover:text-accent transition-colors">
            {entity.label || entity.id}
          </h4>
          <p className="text-[10px] text-text-muted uppercase tracking-wider mt-0.5">
            {entity.entity_type}
          </p>
        </div>
      </div>

      {/* Properties */}
      {entity.properties && Object.keys(entity.properties).length > 0 && (
        <div className="space-y-1 mb-3">
          {Object.entries(entity.properties).slice(0, 3).map(([key, value]) => (
            <div key={key} className="flex justify-between text-xs">
              <span className="text-text-muted truncate mr-2">{key}:</span>
              <span className="text-text-secondary font-medium truncate max-w-[60%]">
                {String(value)}
              </span>
            </div>
          ))}
          {Object.keys(entity.properties).length > 3 && (
            <p className="text-[10px] text-text-muted italic">
              +{Object.keys(entity.properties).length - 3} 更多属性
            </p>
          )}
        </div>
      )}

      {/* Footer */}
      <div className="flex items-center gap-2 pt-2 border-t border-border/50">
        {entity.page_idx != null && (
          <span className="text-[10px] px-2 py-0.5 bg-accent/10 text-accent rounded-full">
            📍 Page {entity.page_idx}
          </span>
        )}
        {entity.grounding_status === 'grounded' && (
          <span className="text-[10px] px-2 py-0.5 bg-green/10 text-green rounded-full">
            ✓ 已溯源
          </span>
        )}
      </div>
    </div>
  )
}
