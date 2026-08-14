<template>
  <div class="page">
    <div class="container">
      <div class="page-head">
        <h1>Gerência de Usuários</h1>
        <p>Crie usuários, atribua permissões granulares e ative/desative acessos.</p>
      </div>

      <!-- Formulario criar/editar -->
      <section class="card form-card">
        <h2 class="section-title">{{ editando ? `Editar: ${form.email}` : 'Novo Usuário' }}</h2>
        <div class="form-grid">
          <div class="field">
            <label>Nome</label>
            <input v-model="form.name" placeholder="Nome completo" />
          </div>
          <div class="field">
            <label>E-mail</label>
            <input v-model="form.email" type="email" :disabled="editando" placeholder="user@app.com" />
          </div>
          <div class="field">
            <label>Role</label>
            <select v-model="form.role">
              <option value="user">User</option>
              <option value="admin">Admin (tudo)</option>
            </select>
          </div>
          <div class="field">
            <label>Empresa</label>
            <select v-model="form.empresa">
              <option value="AC">AC</option>
              <option value="SIN">SIN</option>
            </select>
          </div>
          <div class="field">
            <label>Senha {{ editando ? '(deixe vazio p/ não alterar)' : '' }}</label>
            <input v-model="form.password" type="password" :placeholder="editando ? '••••••' : 'min 8 caracteres'" />
          </div>
          <div class="field col2">
            <label>Ativo</label>
            <label class="switch">
              <input type="checkbox" v-model="form.is_active" />
              <span>{{ form.is_active ? 'Sim' : 'Não' }}</span>
            </label>
          </div>
        </div>

        <!-- Permissoes granulares (so relevante para user) -->
        <div v-if="form.role === 'user'" class="perm-box">
          <h3>Permissões</h3>
          <p class="perm-hint">Marque o que este usuário pode fazer. Admin ignora estas permissões (sempre pode tudo).</p>
          <div class="perm-grid">
            <label v-for="p in PERMISSOES" :key="p.key" class="perm-item">
              <input type="checkbox" :value="p.key" v-model="form.permissions" />
              <span class="perm-icon">{{ p.icon }}</span>
              <span>
                <strong>{{ p.label }}</strong>
                <small>{{ p.desc }}</small>
              </span>
            </label>
          </div>
        </div>

        <div class="acoes">
          <button class="btn btn-primary" @click="salvar" :disabled="salvando">
            {{ salvando ? 'Salvando...' : (editando ? 'Atualizar' : 'Criar usuário') }}
          </button>
          <button v-if="editando" class="btn btn-secondary" @click="cancelarEdicao">Cancelar</button>
          <span v-if="msg" :class="['msg', msgTipo]">{{ msg }}</span>
        </div>
      </section>

      <!-- Lista de usuarios -->
      <section class="card">
        <h2 class="section-title">Usuários cadastrados ({{ usuarios.length }})</h2>
        <div v-if="loading" class="placeholder">Carregando...</div>
        <div v-else class="table-wrap">
          <table class="table">
            <thead>
              <tr>
                <th>Nome</th>
                <th>E-mail</th>
                <th>Empresa</th>
                <th>Role</th>
                <th>Permissões</th>
                <th>Status</th>
                <th>Ações</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="u in usuarios" :key="u.id">
                <td><strong>{{ u.name }}</strong></td>
                <td>{{ u.email }}</td>
                <td><span class="empresa-tag">{{ u.empresa || 'AC' }}</span></td>
                <td>
                  <span :class="['tag', u.role === 'admin' ? 'tag-admin' : 'tag-user']">{{ u.role }}</span>
                </td>
                <td>
                  <div class="perm-chips">
                    <span v-if="u.role === 'admin'" class="chip chip-admin">TUDO</span>
                    <span v-else v-for="p in u.permissions" :key="p" class="chip">{{ p }}</span>
                    <span v-if="u.role !== 'admin' && (!u.permissions || u.permissions.length === 0)" class="chip chip-empty">nenhuma</span>
                  </div>
                </td>
                <td>
                  <span :class="['status', u.is_active ? 'status-on' : 'status-off']">
                    {{ u.is_active ? 'Ativo' : 'Inativo' }}
                  </span>
                </td>
                <td>
                  <button class="btn btn-sm btn-secondary" @click="editar(u)">Editar</button>
                  <button v-if="u.email !== meuEmail" class="btn btn-sm btn-danger" @click="remover(u)">Excluir</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { api, decodeTokenPayload, getLocalToken } from '../api'

