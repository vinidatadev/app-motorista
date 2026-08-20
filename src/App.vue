<template>
  <div class="min-h-screen flex flex-col">
    <header v-if="autenticado" class="navbar">
      <div class="logo">
        <span class="logo-badge" v-html="pinoSvg"></span>
        <span class="logo-text">App Motorista</span>
      </div>
      <nav class="nav-links">
        <RouterLink v-if="temPermissao('visualizar')" to="/clientes/pesquisa" class="nav-btn" active-class="active">Pesquisar</RouterLink>
        <RouterLink v-if="temPermissao('editar')" to="/clientes/editar" class="nav-btn" active-class="active">Editar</RouterLink>
        <RouterLink v-if="temPermissao('criar')" to="/clientes/cadastrar" class="nav-btn" active-class="active">Cadastrar</RouterLink>
        <RouterLink v-if="temPermissao('carga')" to="/clientes/carga" class="nav-btn" active-class="active">Carga Excel</RouterLink>
        <RouterLink v-if="temPermissao('aprovar')" to="/aprovacoes" class="nav-btn" active-class="active">Aprovações</RouterLink>
        <RouterLink v-if="ehEquipeSolicitacoes" to="/solicitacoes" class="nav-btn" active-class="active">Solicitações</RouterLink>
        <RouterLink v-if="usuario?.role === 'admin'" to="/admin/usuarios" class="nav-btn" active-class="active">Usuários</RouterLink>
      </nav>
      <div class="nav-right">
        <div class="notif-wrap" ref="notifWrap">
          <button class="notif-btn" @click="toggleMenu" :class="{ 'has-unread': naoLidas > 0 }" title="Notificações" aria-label="Notificações">
            <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
              <path d="M12 22c1.1 0 2-.9 2-2h-4c0 1.1.9 2 2 2zm6-6v-5c0-3.07-1.63-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v.68C7.64 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2z"/>
            </svg>
            <span v-if="naoLidas > 0" class="notif-badge">{{ naoLidas > 99 ? '99+' : naoLidas }}</span>
          </button>

          <div v-if="menuAberto" class="notif-menu">
            <div class="notif-menu-head">
              <strong>Notificações</strong>
              <button v-if="naoLidas > 0" class="btn-link" @click="marcarTodasLidas()">Marcar todas como lidas</button>
            </div>
            <div v-if="!notificacoes.length" class="notif-vazio">Nenhuma notificação</div>
            <ul v-else class="notif-lista">
              <li
                v-for="n in notificacoes"
                :key="n.id"
                :class="['notif-item', { unread: !n.lida }]"
                @click="abrirNotificacao(n)"
              >
                <span class="notif-icone">{{ iconeNotif(n.tipo) }}</span>
                <span class="notif-texto">
                  <strong>{{ n.titulo }}</strong>
                  <span class="notif-msg">{{ n.mensagem }}</span>
                  <span class="notif-tempo">{{ tempoRelativo(n.created_at) }}</span>
                </span>
              </li>
            </ul>
          </div>
        </div>
        <span class="empresa-badge" :title="`Empresa: ${usuario?.empresa || 'AC'}`">{{ usuario?.empresa || 'AC' }}</span>
        <span class="user-avatar" :title="usuario?.email">{{ iniciais }}</span>
        <button class="btn btn-outline" @click="sair">Sair</button>
      </div>
    </header>

    <main class="flex-1">
      <RouterView />
    </main>

    <footer class="version-bar">
      front v{{ frontVersion }} · app-motorista
    </footer>
  </div>
</template>

