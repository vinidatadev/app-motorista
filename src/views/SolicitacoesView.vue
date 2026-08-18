<template>
  <div class="page">
    <div class="container">
      <div class="page-head">
        <h1>Solicitações</h1>
        <p>
          Pedidos abertos pelos usuários: cadastro de cliente novo ou atualização de contato.
          <template v-if="ehEquipe">Você faz parte do time responsável por atender.</template>
          <template v-else>Aqui aparecem somente as solicitações que você abriu.</template>
        </p>
      </div>

      <!-- Filtros -->
      <div class="filtros">
        <div class="filtros-status">
          <button
            v-for="s in statusList"
            :key="s.value"
            :class="['btn-status', { active: filtroStatus === s.value }]"
            @click="mudarFiltroStatus(s.value)"
          >{{ s.label }} <span class="count">{{ contagens[s.value] || 0 }}</span></button>
        </div>
        <div class="filtros-tipo">
          <button
            v-for="t in tipoList"
            :key="t.value"
            :class="['btn-status', { active: filtroTipo === t.value }]"
            @click="filtroTipo = t.value; carregar()"
          >{{ t.label }}</button>
        </div>
      </div>

      <div v-if="loading" class="placeholder">Carregando...</div>
      <div v-else-if="!solicitacoes.length" class="placeholder">
        <div class="empty-icon">📭</div>
        <p>Nenhuma solicitação {{ filtroLabel }}</p>
      </div>

      <!-- Lista -->
      <div v-else class="lista">
        <article v-for="s in solicitacoes" :key="s.id" class="card solic">
          <header class="sol-head">
            <div class="sol-tags">
              <span :class="['tag', 'tag-' + s.tipo]">{{ s.tipo_label }}</span>
              <span :class="['status-tag', 'status-' + s.status]">{{ statusLabel(s.status) }}</span>
            </div>
            <div class="sol-meta">
              <span class="campo-row"><strong>Aberto por:</strong> {{ nomeComEmpresa(s.solicitante_nome, s.solicitante_empresa) }}</span>
              <span class="campo-row"><strong>Em:</strong> {{ formatarData(s.created_at) }}</span>
              <span v-if="s.resolvido_por_nome" class="campo-row"><strong>Atendido por:</strong> {{ nomeComEmpresa(s.resolvido_por_nome, s.resolvido_por_empresa) }}</span>
            </div>
          </header>

          <h2 class="sol-cliente">
            {{ s.cliente_nome }}
            <code v-if="s.cliente_codigo" class="codigo">#{{ s.cliente_codigo }}</code>
          </h2>

          <p v-if="s.descricao" class="sol-desc">{{ s.descricao }}</p>
          <p v-if="s.observacao_resolucao" class="sol-resolucao">
            <strong>{{ s.status === 'recusada' ? 'Motivo da recusa:' : 'Nota da resolução:' }}</strong> {{ s.observacao_resolucao }}
          </p>

          <!-- Ações do time -->
          <div v-if="ehEquipe && s.status !== 'concluida' && s.status !== 'recusada'" class="acoes-sol">
            <button class="btn btn-secondary" @click="mudarStatus(s, 'em_andamento')" :disabled="processandoId === s.id || s.status === 'em_andamento'">
              {{ s.status === 'em_andamento' ? 'Em andamento...' : 'Iniciar atendimento' }}
            </button>
            <button class="btn btn-success" @click="abrirConcluir(s)" :disabled="processandoId === s.id">✓ Concluir</button>
            <button class="btn btn-danger" @click="abrirRecusar(s)" :disabled="processandoId === s.id">✕ Recusar</button>
          </div>

          <!-- Links rápidos pós-conclusão -->
          <div v-if="s.status === 'concluida'" class="acoes-sol">
            <button v-if="s.tipo === 'novo_cliente'" class="btn btn-primary" @click="cadastrarCliente(s)">
              ➕ Cadastrar cliente
            </button>
            <button v-if="s.tipo === 'atualizar_contato' && s.cliente_id" class="btn btn-primary" @click="editarCliente(s)">
              ✏️ Editar cliente
            </button>
          </div>
        </article>
      </div>

      <span v-if="msg" :class="['msg', msgTipo]">{{ msg }}</span>
    </div>

    <!-- Modal Concluir -->
    <div v-if="modalConcluir" class="modal-overlay" @click.self="fecharConcluir">
      <div class="modal-card">
        <h3>✓ Concluir solicitação</h3>
        <p class="modal-sub">Cliente: <strong>{{ modalConcluir.cliente_nome }}</strong></p>
        <div class="field">
          <label>Nota da resolução (opcional)</label>
          <textarea v-model="formResolucao.obs" rows="2" placeholder="Ex.: cliente cadastrado com sucesso, código C200..."></textarea>
        </div>
        <div class="modal-botoes">
          <button class="btn btn-secondary" @click="fecharConcluir" :disabled="processandoId">Cancelar</button>
          <button class="btn btn-success" @click="confirmarConcluir" :disabled="processandoId">
            {{ processandoId ? 'Salvando...' : '✓ Concluir' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Modal Recusar -->
    <div v-if="modalRecusar" class="modal-overlay" @click.self="fecharRecusar">
      <div class="modal-card">
        <h3>✕ Recusar solicitação</h3>
        <p class="modal-sub">Cliente: <strong>{{ modalRecusar.cliente_nome }}</strong></p>
        <div class="field">
          <label>Motivo da recusa *</label>
          <textarea v-model="formResolucao.obs" rows="2" placeholder="Ex.: cliente já existe na base com outro código..."></textarea>
        </div>
        <div class="modal-botoes">
          <button class="btn btn-secondary" @click="fecharRecusar" :disabled="processandoId">Cancelar</button>
          <button class="btn btn-danger" @click="confirmarRecusar" :disabled="processandoId || !formResolucao.obs.trim()">
            {{ processandoId ? 'Salvando...' : '✕ Recusar' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'

const router = useRouter()

const statusList = [
  { value: 'aberta', label: 'Abertas' },
  { value: 'em_andamento', label: 'Em andamento' },
  { value: 'concluida', label: 'Concluídas' },
  { value: 'recusada', label: 'Recusadas' },
  { value: '', label: 'Todas' },
]
const tipoList = [
  { value: '', label: 'Todos' },
  { value: 'novo_cliente', label: 'Cadastro' },
  { value: 'atualizar_contato', label: 'Contato' },
]

const solicitacoes = ref([])
const contagens = ref({})
const ehEquipe = ref(false)
const loading = ref(false)
const filtroStatus = ref('aberta')
const filtroTipo = ref('')
const processandoId = ref(null)
const msg = ref('')
const msgTipo = ref('ok')

const modalConcluir = ref(null)
const modalRecusar = ref(null)
const formResolucao = ref({ obs: '' })

const filtroLabel = computed(() => {
  const s = statusList.find(x => x.value === filtroStatus.value)
  return s ? s.label.toLowerCase() : ''
})

onMounted(() => carregar())

async function carregar() {
  loading.value = true
  try {
    const data = await api.solicitacoes.listar({
      status: filtroStatus.value || null,
      tipo: filtroTipo.value || null
    })
    ehEquipe.value = data.eh_equipe
    solicitacoes.value = data.solicitacoes || []
    contagens.value = {
      aberta: 0, em_andamento: 0, concluida: 0, recusada: 0
    }
    for (const s of solicitacoes.value) {
      if (contagens.value[s.status] != null) contagens.value[s.status]++
    }
  } catch (e) {
    msg.value = 'Erro ao carregar: ' + e.message
    msgTipo.value = 'erro'
  } finally {
    loading.value = false
  }
}

function mudarFiltroStatus(v) {
  filtroStatus.value = v
  carregar()
}

async function mudarStatus(s, status) {
  processandoId.value = s.id
  msg.value = ''
  try {
    await api.solicitacoes.status(s.id, { status })
    msg.value = 'Status atualizado.'
    msgTipo.value = 'ok'
    await carregar()
  } catch (e) {
    msg.value = 'Erro: ' + e.message
    msgTipo.value = 'erro'
  } finally {
    processandoId.value = null
  }
}

function abrirConcluir(s) {
  modalConcluir.value = s
  formResolucao.value.obs = ''
}
function fecharConcluir() { modalConcluir.value = null }
async function confirmarConcluir() {
  await resolver(modalConcluir.value, 'concluida')
}

function abrirRecusar(s) {
  modalRecusar.value = s
  formResolucao.value.obs = ''
}
function fecharRecusar() { modalRecusar.value = null }
async function confirmarRecusar() {
  await resolver(modalRecusar.value, 'recusada')
}

async function resolver(s, status) {
  if (!s) return
  processandoId.value = s.id
  msg.value = ''
  try {
    await api.solicitacoes.status(s.id, {
      status,
      observacao_resolucao: formResolucao.value.obs.trim() || null
    })
    modalConcluir.value = null
    modalRecusar.value = null
    msg.value = status === 'concluida' ? 'Solicitação concluída!' : 'Solicitação recusada.'
    msgTipo.value = 'ok'
    await carregar()
  } catch (e) {
    msg.value = 'Erro: ' + e.message
    msgTipo.value = 'erro'
  } finally {
    processandoId.value = null
  }
}

function cadastrarCliente(s) {
  const q = new URLSearchParams()
  if (s.cliente_nome) q.set('nome', s.cliente_nome)
  if (s.cliente_codigo) q.set('codigo', s.cliente_codigo)
  if (s.descricao) q.set('obs', s.descricao)
  router.push(`/clientes/cadastrar${q.toString() ? '?' + q.toString() : ''}`)
}

function editarCliente(s) {
  if (!s.cliente_id) return
  router.push(`/clientes/editar?cliente=${s.cliente_id}`)
}

function statusLabel(status) {
  return {
    aberta: 'Aberta',
    em_andamento: 'Em andamento',
    concluida: 'Concluída',
    recusada: 'Recusada'
  }[status] || status
}

function formatarData(iso) {
  if (!iso) return '—'
  try { return new Date(iso).toLocaleString('pt-BR') } catch { return iso }
}

function nomeComEmpresa(nome, empresa) {
  const n = nome || ''
  const e = empresa || ''
  return e ? `${n} (${e})` : n
}
</script>

<style scoped>
.page { padding: 1.5rem 1rem 2.5rem; }
.container { max-width: 900px; margin: 0 auto; }
.page-head { margin-bottom: 1rem; }
.page-head h1 { font-size: 1.5rem; font-weight: 700; color: #0f172a; }
.page-head p { color: #64748b; font-size: 0.88rem; margin-top: 0.2rem; }

.filtros { margin-bottom: 1rem; }
.filtros-status { display: flex; gap: 0.4rem; flex-wrap: wrap; }
.filtros-tipo { display: flex; gap: 0.4rem; margin-top: 0.5rem; flex-wrap: wrap; }
.btn-status {
  padding: 0.4rem 0.85rem; border-radius: 8px; cursor: pointer;
  background: #fff; border: 1px solid #dbe2ee; color: #475569;
  font-size: 0.85rem; font-weight: 600; transition: all 0.15s;
}
.btn-status:hover { background: #eef6ff; border-color: #1f5bf0; color: #1f5bf0; }
.btn-status.active { background: #1f5bf0; color: #fff; border-color: #1f5bf0; }
.btn-status .count {
  display: inline-block; padding: 0.05rem 0.4rem; margin-left: 0.35rem;
  border-radius: 999px; background: rgba(255,255,255,0.25); font-size: 0.72rem;
}
.btn-status:not(.active) .count { background: #e2e8f0; color: #475569; }

.placeholder { text-align: center; padding: 2.5rem 1rem; color: #94a3b8; }
.placeholder .empty-icon { font-size: 2.2rem; margin-bottom: 0.4rem; }
.placeholder p { font-size: 0.85rem; }

.lista { display: flex; flex-direction: column; gap: 0.9rem; }
.card { background: #fff; border-radius: 14px; padding: 1rem 1.2rem; box-shadow: 0 8px 24px -12px rgba(20,40,90,0.18); border: 1px solid #eef2f8; }
.solic { border-left: 4px solid #1f5bf0; }
.solic:has(.status-concluida) { border-left-color: #15803d; }
.solic:has(.status-recusada) { border-left-color: #dc2626; }

.sol-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 1rem; flex-wrap: wrap; }
.sol-tags { display: flex; gap: 0.4rem; flex-wrap: wrap; }
.tag { display: inline-block; padding: 0.18rem 0.5rem; border-radius: 6px; font-size: 0.7rem; font-weight: 700; }
.tag-novo_cliente { background: #dbeafe; color: #1d4ed8; }
.tag-atualizar_contato { background: #dcfce7; color: #15803d; }
.status-tag { display: inline-block; padding: 0.18rem 0.5rem; border-radius: 6px; font-size: 0.7rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.03em; }
.status-aberta { background: #fef3c7; color: #b45309; }
.status-em_andamento { background: #dbeafe; color: #1d4ed8; }
.status-concluida { background: #dcfce7; color: #15803d; }
.status-recusada { background: #fee2e2; color: #b91c1c; }

.sol-meta { font-size: 0.76rem; color: #64748b; display: flex; flex-direction: column; align-items: flex-end; gap: 0.15rem; }
.campo-row strong { color: #1d2a4d; }

.sol-cliente { font-size: 1.05rem; font-weight: 700; color: #0f172a; margin: 0.6rem 0 0.3rem; display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; }
.codigo { background: #f1f5f9; padding: 0.1rem 0.45rem; border-radius: 5px; font-size: 0.78rem; }

.sol-desc { font-size: 0.88rem; color: #334155; background: #f8fafc; border: 1px solid #eef2f8; border-radius: 8px; padding: 0.6rem 0.75rem; white-space: pre-wrap; margin: 0.3rem 0 0; }
.sol-resolucao { font-size: 0.82rem; color: #475569; background: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 8px; padding: 0.5rem 0.7rem; margin: 0.6rem 0 0; }
.solic:has(.status-recusada) .sol-resolucao { background: #fef2f2; border-color: #fecaca; }

.acoes-sol { display: flex; gap: 0.5rem; margin-top: 0.8rem; flex-wrap: wrap; }

.btn { padding: 0.5rem 1rem; border-radius: 9px; cursor: pointer; font-weight: 600; font-size: 0.85rem; border: none; }
.btn-primary { background: linear-gradient(135deg, #3479fb, #1746dc); color: #fff; box-shadow: 0 8px 18px -8px rgba(23,70,220,0.5); }
.btn-secondary { background: #eef6ff; color: #1746dc; border: 1px solid #bcdcff; }
.btn-success { background: #dcfce7; color: #15803d; border: 1px solid #86efac; }
.btn-danger { background: #fee2e2; color: #b91c1c; border: 1px solid #fecaca; }
.btn:disabled { opacity: 0.6; cursor: not-allowed; }

.msg { display: block; margin-top: 1rem; font-size: 0.88rem; }
.msg.ok { color: #15803d; }
.msg.erro { color: #b91c1c; }

/* Modais */
.modal-overlay {
  position: fixed; inset: 0; background: rgba(15, 23, 42, 0.55);
  display: flex; align-items: center; justify-content: center; padding: 1rem;
  z-index: 1000; backdrop-filter: blur(2px); overflow-y: auto;
}
.modal-card {
  background: #fff; border-radius: 16px; padding: 1.3rem;
  max-width: 460px; width: 100%; max-height: calc(100vh - 2rem); overflow-y: auto; margin: auto;
  box-shadow: 0 30px 70px -20px rgba(15, 23, 42, 0.45);
  animation: modal-in 0.16s ease-out;
}
.modal-card h3 { font-size: 1.05rem; font-weight: 700; color: #0f172a; margin-bottom: 0.35rem; }
.modal-sub { font-size: 0.82rem; color: #64748b; margin-bottom: 0.8rem; }
.modal-card .field label { display: block; font-size: 0.78rem; font-weight: 600; color: #475569; margin-bottom: 0.3rem; }
.modal-card textarea {
  width: 100%; padding: 0.5rem 0.7rem; border: 1px solid #dbe2ee; border-radius: 8px;
  font-size: 0.9rem; outline: none; background: #fff; box-sizing: border-box; font-family: inherit; resize: vertical;
}
.modal-card textarea:focus { border-color: #1f5bf0; box-shadow: 0 0 0 4px rgba(31,91,240,0.12); }
.modal-botoes { display: flex; gap: 0.6rem; justify-content: flex-end; margin-top: 1rem; flex-wrap: wrap; }
@keyframes modal-in {
  from { opacity: 0; transform: translateY(8px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}
</style>