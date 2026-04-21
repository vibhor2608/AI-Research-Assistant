const BASE_URL = 'https://2a15-54-226-177-158.ngrok-free.app'

const DEFAULT_HEADERS = {
  'ngrok-skip-browser-warning': 'true'
}

const JSON_HEADERS = {
  'Content-Type': 'application/json',
  'ngrok-skip-browser-warning': 'true'
}

export async function fetchPapers(query, limit = 10) {
  const resp = await fetch(
    `${BASE_URL}/papers?q=${encodeURIComponent(query)}&limit=${limit}`,
    {
      method: 'GET',
      headers: DEFAULT_HEADERS,
    }
  )

  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}))
    throw new Error(err.detail || `Failed to fetch papers (${resp.status})`)
  }

  return resp.json()
}

export async function summarizeText(text, title = '') {
  const resp = await fetch(`${BASE_URL}/summarize`, {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify({ text, title }),
  })

  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}))
    throw new Error(err.detail || 'Summarization failed')
  }

  return resp.json()
}

export async function uploadPDF(file) {
  const form = new FormData()
  form.append('file', file)

  const resp = await fetch(`${BASE_URL}/upload-pdf`, {
    method: 'POST',
    headers: DEFAULT_HEADERS,
    body: form,
  })

  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}))
    throw new Error(err.detail || 'PDF upload failed')
  }

  return resp.json()
}

export async function chatWithPaper(question, contextText = '') {
  const resp = await fetch(`${BASE_URL}/chat`, {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify({
      question,
      context_text: contextText,
    }),
  })

  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}))
    throw new Error(err.detail || 'Chat failed')
  }

  return resp.json()
}

export async function getRagStatus() {
  const resp = await fetch(`${BASE_URL}/rag-status`, {
    method: 'GET',
    headers: DEFAULT_HEADERS,
  })

  if (!resp.ok) {
    return {
      index_ready: false,
      chunks: 0,
      sources: [],
    }
  }

  return resp.json()
}
