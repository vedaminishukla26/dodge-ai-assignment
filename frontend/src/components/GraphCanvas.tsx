import { useState, useEffect, useRef, useCallback } from 'react'
import ForceGraph2D, { type ForceGraphMethods } from 'react-force-graph-2d'

interface GraphNode {
  id: string
  label: string
  name: string
  properties: Record<string, any>
  x?: number
  y?: number
  __highlighted?: boolean
}

interface GraphLink {
  source: string | GraphNode
  target: string | GraphNode
  type: string
}

interface GraphData {
  nodes: GraphNode[]
  links: GraphLink[]
}

interface GraphCanvasProps {
  highlightedNodeIds: string[]
}

const NODE_COLORS: Record<string, string> = {
  SalesOrder: '#6366f1',
  SalesOrderItem: '#818cf8',
  Delivery: '#06b6d4',
  DeliveryItem: '#22d3ee',
  BillingDocument: '#f59e0b',
  BillingDocumentItem: '#fbbf24',
  JournalEntry: '#ef4444',
  Payment: '#34d399',
  Customer: '#ec4899',
  Product: '#a78bfa',
  Plant: '#14b8a6',
}

const NODE_SIZES: Record<string, number> = {
  SalesOrder: 7,
  SalesOrderItem: 4,
  Delivery: 7,
  DeliveryItem: 4,
  BillingDocument: 7,
  BillingDocumentItem: 4,
  JournalEntry: 6,
  Payment: 6,
  Customer: 9,
  Product: 8,
  Plant: 8,
}

const LEGEND_ITEMS = Object.entries(NODE_COLORS).map(([label, color]) => ({
  label,
  color,
}))

