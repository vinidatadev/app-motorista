const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const LOCAL_TOKEN_KEY = 'local_token'

export function saveLocalToken(token) {
  sessionStorage.setItem(LOCAL_TOKEN_KEY, token)
}
export function getLocalToken() {
  return sessionStorage.getItem(LOCAL_TOKEN_KEY)
}
export function clearLocalToken() {
  sessionStorage.removeItem(LOCAL_TOKEN_KEY)
}

export function decodeTokenPayload(token) {
  try {
    const payload = token.split('.')[1]
    return JSON.parse(atob(payload))
  } catch {
    return null
  }
}

export function isTokenValid(token) {
  const payload = decodeTokenPayload(token)
  if (!payload || !payload.exp) return false
  return payload.exp * 1000 > Date.now()
}

function parseError(err) {
  if (Array.isArray(err?.detail)) {
    return err.detail.map(e => e.msg).join(', ')
  }
  return err?.detail || 'Erro desconhecido'
}

async function request(method, path, body = null) {
  const token = getLocalToken()
  const headers = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined
  })

  if (res.status === 204) return null
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Erro desconhecido' }))
    throw new Error(parseError(err))
  }
  return res.json()
}

export const api = {
  auth: {
    me: () => request('GET', '/api/auth/me'),
    login: async (email, password) => {
      const res = await fetch(`${BASE_URL}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Erro desconhecido' }))
        throw new Error(parseError(err))
      }
      return res.json()
    }
  },
  locais: {
    estados: () => request('GET', '/api/locais/estados'),
    cidades: (estado) => request('GET', `/api/locais/cidades?estado=${encodeURIComponent(estado)}`)
  },
  clientes: {
    listar: ({ estado = null, cidade = null } = {}) => {
      const params = new URLSearchParams()
      if (estado) params.set('estado', estado)
      if (cidade) params.set('cidade', cidade)
      const qs = params.toString()
      return request('GET', `/api/clientes${qs ? '?' + qs : ''}`)
    },
    obter: (id) => request('GET', `/api/clientes/${id}`),
    criar: (dados) => request('POST', `/api/clientes`, dados),
    atualizar: (id, dados) => request('PUT', `/api/clientes/${id}`, dados),
    remover: (id) => request('DELETE', `/api/clientes/${id}`),
    uploadFoto: async (clienteId, file) => {
      const token = getLocalToken()
      const form = new FormData()
      form.append('file', file)
      const res = await fetch(`${BASE_URL}/api/clientes/${clienteId}/fotos`, {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: form
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Erro no upload' }))
        throw new Error(parseError(err))
      }
      return res.json()
    },
    deletarFoto: (clienteId, fotoId) => request('DELETE', `/api/clientes/${clienteId}/fotos/${fotoId}`),
    alteracoes: {
      listar: (statusFilter = null, empresaFilter = null) => {
        const params = new URLSearchParams()
        if (statusFilter) params.set('status', statusFilter)
        if (empresaFilter) params.set('empresa', empresaFilter)
        const qs = params.toString()
        return request('GET', `/api/alteracoes${qs ? '?' + qs : ''}`)
      },
      aprovar: (altId) => request('POST', `/api/alteracoes/${altId}/aprovar`),
      recusar: (altId, observacao = null) => request('POST', `/api/alteracoes/${altId}/recusar`, { observacao }),
      editar: (altId, dados) => request('PUT', `/api/alteracoes/${altId}/editar`, dados),
      historico: (clienteId) => request('GET', `/api/clientes/${clienteId}/alteracoes`)
    },
    exportar: async ({ estado = null, cidade = null } = {}) => {
      const params = new URLSearchParams()
      if (estado) params.set('estado', estado)
      if (cidade) params.set('cidade', cidade)
      const qs = params.toString()
      const token = getLocalToken()
      const res = await fetch(`${BASE_URL}/api/clientes/export${qs ? '?' + qs : ''}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {}
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Erro ao exportar' }))
        throw new Error(parseError(err))
      }
      return res.blob()
    },
    previewCarga: async (file) => {
      const token = getLocalToken()
      const form = new FormData()
      form.append('file', file)
      const res = await fetch(`${BASE_URL}/api/clientes/carga/preview`, {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: form
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Erro ao processar planilha' }))
        throw new Error(parseError(err))
      }
      return res.json()
    },
    aplicarCarga: async (file) => {
      const token = getLocalToken()
      const form = new FormData()
      form.append('file', file)
      const res = await fetch(`${BASE_URL}/api/clientes/carga/aplicar`, {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: form
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Erro ao aplicar carga' }))
        throw new Error(parseError(err))
      }
      return res.json()
    }
  },
  users: {
    listar:   ()              => request('GET',    '/api/users/'),
    criar:    (data)          => request('POST',   '/api/users/',      data),
    atualizar: (id, data)     => request('PATCH',   `/api/users/${id}`, data),
    remover:  (id)            => request('DELETE', `/api/users/${id}`)
  },
  notificacoes: {
    listar: () => request('GET', '/api/notificacoes'),
    marcarLida: (id) => request('POST', `/api/notificacoes/${id}/ler`),
    marcarTodasLidas: () => request('POST', '/api/notificacoes/ler-todas')
  },
  solicitacoes: {
    listar: (params = {}) => {
      const qs = new URLSearchParams()
      if (params.status) qs.set('status', params.status)
      if (params.tipo) qs.set('tipo', params.tipo)
      const s = qs.toString()
      return request('GET', `/api/solicitacoes${s ? '?' + s : ''}`)
    },
    criar: (dados) => request('POST', '/api/solicitacoes', dados),
    status: (id, dados) => request('POST', `/api/solicitacoes/${id}/status`, dados)
  }
}