const PERMISSOES = [
  { key: 'visualizar', label: 'Visualizar', icon: '👁', desc: 'Pesquisar e ver clientes' },
  { key: 'editar',     label: 'Editar',     icon: '✏️', desc: 'Alterar dados de clientes (submete p/ aprovação)' },
  { key: 'criar',      label: 'Criar',      icon: '➕', desc: 'Cadastrar novos clientes' },
  { key: 'deletar',    label: 'Excluir',    icon: '🗑', desc: 'Remover clientes' },
  { key: 'carga',      label: 'Carga',      icon: '📊', desc: 'Carga em massa via Excel' },
  { key: 'exportar',   label: 'Exportar',   icon: '📤', desc: 'Exportar dados em Excel' },
  { key: 'aprovar',    label: 'Aprovar',    icon: '✔', desc: 'Revisar e aprovar endereços submetidos' }
]

const usuarios = ref([])
const loading = ref(false)
const salvando = ref(false)
const editando = ref(null)
const msg = ref('')
const msgTipo = ref('ok')

const formInit = () => ({
  name: '', email: '', password: '', role: 'user',
  empresa: 'AC', permissions: [], is_active: true
})
const form = reactive(formInit())

const meuEmail = computed(() => {
  const token = getLocalToken()
  const payload = token ? decodeTokenPayload(token) : null
  return payload?.email || ''
})

onMounted(() => carregar())

async function carregar() {
  loading.value = true
  try {
    usuarios.value = await api.users.listar()
  } catch (e) {
    msg.value = 'Erro ao carregar: ' + e.message
    msgTipo.value = 'erro'
  } finally {
    loading.value = false
  }
}

