import { useState, useEffect, useCallback } from 'react'
import {
  Search, BookOpen, Upload, MessageSquare, Loader2,
  Telescope, Zap, FileText, Brain, ChevronRight,
  AlertCircle, RefreshCw, Sparkles, X
} from 'lucide-react'
import PaperCard from './components/PaperCard'
import PDFUploader from './components/PDFUploader'
import RAGChatPanel from './components/RAGChatPanel'
import { fetchPapers, getRagStatus } from './utils/api'
import { getKGStatus, clearKnowledgeGraph } from './utils/kg'
function Modal({ open, title, children, onClose }) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-[#181828] rounded-2xl shadow-xl p-8 max-w-sm w-full border border-white/10">
        <h2 className="font-bold text-lg text-white mb-3">{title}</h2>
        <div className="text-gray-300 text-sm mb-6">{children}</div>
        <button onClick={onClose} className="absolute top-3 right-4 text-gray-500 hover:text-gray-300"><X size={18} /></button>
      </div>
    </div>
  )
}

const TABS = [
  { id: 'discover', label: 'Discover', icon: Telescope },
  { id: 'upload', label: 'Upload PDF', icon: Upload },
  { id: 'chat', label: 'Deep Chat', icon: Brain },
]

const TRENDING = [
  'large language models', 'diffusion models', 'multimodal learning',
  'reinforcement learning', 'graph neural networks', 'protein structure',
]

