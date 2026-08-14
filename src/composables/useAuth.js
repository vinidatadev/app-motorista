import { ref, computed } from 'vue'
import { getLocalToken, clearLocalToken, saveLocalToken, decodeTokenPayload, isTokenValid, api } from '../api'

const usuario = ref(null)

export function getUsuario() { return usuario }
export const autenticado = computed(() => !!usuario.value)

// Restaurar sessão a partir do token (sincrono) — usado pelo router guard.
// Não busca /me aqui (assincrono) pra nao atrasar a navegacao.
export function carregarSessao() {
  if (usuario.value) return usuario.value
  const token = getLocalToken()
  if (!token || !isTokenValid(token)) {
    clearLocalToken()
    usuario.value = null
    return null
  }
  const payload = decodeTokenPayload(token)
  usuario.value = {
    name: payload?.name,
    email: payload?.email,
    role: payload?.role,
    empresa: payload?.empresa || 'AC',
    permissions: payload?.permissions || []
  }
  return usuario.value
}

// Re-valida permissões no backend (lê do DB) e atualiza o estado reativo.
// Chamar apos login, F5 e quando admin alterar permissoes de um usuario.
// Resolve o bug: permissões mudadas no admin só entram em vigor após refresh.
export async function sincronizarPermissoes() {
  const token = getLocalToken()
  if (!token || !isTokenValid(token)) return null
  try {
    const me = await api.auth.me()
    // Atualiza role + permissions refletindo o estado atual do banco
    if (usuario.value) {
      usuario.value = {
        ...usuario.value,
        name: me.name,
        role: me.role,
        empresa: me.empresa || 'AC',
        permissions: me.permissions || []
      }
    }
    return usuario.value
  } catch {
    // token invalido/network err — mantém o estado do token como fallback
    return usuario.value
  }
}

export function loginComToken(token) {
  saveLocalToken(token)
  carregarSessao()
  // Busca perms reais do backend (token pode estar desatualizado pós-alteração)
  sincronizarPermissoes()
}

export function logout() {
  clearLocalToken()
  usuario.value = null
}

// Helper: verifica se o usuario tem uma permissao (admin sempre true).
// Lê do estado reativo `usuario` (atualizado por sincronizarPermissoes).
export function temPermissao(permissao) {
  const u = usuario.value
  if (!u) return false
  if (u.role === 'admin') return true
  return (u.permissions || []).includes(permissao)
}

export function isAdmin() {
  return usuario.value?.role === 'admin'
}