<script setup>
import { onMounted, onBeforeUnmount, watch, computed, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { autenticado, carregarSessao, logout, getUsuario, temPermissao, sincronizarPermissoes } from './composables/useAuth'
import { notificacoes, naoLidas, iniciarNotificacoes, pararNotificacoes, marcarLida, marcarTodasLidas, carregar } from './composables/useNotificacoes'

const router = useRouter()
const route = useRoute()
const usuario = getUsuario()
const frontVersion = __APP_VERSION__

// Time de solicitações: admin ou quem tem permissão 'solicitacoes'
const ehEquipeSolicitacoes = computed(() =>
  usuario.value?.role === 'admin' || temPermissao('solicitacoes')
)

// Notificações (sino)
const menuAberto = ref(false)
const notifWrap = ref(null)

function toggleMenu() {
  menuAberto.value = !menuAberto.value
  // Sempre sincroniza a lista ao abrir o sino (mesmo se o WS estiver fora)
  if (menuAberto.value) carregar()
}

function abrirNotificacao(n) {
  menuAberto.value = false
  marcarLida(n)
  // A tela de Solicitações é da equipe: se o usuário não faz parte dela, a
  // notificação apenas abre o cliente/área adequada (ou nada, só marca como lida).
  let link = n.link || (n.tipo === 'nova_alteracao' ? '/aprovacoes?status=pendente' : '/clientes/pesquisa')
  if (link.startsWith('/solicitacoes') && !ehEquipeSolicitacoes.value) {
    link = n.cliente_id ? `/clientes/pesquisa?cliente=${n.cliente_id}` : '/clientes/pesquisa'
  }
  router.push(link)
}

function iconeNotif(tipo) {
  return {
    nova_alteracao: '🔔',
    aprovada: '✅',
    recusada: '❌',
    editada: '✏️',
    nova_solicitacao: '📋',
    solicitacao_concluida: '✅',
    solicitacao_recusada: '❌'
  }[tipo] || '🔔'
}

function tempoRelativo(iso) {
  if (!iso) return ''
  try {
    const t = new Date(iso)
    const min = Math.floor((Date.now() - t.getTime()) / 60000)
    if (min < 1) return 'agora'
    if (min < 60) return `${min} min`
    const h = Math.floor(min / 60)
    if (h < 24) return `${h} h`
    const d = Math.floor(h / 24)
    if (d < 7) return `${d} d`
    return t.toLocaleDateString('pt-BR')
  } catch { return '' }
}

function onClickOutside(e) {
  if (menuAberto.value && notifWrap.value && !notifWrap.value.contains(e.target)) {
    menuAberto.value = false
  }
}

// Pino de mapa azul (SVG inline) usado como logo
const pinoSvg = `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" width="22" height="22">
  <path d="M12 2C7.6 2 4 5.6 4 10c0 5.9 7.1 11.2 7.4 11.4.4.3.8.3 1.2 0C12.9 21.2 20 15.9 20 10c0-4.4-3.6-8-8-8z" fill="#fff"/>
  <circle cx="12" cy="10" r="3" fill="#1746dc"/>
</svg>`

// Iniciais do primeiro + último nome (ex: "Administrador Teste" -> "AT")
const iniciais = computed(() => {
  const nome = usuario.value?.name || ''
  const partes = nome.trim().split(/\s+/).filter(Boolean)
  if (partes.length === 0) return '?'
  if (partes.length === 1) return partes[0].slice(0, 2).toUpperCase()
  return (partes[0][0] + partes[partes.length - 1][0]).toUpperCase()
})

onMounted(async () => {
  carregarSessao()
  const sessao = carregarSessao()
  // Sincroniza perms com o backend (1x por mount) — pega mudancas do admin
  if (sessao) {
    await sincronizarPermissoes()
  }
  if (sessao && route.path === '/login') {
    router.replace('/clientes/pesquisa')
  }
  if (!sessao && route.meta?.auth) {
    router.replace({ name: 'login', query: { redirect: route.fullPath } })
  }
  // Inicia as notificações em tempo real se já estiver autenticado
  if (autenticado.value) iniciarNotificacoes()
  document.addEventListener('click', onClickOutside)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onClickOutside)
  pararNotificacoes()
})

watch(() => route.fullPath, () => {
  const sessao = carregarSessao()
  if (!sessao && route.meta?.auth) {
    router.replace({ name: 'login', query: { redirect: route.fullPath } })
  }
})

// Conecta/desconecta o WebSocket de notificações junto com o login/logout
watch(autenticado, (val) => {
  if (val) iniciarNotificacoes()
  else pararNotificacoes()
})

function sair() {
  pararNotificacoes()
  logout()
  router.replace('/login')
}
</script>

