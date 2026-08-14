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
        <RouterLink v-if="usuario?.role === 'admin'" to="/admin/usuarios" class="nav-btn" active-class="active">Usuários</RouterLink>
      </nav>
      <div class="nav-right">
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
import { onMounted, watch, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { autenticado, carregarSessao, logout, getUsuario, temPermissao, sincronizarPermissoes } from './composables/useAuth'

const router = useRouter()
const route = useRoute()
const usuario = getUsuario()
const frontVersion = __APP_VERSION__

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
})

watch(() => route.fullPath, () => {
  const sessao = carregarSessao()
  if (!sessao && route.meta?.auth) {
    router.replace({ name: 'login', query: { redirect: route.fullPath } })
  }
})

function sair() {
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
.user-avatar {
  width: 34px; height: 34px; border-radius: 50%;
  background: linear-gradient(135deg, #3479fb, #1746dc);
  color: #fff; font-weight: 700; font-size: 0.78rem; letter-spacing: 0.02em;
  display: inline-flex; align-items: center; justify-content: center;
  box-shadow: 0 4px 10px -4px rgba(31, 91, 240, 0.6);
  cursor: default; flex-shrink: 0;
}

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