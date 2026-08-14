<template>
  <div class="page">
    <div class="container">
      <div class="card">
        <div class="icon">🔒</div>
        <h1>Acesso negado</h1>
        <p>Você não tem permissão para acessar esta página.</p>
        <p class="sub" v-if="usuario?.email">Conectado como <strong>{{ usuario.email }}</strong> · role: <span class="tag">{{ usuario.role }}</span></p>
        <div class="perms" v-if="usuario?.permissions?.length">
          <span class="hint">Permissões atuais:</span>
          <span v-for="p in usuario.permissions" :key="p" class="chip">{{ p }}</span>
        </div>
        <p class="sub" v-else>Sem permissões granulares atribuídas.</p>
        <p class="sub">Contate o administrador para liberar acesso, ou retorne para uma página permitida.</p>
        <div class="acoes">
          <router-link v-if="temPermissao('visualizar')" to="/clientes/pesquisa" class="btn btn-primary">← Ir para Pesquisa</router-link>
          <button class="btn btn-secondary" @click="refresh">🔄 Recarregar</button>
        </div>
        <p class="dica">Se o administrador acabou de liberar uma permissão para você, clique em "Recarregar" (isso sincroniza com o banco).</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { temPermissao, getUsuario, sincronizarPermissoes } from '../composables/useAuth'
import { useRouter } from 'vue-router'

const usuario = getUsuario()
const router = useRouter()

async function refresh() {
  // Re-busca perms no backend e tenta re-navegar (se liberou, segue; se não, fica aqui)
  await sincronizarPermissoes()
  // Se ganhou visualizar, manda pra pesquisa; senão fica na sem-acesso
  if (temPermissao('visualizar')) router.push('/clientes/pesquisa')
}
</script>

<style scoped>
.page { padding: 2rem 1rem; min-height: 70vh; display: flex; align-items: center; justify-content: center; }
.container { max-width: 480px; width: 100%; }
.card { background: #fff; border-radius: 18px; padding: 2rem; text-align: center; box-shadow: 0 14px 40px -10px rgba(20,40,90,0.2); border: 1px solid #eef2f8; }
.icon { font-size: 3.5rem; margin-bottom: 0.5rem; }
h1 { font-size: 1.4rem; font-weight: 700; color: #0f172a; margin-bottom: 0.4rem; }
p { color: #475569; font-size: 0.9rem; margin: 0.3rem 0; line-height: 1.4; }
.sub { color: #94a3b8; font-size: 0.82rem; }
.tag { display: inline-block; padding: 0.1rem 0.45rem; border-radius: 5px; font-size: 0.72rem; font-weight: 700; background: #e2e8f0; color: #475569; text-transform: uppercase; }
.perms { margin: 0.7rem 0; display: flex; flex-wrap: wrap; gap: 0.4rem; align-items: center; justify-content: center; }
.hint { font-size: 0.78rem; color: #64748b; width: 100%; margin-bottom: 0.3rem; }
.chip { display: inline-block; padding: 0.15rem 0.55rem; border-radius: 6px; font-size: 0.76rem; font-weight: 600; background: #eef6ff; color: #1746dc; }
.acoes { display: flex; gap: 0.6rem; justify-content: center; margin-top: 1.2rem; flex-wrap: wrap; }
.btn { padding: 0.55rem 1.1rem; border-radius: 9px; cursor: pointer; font-weight: 600; font-size: 0.88rem; border: none; text-decoration: none; display: inline-block; }
.btn-primary { background: linear-gradient(135deg, #3479fb, #1746dc); color: #fff; box-shadow: 0 8px 18px -8px rgba(23,70,220,0.6); }
.btn-secondary { background: #eef6ff; color: #1746dc; border: 1px solid #bcdcff; }
.dica { margin-top: 1rem; font-size: 0.72rem; color: #94a3b8; font-style: italic; }
</style>