<style scoped>
.navbar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.75rem 1rem;
  padding: 0.7rem 1rem;
  background: #ffffff;
  border-bottom: 1px solid #e8eaf0;
  box-shadow: 0 1px 4px rgba(15, 23, 42, 0.05);
}
.logo { display: flex; align-items: center; gap: 0.55rem; flex-shrink: 0; }
.logo-badge {
  width: 36px; height: 36px; border-radius: 11px;
  background: linear-gradient(135deg, #3479fb, #1746dc);
  display: inline-flex; align-items: center; justify-content: center;
  box-shadow: 0 6px 14px -6px rgba(31, 91, 240, 0.7);
  flex-shrink: 0;
}
.logo-text { font-weight: 700; color: #1d2a4d; letter-spacing: -0.01em; font-size: 0.95rem; }

.nav-links { display: flex; gap: 0.25rem; flex: 1; min-width: 0; flex-wrap: wrap; }
.nav-btn {
  padding: 0.42rem 0.85rem; border-radius: 8px; cursor: pointer;
  font-size: 0.88rem; color: #475569; text-decoration: none;
  background: none; border: none; transition: all 0.15s; white-space: nowrap;
}
.nav-btn:hover { background: #eef6ff; color: #1f5bf0; }
.nav-btn.active { background: #d9eaff; color: #1746dc; font-weight: 600; }

.nav-right { display: flex; align-items: center; gap: 0.75rem; flex-shrink: 0; margin-left: auto; }
.empresa-badge {
  padding: 0.16rem 0.55rem; border-radius: 6px;
  background: #dbeafe; color: #1d4ed8;
  font-size: 0.72rem; font-weight: 700; letter-spacing: 0.04em;
}
.user-avatar {
  width: 34px; height: 34px; border-radius: 50%;
  background: linear-gradient(135deg, #3479fb, #1746dc);
  color: #fff; font-weight: 700; font-size: 0.78rem; letter-spacing: 0.02em;
  display: inline-flex; align-items: center; justify-content: center;
  box-shadow: 0 4px 10px -4px rgba(31, 91, 240, 0.6);
  cursor: default; flex-shrink: 0;
}

/* Notificações (sino) */
.notif-wrap { position: relative; }
.notif-btn {
  position: relative;
  width: 36px; height: 36px; border-radius: 10px;
  background: #f1f5f9; border: 1px solid #e2e8f0;
  color: #475569; cursor: pointer;
  display: inline-flex; align-items: center; justify-content: center;
  transition: all 0.15s;
}
.notif-btn:hover { background: #eef6ff; border-color: #1f5bf0; color: #1f5bf0; }
.notif-btn.has-unread { background: #dbeafe; border-color: #1f5bf0; color: #1d4ed8; }
.notif-badge {
  position: absolute; top: -6px; right: -6px;
  min-width: 18px; height: 18px; padding: 0 4px;
  border-radius: 999px;
  background: #dc2626; color: #fff;
  font-size: 0.66rem; font-weight: 700; line-height: 18px; text-align: center;
  box-shadow: 0 2px 6px rgba(220, 38, 38, 0.4);
}
.notif-menu {
  position: absolute; right: 0; top: calc(100% + 8px);
  width: 340px; max-width: calc(100vw - 2rem);
  background: #fff; border-radius: 14px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 24px 60px -18px rgba(15, 23, 42, 0.35);
  z-index: 1200; overflow: hidden;
  animation: notif-in 0.16s ease-out;
}

/* Ajuste para mobile: menu responsivo sem scroll horizontal */
@media (max-width: 640px) {
  .notif-menu {
    position: fixed;
    right: 0.5rem;
    left: 0.5rem;
    top: 60px;
    transform: none;
    width: auto;
    max-width: calc(100vw - 1rem);
  }
}
@keyframes notif-in {
  from { opacity: 0; transform: translateY(-6px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}
.notif-menu-head {
  display: flex; align-items: center; justify-content: space-between; gap: 0.5rem;
  padding: 0.65rem 0.85rem;
  border-bottom: 1px solid #eef2f8;
  background: #f8fafc;
}
.notif-menu-head strong { font-size: 0.85rem; color: #1d2a4d; }
.btn-link {
  background: none; border: none; cursor: pointer;
  font-size: 0.74rem; color: #1f5bf0; font-weight: 600;
  padding: 0.1rem 0.2rem;
}
.btn-link:hover { text-decoration: underline; }
.notif-vazio {
  padding: 1.4rem 1rem; text-align: center;
  font-size: 0.82rem; color: #94a3b8;
}
.notif-lista {
  list-style: none; margin: 0; padding: 0.35rem;
  max-height: 420px; overflow-y: auto;
}
.notif-item {
  display: flex; gap: 0.6rem; align-items: flex-start;
  padding: 0.6rem 0.6rem; border-radius: 10px; cursor: pointer;
  transition: background 0.12s;
}
.notif-item:hover { background: #f1f7ff; }
.notif-item.unread { background: #eef6ff; }
.notif-item.unread:hover { background: #dbeafe; }
.notif-icone { font-size: 1.05rem; line-height: 1.2; flex-shrink: 0; }
.notif-texto { display: flex; flex-direction: column; gap: 0.1rem; min-width: 0; }
.notif-texto strong { font-size: 0.82rem; color: #1d2a4d; line-height: 1.3; }
.notif-item.unread .notif-texto strong { color: #1d4ed8; }
.notif-msg { font-size: 0.76rem; color: #64748b; line-height: 1.35; }
.notif-tempo { font-size: 0.68rem; color: #94a3b8; }

.version-bar {
  padding: 0.5rem 1rem; text-align: right;
  font-size: 0.72rem; color: #b6c2d4;
  border-top: 1px solid #e8eaf0; background: #fff;
}

.btn { padding: 0.45rem 1rem; border-radius: 8px; cursor: pointer; font-size: 0.85rem; font-weight: 500; }
.btn-outline { background: transparent; border: 1px solid #1f5bf0; color: #1f5bf0; }
.btn-outline:hover { background: #eef6ff; }

/* Mobile: navbar em coluna — logo+perfil na mesma linha, nav abaixo */
@media (max-width: 640px) {
  .navbar { gap: 0.6rem; padding: 0.6rem 0.75rem; }
  .nav-links { order: 3; width: 100%; flex: none; }
  .nav-btn { flex: 1; text-align: center; font-size: 0.82rem; padding: 0.45rem 0.5rem; }
  .logo-text { font-size: 0.9rem; }
}
</style>