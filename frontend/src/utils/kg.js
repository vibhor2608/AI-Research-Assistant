export async function getKGStatus() {
  const resp = await fetch('https://0454-54-226-177-158.ngrok-free.app/kg-status')
  if (!resp.ok) return { enabled: false, connected: false, kg_has_data: false }
  return resp.json()
}

export async function clearKnowledgeGraph() {
  const resp = await fetch('https://0454-54-226-177-158.ngrok-free.app/kg-all', { method: 'DELETE' })
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to clear knowledge graph')
  }
  return resp.json()
}
