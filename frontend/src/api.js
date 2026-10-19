// FastAPI 백엔드 호출. 같은 출처의 /api 로 보내고, 개발 서버·nginx 가 백엔드로 넘겨 준다.

async function request(path, options = {}) {
  const res = await fetch(`/api${path}`, options)
  if (!res.ok) {
    let message = `요청에 실패했습니다 (${res.status})`
    try {
      const body = await res.json()
      if (typeof body.detail === 'string') message = body.detail
      else if (Array.isArray(body.detail)) message = body.detail.map((d) => d.msg).join(', ')
    } catch {
      /* 본문이 JSON이 아니면 기본 메시지 */
    }
    throw new Error(message)
  }
  if (res.status === 204) return null
  return res.json()
}

const json = (method, body) => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

function query(params = {}) {
  const q = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) if (v !== '' && v != null) q.set(k, v)
  const s = q.toString()
  return s ? `?${s}` : ''
}

export const api = {
  meta: () => request('/meta'),
  vendors: () => request('/vendors'),
  upload(files, docType) {
    const form = new FormData()
    for (const f of files) form.append('files', f)
    if (docType) form.append('doc_type', docType)
    return request('/documents', { method: 'POST', body: form })
  },
  list: (params) => request(`/documents${query(params)}`),
  get: (id) => request(`/documents/${id}`),
  update: (id, data) => request(`/documents/${id}`, json('PUT', data)),
  confirm: (id) => request(`/documents/${id}/confirm`, { method: 'POST' }),
  unconfirm: (id) => request(`/documents/${id}/unconfirm`, { method: 'POST' }),
  remove: (id) => request(`/documents/${id}`, { method: 'DELETE' }),
  summary: (params) => request(`/summary${query(params)}`),
  journal: (params) => request(`/journal${query(params)}`),
  excelUrl: (params) => `/api/export/excel${query(params)}`,
}