export default function App() {
  const [activeTab, setActiveTab] = useState('discover')
  const [query, setQuery] = useState('')
  const [papers, setPapers] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [hasSearched, setHasSearched] = useState(false)
  const [ragStatus, setRagStatus] = useState({ index_ready: false, chunks: 0 })

  // Knowledge Graph clear modal state
  const [showKGModal, setShowKGModal] = useState(false)
  const [kgLoading, setKgLoading] = useState(false)
  const [kgError, setKgError] = useState('')

  // On mount, check if KG has data and prompt user
  useEffect(() => {
    let didPrompt = false
    getKGStatus().then(res => {
      if (res.kg_has_data && !didPrompt) {
        setShowKGModal(true)
        didPrompt = true
      }
    })
  }, [])

  // Handler for KG clear modal
  const handleKGClear = async (clear) => {
    setKgError('')
    setKgLoading(true)
    if (clear) {
      try {
        await clearKnowledgeGraph()
        setShowKGModal(false)
      } catch (e) {
        setKgError(e.message || 'Failed to clear knowledge graph')
      }
    } else {
      setShowKGModal(false)
    }
    setKgLoading(false)
  }

  // Poll RAG status
  useEffect(() => {
    const poll = async () => {
      try {
        const status = await getRagStatus()
        setRagStatus(status)
      } catch {}
    }
    poll()
    const interval = setInterval(poll, 8000)
    return () => clearInterval(interval)
  }, [])

  const handleSearch = useCallback(async (q) => {
    const searchQuery = q || query
    if (!searchQuery.trim()) return

    setLoading(true)
    setError('')
    setHasSearched(true)
    setPapers([])

    try {
      const data = await fetchPapers(searchQuery.trim())
      setPapers(data.papers || [])
      if ((data.papers || []).length === 0) {
        setError('No papers found for this query. Try different keywords or a broader topic.')
      }
    } catch (e) {
      setError(e.message || 'Failed to fetch papers. Make sure the backend is running.')
    } finally {
      setLoading(false)
    }
  }, [query])

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') handleSearch()
  }

  const handleTrending = (topic) => {
    setQuery(topic)
    handleSearch(topic)
  }

  return (
    <div className="min-h-screen" style={{ background: 'linear-gradient(135deg, #0a0a0f 0%, #0f0f1a 50%, #0d0a1a 100%)' }}>
      {/* KG Clear Modal */}
      <Modal open={showKGModal} title="Clear Knowledge Graph?" onClose={() => setShowKGModal(false)}>
        <div className="mb-4">
          The knowledge graph database contains data from previous sessions.<br />
          Would you like to <span className="text-red-400 font-semibold">clear all knowledge graph data</span>?
        </div>
        {kgError && <div className="text-red-400 text-xs mb-2">{kgError}</div>}
        <div className="flex gap-3">
          <button
            className="btn-primary bg-red-500/80 hover:bg-red-600/90 text-white px-4 py-2 rounded-lg font-semibold"
            onClick={() => handleKGClear(true)}
            disabled={kgLoading}
          >
            {kgLoading ? 'Clearing...' : 'Yes, Clear All'}
          </button>
          <button
            className="btn-primary bg-gray-700/80 hover:bg-gray-600/90 text-white px-4 py-2 rounded-lg font-semibold"
            onClick={() => handleKGClear(false)}
            disabled={kgLoading}
          >
            No, Keep Data
          </button>
        </div>
      </Modal>
      {/* Background decoration */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-0 left-1/4 w-96 h-96 rounded-full opacity-5"
          style={{ background: 'radial-gradient(circle, #4fc3f7 0%, transparent 70%)', filter: 'blur(60px)' }} />
        <div className="absolute bottom-1/4 right-1/4 w-80 h-80 rounded-full opacity-4"
          style={{ background: 'radial-gradient(circle, #ce93d8 0%, transparent 70%)', filter: 'blur(60px)' }} />
      </div>

      <div className="relative z-10 max-w-5xl mx-auto px-4 py-8">
        {/* Header */}
        <header className="mb-10 text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-blue-400/10 border border-blue-400/20 text-blue-400 text-xs font-mono mb-4">
            <Sparkles size={11} />
            AI-Powered Research Discovery
          </div>
          <h1 className="font-display font-bold text-4xl md:text-5xl text-white mb-3 tracking-tight">
            Research
            <span style={{ background: 'linear-gradient(90deg, #4fc3f7, #ce93d8)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}> Assistant</span>
          </h1>
          <p className="text-gray-500 text-base max-w-lg mx-auto">
            Explore the latest research, simplified for you
          </p>
        </header>

        {/* Tabs */}
        <nav className="flex gap-1 glass rounded-2xl p-1.5 mb-8">
          {TABS.map(tab => {
            const Icon = tab.icon
            const isActive = activeTab === tab.id
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl text-sm font-display font-semibold transition-all duration-200 ${
                  isActive
                    ? 'bg-gradient-to-r from-blue-600/40 to-purple-600/40 text-white border border-white/10'
                    : 'text-gray-500 hover:text-gray-300'
                }`}
              >
                <Icon size={15} />
                <span className="hidden sm:inline">{tab.label}</span>
                {tab.id === 'chat' && ragStatus.index_ready && (
                  <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
                )}
              </button>
            )
          })}
        </nav>

        {/* === DISCOVER TAB === */}
        {activeTab === 'discover' && (
          <div className="space-y-6">
            {/* Search Box */}
            <div className="glass rounded-2xl p-5">
              <div className="flex gap-3">
                <div className="relative flex-1">
                  <Search size={16} className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-600" />
                  <input
                    type="text"
                    value={query}
                    onChange={e => setQuery(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Search research papers… e.g. 'transformer attention'"
                    className="w-full bg-white/5 border border-white/8 rounded-xl pl-11 pr-4 py-3.5
                      text-white placeholder-gray-600 text-sm outline-none
                      focus:border-blue-400/40 focus:bg-white/7 transition-all"
                  />
                  {query && (
                    <button onClick={() => setQuery('')} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-600 hover:text-gray-400">
                      <X size={14} />
                    </button>
                  )}
                </div>
                <button
                  onClick={() => handleSearch()}
                  disabled={loading || !query.trim()}
                  className="btn-primary flex items-center gap-2 px-6 whitespace-nowrap"
                >
                  {loading ? <Loader2 size={15} className="spin" /> : <Search size={15} />}
                  {loading ? 'Searching…' : 'Get Papers'}
                </button>
              </div>

              {/* Trending chips */}
              <div className="mt-4 flex flex-wrap gap-2">
                <span className="text-xs text-gray-600 self-center">Trending:</span>
                {TRENDING.map(topic => (
                  <button
                    key={topic}
                    onClick={() => handleTrending(topic)}
                    className="text-xs px-3 py-1.5 rounded-full bg-white/4 border border-white/8
                      text-gray-400 hover:text-white hover:bg-white/8 hover:border-blue-400/30
                      transition-all font-mono"
                  >
                    {topic}
                  </button>
                ))}
              </div>
            </div>

            {/* Error */}
            {error && !loading && (
              <div className="flex items-start gap-3 bg-red-400/8 border border-red-400/20 rounded-xl px-4 py-3 text-sm text-red-400">
                <AlertCircle size={16} className="shrink-0 mt-0.5" />
                <div>
                  <p>{error}</p>
                  {error.includes('backend') && (
                    <p className="text-xs text-red-500/70 mt-1">
                      Make sure you ran: <code className="font-mono">uvicorn main:app --reload</code> in the backend folder
                    </p>
                  )}
                </div>
              </div>
            )}

            {/* Loading skeletons */}
            {loading && (
              <div className="space-y-4">
                {[1, 2, 3].map(i => (
                  <div key={i} className="glass rounded-2xl p-6 space-y-3">
                    <div className="shimmer-bg h-5 rounded-lg w-3/4" />
                    <div className="shimmer-bg h-3 rounded w-1/3" />
                    <div className="shimmer-bg h-3 rounded w-full" />
                    <div className="shimmer-bg h-3 rounded w-5/6" />
                  </div>
                ))}
              </div>
            )}

            {/* Results */}
            {!loading && papers.length > 0 && (
              <div>
                <div className="flex items-center justify-between mb-4">
                  <p className="text-sm text-gray-500">
                    Found <span className="text-white font-semibold">{papers.length}</span> papers
                    {query && <> for <span className="text-blue-400 font-mono">"{query}"</span></>}
                  </p>
                  <button
                    onClick={() => handleSearch()}
                    className="flex items-center gap-1.5 text-xs text-gray-600 hover:text-gray-400 transition-colors"
                  >
                    <RefreshCw size={11} /> Refresh
                  </button>
                </div>
                <div className="space-y-4">
                  {papers.map((paper, i) => (
                    <PaperCard key={paper.paperId || i} paper={paper} index={i} />
                  ))}
                </div>
              </div>
            )}

            {/* Empty state */}
            {!loading && !hasSearched && (
              <div className="text-center py-16">
                <Telescope size={48} className="text-gray-800 mx-auto mb-4" />
                <p className="text-gray-600 text-sm">Search for a topic to discover the latest research</p>
                <p className="text-gray-700 text-xs mt-1">Results from the last 7 days ·</p>
              </div>
            )}
          </div>
        )}

        {/* === UPLOAD TAB === */}
        {activeTab === 'upload' && (
          <div className="glass rounded-2xl p-6">
            <div className="mb-5">
              <h2 className="font-display font-bold text-xl text-white mb-1">Upload Research Paper</h2>
              <p className="text-sm text-gray-500">
                Upload a PDF to extract text, get AI summary, and enable deep RAG chat
              </p>
            </div>
            <PDFUploader
              onPDFLoaded={(data) => {
                setRagStatus(prev => ({ ...prev, index_ready: true, chunks: Math.ceil(data.full_length / 500) }))
              }}
            />

            {ragStatus.index_ready && (
              <div className="mt-5 p-4 rounded-xl bg-green-400/8 border border-green-400/20">
                <div className="flex items-center gap-2 text-green-400 text-sm font-semibold mb-1">
                  <Brain size={15} />
                  RAG Index is Active
                </div>
                <p className="text-xs text-green-400/60">
                  {ragStatus.chunks} chunks indexed · Switch to Deep Chat tab to ask questions
                </p>
                <button
                  onClick={() => setActiveTab('chat')}
                  className="mt-3 flex items-center gap-1.5 text-xs text-green-400 font-semibold hover:text-green-300 transition-colors"
                >
                  Go to Deep Chat <ChevronRight size={12} />
                </button>
              </div>
            )}
          </div>
        )}

        {/* === CHAT TAB === */}
        {activeTab === 'chat' && (
          <div className="glass rounded-2xl p-6">
            <div className="mb-5">
              <h2 className="font-display font-bold text-xl text-white mb-1">Deep Chat (RAG-Powered)</h2>
              <p className="text-sm text-gray-500">
                {ragStatus.index_ready
                  ? `Ask questions about your uploaded paper. Using ${ragStatus.chunks} indexed chunks.`
                  : 'Upload a PDF first for accurate RAG-based answers. Abstract-only mode is available for searched papers.'}
              </p>
            </div>
            <RAGChatPanel
              ragReady={ragStatus.index_ready}
              chunksCount={ragStatus.chunks}
            />
          </div>
        )}

        {/* Footer */}
        <footer className="mt-12 text-center text-xs text-gray-700 space-y-1">
          <p>Your AI-powered research companion</p>
<p className="font-mono">Search · Understand · Explore · Learn</p>
        </footer>
      </div>
    </div>
  )
}
