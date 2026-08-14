import { createRouter, createWebHistory } from 'vue-router'
import { getLocalToken, isTokenValid, decodeTokenPayload } from '../api'
import { carregarSessao, sincronizarPermissoes, temPermissao, isAdmin } from '../composables/useAuth'

const routes = [
  { path: '/', redirect: '/login' },
  { path: '/login', name: 'login', component: () => import('../views/LoginView.vue') },
  { path: '/clientes/pesquisa', name: 'pesquisa', component: () => import('../views/PesquisaView.vue'), meta: { auth: true, perm: 'visualizar' } },
  { path: '/clientes/editar', name: 'editar', component: () => import('../views/EditarView.vue'), meta: { auth: true, perm: 'editar' } },
  { path: '/clientes/cadastrar', name: 'cadastrar', component: () => import('../views/CadastrarView.vue'), meta: { auth: true, perm: 'criar' } },
  { path: '/clientes/carga', name: 'carga', component: () => import('../views/CargaView.vue'), meta: { auth: true, perm: 'carga' } },
  { path: '/aprovacoes', name: 'aprovacoes', component: () => import('../views/AprovacoesView.vue'), meta: { auth: true, perm: 'aprovar' } },
  { path: '/admin/usuarios', name: 'usuarios', component: () => import('../views/AdminView.vue'), meta: { auth: true, admin: true } },
  { path: '/sem-acesso', name: 'sem-acesso', component: () => import('../views/SemAcessoView.vue') }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

let permSincronizadas = false

router.beforeEach(async (to) => {
  if (!to.meta?.auth) return true

  // 1. Token valido?
  const token = getLocalToken()
  if (!token || !isTokenValid(token)) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }

  // 2. Restaura sessao do token (sincrono)
  carregarSessao()

  // 3. Sincroniza permissões com o backend (1x por load/interação)
  //    Evita bloquear navegacao quando admin mudou permissoes do user.
  if (!permSincronizadas) {
    await sincronizarPermissoes()
    permSincronizadas = true
  }

  // 4. Checa permissão granular da rota (antics admins sempre passam)
  if (to.meta?.admin && !isAdmin()) {
    return { name: 'sem-acesso' }
  }
  if (to.meta?.perm && !temPermissao(to.meta.perm)) {
    return { name: 'sem-acesso' }
  }

  return true
})

export default router