function editar(u) {
  editando.value = u.id
  Object.assign(form, {
    name: u.name, email: u.email, password: '', role: u.role,
    empresa: u.empresa || 'AC',
    permissions: [...(u.permissions || [])], is_active: u.is_active
  })
  msg.value = ''
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function cancelarEdicao() {
  editando.value = null
  Object.assign(form, formInit())
  msg.value = ''
}

async function salvar() {
  if (!form.name || !form.email) { msg.value = 'Nome e e-mail são obrigatórios'; msgTipo.value = 'erro'; return }
  if (!editando.value && !form.password) { msg.value = 'Senha é obrigatória ao criar'; msgTipo.value = 'erro'; return }

  salvando.value = true
  msg.value = ''
  try {
    if (editando.value) {
      const payload = { name: form.name, role: form.role, empresa: form.empresa, is_active: form.is_active }
      if (form.role === 'user') payload.permissions = form.permissions
      if (form.password) payload.password = form.password
      await api.users.atualizar(editando.value, payload)
      msg.value = 'Usuário atualizado!'
    } else {
      const payload = {
        name: form.name, email: form.email, auth_provider: 'local',
        role: form.role, empresa: form.empresa,
        permissions: form.role === 'user' ? form.permissions : [],
        password: form.password
      }
      await api.users.criar(payload)
      msg.value = 'Usuário criado!'
    }
    msgTipo.value = 'ok'
    cancelarEdicao()
    await carregar()
  } catch (e) {
    msg.value = 'Erro: ' + e.message
    msgTipo.value = 'erro'
  } finally {
    salvando.value = false
  }
}

async function remover(u) {
  if (!confirm(`Excluir o usuário "${u.name}" (${u.email})?`)) return
  try {
    await api.users.remover(u.id)
    await carregar()
  } catch (e) {
    msg.value = 'Erro ao excluir: ' + e.message
    msgTipo.value = 'erro'
  }
}
</script>

<style scoped>
.page { padding: 1.5rem 1rem 2.5rem; }
.container { max-width: 1000px; margin: 0 auto; }
.page-head { margin-bottom: 1.25rem; }
.page-head h1 { font-size: 1.5rem; font-weight: 700; color: #0f172a; }
.page-head p { color: #64748b; font-size: 0.88rem; margin-top: 0.2rem; }
.card { background: #fff; border-radius: 16px; padding: 1.25rem; box-shadow: 0 10px 30px -12px rgba(20,40,90,0.18); border: 1px solid #eef2f8; margin-bottom: 1.1rem; }
.section-title { font-size: 1rem; font-weight: 700; color: #1d2a4d; margin-bottom: 0.9rem; padding-bottom: 0.6rem; border-bottom: 1px solid #eef2f8; }
.form-card { margin-bottom: 1.1rem; }

.form-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 0.4rem 0.9rem; }
.col2 { grid-column: span 1; }
@media (max-width: 720px) { .form-grid { grid-template-columns: 1fr; } }

.field { margin-bottom: 0.8rem; }
.field label { display: block; font-size: 0.78rem; font-weight: 600; color: #475569; margin-bottom: 0.3rem; }
.field input, .field select {
  width: 100%; padding: 0.5rem 0.7rem; border: 1px solid #dbe2ee; border-radius: 8px;
  font-size: 0.9rem; outline: none; background: #fff; transition: all 0.15s;
}
.field input:focus, .field select:focus { border-color: #1f5bf0; box-shadow: 0 0 0 4px rgba(31,91,240,0.12); }
.field input:disabled { background: #f1f5f9; color: #94a3b8; }
.switch { display: inline-flex; align-items: center; gap: 0.5rem; cursor: pointer; font-size: 0.85rem; }
.switch input { width: 18px; height: 18px; cursor: pointer; }

.perm-box { margin-top: 1rem; padding: 1rem; background: #f1f7ff; border-radius: 10px; border: 1px solid #d9eaff; }
.perm-box h3 { font-size: 0.95rem; font-weight: 700; color: #1e3a8a; margin-bottom: 0.3rem; }
.perm-hint { font-size: 0.78rem; color: #64748b; margin-bottom: 0.7rem; }
.perm-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 0.6rem; }
.perm-item { display: flex; align-items: flex-start; gap: 0.5rem; padding: 0.65rem; background: #fff; border-radius: 8px; border: 1px solid #eef2f8; cursor: pointer; transition: all 0.15s; }
.perm-item:hover { border-color: #1f5bf0; }
.perm-item input { margin-top: 0.2rem; width: 18px; height: 18px; cursor: pointer; }
.perm-icon { font-size: 1.1rem; }
.perm-item strong { display: block; font-size: 0.85rem; color: #1d2a4d; }
.perm-item small { display: block; font-size: 0.72rem; color: #94a3b8; margin-top: 0.1rem; }

.acoes { display: flex; align-items: center; gap: 0.7rem; margin-top: 1rem; flex-wrap: wrap; }
.msg { font-size: 0.85rem; }
.msg.ok { color: #15803d; }
.msg.erro { color: #b91c1c; }

.table-wrap { overflow-x: auto; }
.table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
.table th { text-align: left; padding: 0.55rem 0.7rem; border-bottom: 2px solid #eef2f8; color: #64748b; font-weight: 600; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.04em; }
.table td { padding: 0.6rem 0.7rem; border-bottom: 1px solid #f1f5f9; vertical-align: top; }
.table tr:hover td { background: #f8fafe; }

.tag { display: inline-block; padding: 0.15rem 0.5rem; border-radius: 5px; font-size: 0.7rem; font-weight: 700; text-transform: uppercase; }
.tag-admin { background: #1f5bf0; color: #fff; }
.tag-user { background: #e2e8f0; color: #475569; }

.empresa-tag { display: inline-block; padding: 0.15rem 0.55rem; border-radius: 5px; font-size: 0.7rem; font-weight: 700; background: #dbeafe; color: #1d4ed8; letter-spacing: 0.03em; }

.perm-chips { display: flex; flex-wrap: wrap; gap: 0.25rem; }
.chip { display: inline-block; padding: 0.1rem 0.45rem; border-radius: 5px; font-size: 0.68rem; font-weight: 600; background: #eef6ff; color: #1746dc; }
.chip-admin { background: #1f5bf0; color: #fff; }
.chip-empty { background: #f1f5f9; color: #94a3b8; font-style: italic; }

.status { display: inline-block; padding: 0.15rem 0.5rem; border-radius: 5px; font-size: 0.72rem; font-weight: 600; }
.status-on { background: #dcfce7; color: #15803d; }
.status-off { background: #fee2e2; color: #b91c1c; }

.btn { padding: 0.5rem 0.95rem; border-radius: 8px; cursor: pointer; font-weight: 600; font-size: 0.85rem; border: none; }
.btn-primary { background: linear-gradient(135deg, #3479fb, #1746dc); color: #fff; box-shadow: 0 8px 18px -8px rgba(23,70,220,0.6); }
.btn-secondary { background: #eef6ff; color: #1746dc; border: 1px solid #bcdcff; }
.btn-danger { background: #fee2e2; color: #b91c1c; border: 1px solid #fecaca; }
.btn-sm { padding: 0.35rem 0.65rem; font-size: 0.78rem; }
.btn:disabled { opacity: 0.6; cursor: not-allowed; }
.placeholder { text-align: center; padding: 1.5rem; color: #94a3b8; }
</style>