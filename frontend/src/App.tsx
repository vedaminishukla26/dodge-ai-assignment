import { useState, useCallback } from 'react'
import ChatSidebar from './components/ChatSidebar'
import GraphCanvas from './components/GraphCanvas'

export default function App() {
  const [highlightedNodeIds, setHighlightedNodeIds] = useState<string[]>([])

  const handleHighlightNodes = useCallback((nodeIds: string[]) => {
    setHighlightedNodeIds(nodeIds)
  }, [])

  return (
    <div className="app-layout">
      <ChatSidebar onHighlightNodes={handleHighlightNodes} />
      <GraphCanvas highlightedNodeIds={highlightedNodeIds} />
    </div>
  )
}