export default function GraphCanvas({ highlightedNodeIds }: GraphCanvasProps) {
  const [graphData, setGraphData] = useState<GraphData>({ nodes: [], links: [] })
  const [loading, setLoading] = useState(true)
  const [tooltip, setTooltip] = useState<{
    node: GraphNode | null
    x: number
    y: number
  }>({ node: null, x: 0, y: 0 })
  const graphRef = useRef<ForceGraphMethods>()
  const containerRef = useRef<HTMLDivElement>(null)
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 })

  // Fetch graph data
  useEffect(() => {
    async function fetchGraph() {
      try {
        const res = await fetch('/api/graph/data')
        const data = await res.json()
        setGraphData(data)
      } catch (e) {
        console.error('Failed to fetch graph data:', e)
      } finally {
        setLoading(false)
      }
    }
    fetchGraph()
  }, [])

  // Track container dimensions
  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const observer = new ResizeObserver(entries => {
      for (const entry of entries) {
        setDimensions({
          width: entry.contentRect.width,
          height: entry.contentRect.height,
        })
      }
    })

    observer.observe(container)
    return () => observer.disconnect()
  }, [])

  // Update highlighted nodes
  useEffect(() => {
    if (highlightedNodeIds.length > 0 && graphData.nodes.length > 0) {
      // Find which graph nodes match the highlighted PKs
      const highlightSet = new Set(highlightedNodeIds)

      setGraphData(prev => ({
        ...prev,
        nodes: prev.nodes.map(node => {
          // Check if any property value matches a highlighted ID
          const isHighlighted = Object.values(node.properties).some(
            val => highlightSet.has(String(val))
          )
          return { ...node, __highlighted: isHighlighted }
        }),
      }))
    }
  }, [highlightedNodeIds])

  const handleNodeHover = useCallback(
    (node: any, prevNode: any) => {
      if (node) {
        const canvas = containerRef.current?.querySelector('canvas')
        if (canvas) {
          const rect = canvas.getBoundingClientRect()
          // Use screen coordinates from the graph
          const screenPos = graphRef.current?.graph2ScreenCoords(node.x, node.y)
          if (screenPos) {
            setTooltip({
              node,
              x: rect.left + screenPos.x + 15,
              y: rect.top + screenPos.y - 10,
            })
          }
        }
      } else {
        setTooltip({ node: null, x: 0, y: 0 })
      }
    },
    []
  )

  const handleNodeClick = useCallback(
    async (node: any) => {
      // Fetch neighbors and add to graph
      try {
        const res = await fetch(`/api/graph/node/${encodeURIComponent(node.id)}`)
        const data = await res.json()

        if (data.neighbors && data.neighbors.length > 0) {
          setGraphData(prev => {
            const existingIds = new Set(prev.nodes.map(n => n.id))
            const newNodes = data.neighbors
              .filter((n: any) => !existingIds.has(n.id))
              .map((n: any) => ({
                id: n.id,
                label: n.label,
                name: n.name,
                properties: n.properties,
              }))

            const newLinks: GraphLink[] = data.neighbors
              .map((n: any) => {
                if (n.direction === 'outgoing') {
                  return { source: node.id, target: n.id, type: n.rel_type }
                } else {
                  return { source: n.id, target: node.id, type: n.rel_type }
                }
              })
              // Avoid duplicate links
              .filter((link: GraphLink) => {
                const sourceId = typeof link.source === 'string' ? link.source : link.source.id
                const targetId = typeof link.target === 'string' ? link.target : link.target.id
                return !prev.links.some(existing => {
                  const eSourceId = typeof existing.source === 'string' ? existing.source : (existing.source as GraphNode).id
                  const eTargetId = typeof existing.target === 'string' ? existing.target : (existing.target as GraphNode).id
                  return eSourceId === sourceId && eTargetId === targetId
                })
              })

            return {
              nodes: [...prev.nodes, ...newNodes],
              links: [...prev.links, ...newLinks],
            }
          })
        }
      } catch (e) {
        console.error('Failed to fetch node neighbors:', e)
      }
    },
    []
  )

  const nodeCanvasObject = useCallback(
    (node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const label = node.label || ''
      const color = NODE_COLORS[label] || '#666'
      const size = NODE_SIZES[label] || 5
      const isHighlighted = node.__highlighted

      // Draw glow for highlighted nodes
      if (isHighlighted) {
        const time = Date.now() / 600
        const pulseSize = size + 4 + Math.sin(time) * 3
        ctx.beginPath()
        ctx.arc(node.x, node.y, pulseSize, 0, 2 * Math.PI)
        ctx.fillStyle = `${color}44`
        ctx.fill()

        ctx.beginPath()
        ctx.arc(node.x, node.y, pulseSize + 3, 0, 2 * Math.PI)
        ctx.fillStyle = `${color}22`
        ctx.fill()
      }

      // Draw node
      ctx.beginPath()
      ctx.arc(node.x, node.y, size, 0, 2 * Math.PI)
      ctx.fillStyle = isHighlighted ? '#fff' : color
      ctx.fill()

      if (isHighlighted) {
        ctx.strokeStyle = color
        ctx.lineWidth = 2
        ctx.stroke()
      }

      // Draw label at higher zoom levels
      if (globalScale > 1.2) {
        const displayName = node.name || label
        const truncName = displayName.length > 20 ? displayName.slice(0, 18) + '…' : displayName
        const fontSize = Math.min(12 / globalScale, 4)
        ctx.font = `${fontSize}px Inter, sans-serif`
        ctx.textAlign = 'center'
        ctx.textBaseline = 'top'
        ctx.fillStyle = isHighlighted ? '#fff' : '#9898b0'
        ctx.fillText(truncName, node.x, node.y + size + 2)
      }
    },
    []
  )

  // Reset view handler
  const handleResetView = useCallback(() => {
    if (graphRef.current) {
      graphRef.current.zoomToFit(400, 50)
    }
  }, [])

  // Format property key for display
  const formatKey = (key: string) => {
    return key.replace(/([A-Z])/g, ' $1').replace(/^./, s => s.toUpperCase())
  }

  return (
    <div className="graph-container" ref={containerRef}>
      {/* Header */}
      <div className="graph-header">
        <div className="graph-title">
          <span>🔗</span>
          <span>Knowledge Graph</span>
        </div>
        <div className="graph-stats">
          <button
            className="graph-reset-btn"
            onClick={handleResetView}
            title="Reset View"
          >
            <span>🔄</span> Reset
          </button>
          <span className="stat">
            <span className="stat-dot" style={{ background: '#6366f1' }} />
            {graphData.nodes.length} nodes
          </span>
          <span className="stat">
            <span className="stat-dot" style={{ background: '#34d399' }} />
            {graphData.links.length} relationships
          </span>
        </div>
      </div>

      {/* Loading */}
      {loading && (
        <div className="graph-loading">
          <div className="spinner" />
          <div className="loading-text">Loading knowledge graph…</div>
        </div>
      )}

      {/* Graph */}
      {!loading && (
        <ForceGraph2D
          ref={graphRef as any}
          graphData={graphData}
          width={dimensions.width}
          height={dimensions.height}
          backgroundColor="#0a0a12"
          nodeCanvasObject={nodeCanvasObject}
          nodePointerAreaPaint={(node: any, color, ctx) => {
            const size = NODE_SIZES[node.label] || 5
            ctx.beginPath()
            ctx.arc(node.x, node.y, size + 3, 0, 2 * Math.PI)
            ctx.fillStyle = color
            ctx.fill()
          }}
          linkColor={() => 'rgba(255,255,255,0.1)'}
          linkWidth={1.5}
          linkDirectionalArrowLength={6}
          linkDirectionalArrowRelPos={1}
          linkDirectionalArrowColor={() => 'rgba(255,255,255,0.3)'}
          onNodeHover={handleNodeHover}
          onNodeClick={handleNodeClick}
          cooldownTicks={60}
          d3AlphaDecay={0.04}
          d3VelocityDecay={0.3}
          warmupTicks={40}
          minZoom={0.5}
          maxZoom={10}
          enableZoomInteraction={true}
          enablePanInteraction={true}
        />
      )}

      {/* Tooltip */}
      {tooltip.node && (
        <div
          className="node-tooltip"
          style={{ left: tooltip.x, top: tooltip.y }}
        >
          <div className="tooltip-label">{tooltip.node.label}</div>
          <div className="tooltip-title">{tooltip.node.name}</div>
          <div className="tooltip-props">
            {Object.entries(tooltip.node.properties)
              .slice(0, 8)
              .map(([key, value]) => (
                <div key={key} className="tooltip-prop">
                  <span className="prop-key">{formatKey(key)}</span>
                  <span className="prop-value">{String(value)}</span>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Legend */}
      <div className="graph-legend">
        {LEGEND_ITEMS.map(item => (
          <div key={item.label} className="legend-item">
            <span className="legend-dot" style={{ background: item.color }} />
            {item.label}
          </div>
        ))}
      </div>
    </div>
  )
}
