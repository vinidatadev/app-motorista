<template>
  <div class="page">
    <div class="container">
      <div class="page-head">
        <h1>Aprovações de Endereço</h1>
        <p>Submissões enviadas pelos motoristas aguardando revisão.</p>
      </div>

      <!-- Filtros de status -->
      <div class="filtros-status">
        <button
          v-for="s in statusList"
          :key="s.value"
          :class="['btn-status', { active: filtroStatus === s.value }]"
          @click="mudarFiltro(s.value)"
        >{{ s.label }} <span class="count">{{ contagens[s.value] || 0 }}</span></button>
      </div>

      <!-- Filtro por empresa (do motorista que solicitou) -->
      <div class="filtros-empresa">
        <span class="filtro-label">Empresa do solicitante:</span>
        <button
          v-for="e in empresaList"
          :key="e.value"
          :class="['btn-status', { active: filtroEmpresa === e.value }]"
          @click="mudarFiltroEmpresa(e.value)"
        >{{ e.label }}</button>
      </div>

      <div v-if="loading" class="placeholder">Carregando...</div>
      <div v-else-if="!alteracoes.length" class="placeholder">
        <div class="empty-icon">✅</div>
        <p>Nenhuma submissão {{ filtroLabel }}</p>
      </div>

      <!-- Lista de submissoes -->
      <div v-else class="lista">
        <article v-for="alt in alteracoes" :key="alt.id" class="card submissao">
          <header class="sub-head">
            <div>
              <span :class="['status-tag', 'status-' + alt.status]">{{ statusLabel(alt.status) }}</span>
              <h2>{{ alt.cliente_codigo || '—' }} · {{ alt.cliente_nome }}</h2>
            </div>
            <div class="sub-meta">
              <span class="campo-row"><strong>Submetido por:</strong> {{ nomeComEmpresa(alt.motorista_nome, alt.motorista_empresa) }}</span>
              <span class="campo-row"><strong>Em:</strong> {{ formatarData(alt.created_at) }}</span>
              <span v-if="alt.revisado_at" class="campo-row"><strong>Revisado em:</strong> {{ formatarData(alt.revisado_at) }}</span>
              <span v-if="alt.revisado_por_nome" class="campo-row"><strong>Revisado por:</strong> {{ nomeComEmpresa(alt.revisado_por_nome, alt.revisado_por_empresa) }}</span>
            </div>
          </header>

          <div v-if="alt.observacao_revisao" class="obs-revisao">
            <strong>Obs. da revisão:</strong> {{ alt.observacao_revisao }}
          </div>

          <!-- Diff com os dados atuais (apenas para pendentes) -->
          <details v-if="alt.status === 'pendente'" class="diff-block" open>
            <summary>Comparar proposta x dados atuais</summary>
            <div class="diff-grid">
              <div class="diff-col diff-atual">
                <h3>📍 Atual (aprovado)</h3>
                <dl>
                  <div v-for="campo in diffCamposCliente" :key="campo.key">
                    <dt>{{ campo.label }}</dt>
                    <dd>{{ atual(alt, campo.key) || '—' }}</dd>
                  </div>
                </dl>
                <div v-if="enderecosAtuais(alt).length" class="enderecos-diff">
                  <div v-for="(e, i) in enderecosAtuais(alt)" :key="i" class="endereco-diff-card">
                    <h4>📍 {{ e.nome || `Endereço ${i + 1}` }}</h4>
                    <div v-for="f in camposEndereco" :key="f.key">
                      <dt>{{ f.label }}</dt><dd>{{ valStr(e[f.key]) }}</dd>
                    </div>
                    <div v-if="e.contatos && e.contatos.length" class="contatos-diff">
                      <strong>Contatos:</strong>
                      <span v-for="(ct, j) in e.contatos" :key="j">
                        {{ ct.nome }}<template v-if="ct.telefone"> ({{ ct.telefone }})</template>{{ j < e.contatos.length - 1 ? ' · ' : '' }}
                      </span>
                    </div>
                    <p v-else class="sem-contato">Sem contatos.</p>
                  </div>
                </div>
                <p v-else class="sem-contato">Sem endereços cadastrados.</p>
              </div>
              <div class="diff-col diff-novo">
                <h3>✍️ Proposto ({{ nomeComEmpresa(alt.motorista_nome, alt.motorista_empresa) }})</h3>
                <dl>
                  <div v-for="campo in diffCamposCliente" :key="campo.key" :class="{ changed: mudou(alt, campo.key) }">
                    <dt>{{ campo.label }}</dt>
                    <dd>{{ novo(alt, campo.key) || '—' }}</dd>
                  </div>
                </dl>
                <div v-if="enderecosPropostos(alt).length" class="enderecos-diff">
                  <div v-for="(e, i) in enderecosPropostos(alt)" :key="i" class="endereco-diff-card" :class="{ changed: enderecoMudou(alt, i) }">
                    <h4>📍 {{ e.nome || `Endereço ${i + 1}` }}</h4>
                    <div v-for="f in camposEndereco" :key="f.key">
                      <dt>{{ f.label }}</dt><dd>{{ valStr(e[f.key]) }}</dd>
                    </div>
                    <div v-if="e.contatos && e.contatos.length" class="contatos-diff">
                      <strong>Contatos:</strong>
                      <span v-for="(ct, j) in e.contatos" :key="j">
                        {{ ct.nome }}<template v-if="ct.telefone"> ({{ ct.telefone }})</template>{{ j < e.contatos.length - 1 ? ' · ' : '' }}
                      </span>
                    </div>
                    <p v-else class="sem-contato">Sem contatos.</p>
                  </div>
                </div>
                <p v-else class="sem-contato">Nenhum endereço proposto.</p>
              </div>
            </div>
          </details>

          <!-- Snapshot final (para ja-revisados) -->
          <details v-else class="diff-block">
            <summary>Snapshot enviado</summary>
            <dl class="snap-grid">
              <div v-for="campo in diffCamposCliente" :key="campo.key">
                <dt>{{ campo.label }}</dt>
                <dd>{{ novo(alt, campo.key) || '—' }}</dd>
              </div>
            </dl>
            <div v-if="enderecosPropostos(alt).length" class="enderecos-diff">
              <div v-for="(e, i) in enderecosPropostos(alt)" :key="i" class="endereco-diff-card">
                <h4>📍 {{ e.nome || `Endereço ${i + 1}` }}</h4>
                <div v-for="f in camposEndereco" :key="f.key">
                  <dt>{{ f.label }}</dt><dd>{{ valStr(e[f.key]) }}</dd>
                </div>
                <div v-if="e.contatos && e.contatos.length" class="contatos-diff">
                  <strong>Contatos:</strong>
                  <span v-for="(ct, j) in e.contatos" :key="j">
                    {{ ct.nome }}<template v-if="ct.telefone"> ({{ ct.telefone }})</template>{{ j < e.contatos.length - 1 ? ' · ' : '' }}
                  </span>
                </div>
              </div>
            </div>
          </details>

          <!-- Acoes (somente pendentes) -->
          <div v-if="alt.status === 'pendente'" class="acoes-sub">
            <button class="btn btn-primary" @click="abrirEditar(alt)" :disabled="processandoId === alt.id">✏️ Editar e aprovar</button>
            <button class="btn btn-success" @click="aprovar(alt)" :disabled="processandoId === alt.id">✓ Aprovar</button>
            <button class="btn btn-danger" @click="abrirRecusar(alt)" :disabled="processandoId === alt.id">✕ Recusar</button>
          </div>
        </article>
      </div>

      <span v-if="msg" :class="['msg', msgTipo]">{{ msg }}</span>
    </div>

    <!-- Modal Editar (snapshot) -->
    <div v-if="modalEditar" class="modal-overlay" @click.self="fecharEditar">
      <div class="modal-card modal-editar">
        <h3>Editar antes de aprovar</h3>
        <p class="modal-sub">Ajuste os campos que quiser. Ao confirmar, o cliente será atualizado e a submissão marcada como <strong>editada/aprovada</strong>.</p>
        <div class="form-editar-grid">
          <div class="field full">
            <label>Nome / Razão Social</label>
            <input v-model="formEditar.nome_razao_social" />
          </div>
          <div class="field"><label>Telefone</label><input v-model="formEditar.telefone" placeholder="(00) 0 0000-0000" /></div>
          <div class="field"><label>Pessoa de Contato</label><input v-model="formEditar.pessoa_contato" /></div>
          <div class="field"><label>CEP</label><input v-model="formEditar.cep" /></div>
          <div class="field"><label>Número</label><input v-model="formEditar.numero" /></div>
          <div class="field col2"><label>Rua</label><input v-model="formEditar.rua" /></div>
          <div class="field"><label>Bairro</label><input v-model="formEditar.bairro" /></div>
          <div class="field"><label>Cidade</label><input v-model="formEditar.cidade" /></div>
          <div class="field"><label>Estado (UF)</label><input v-model="formEditar.estado" maxlength="2" class="uf" /></div>
          <div class="field col2"><label>Ponto de Referência</label><input v-model="formEditar.ponto_referencia" /></div>
          <div class="field full"><label>Observação</label><textarea v-model="formEditar.observacao" rows="2"></textarea></div>
        </div>
        <div class="modal-botoes">
          <button class="btn btn-secondary" @click="fecharEditar" :disabled="processandoId">Cancelar</button>
          <button class="btn btn-primary" @click="salvarEditar" :disabled="processandoId">
            {{ processandoId ? 'Salvando...' : '✓ Salvar e aprovar' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Modal Recusar -->
    <div v-if="modalRecusar" class="modal-overlay" @click.self="fecharRecusar">
      <div class="modal-card modal-recusar">
        <h3>Recusar submissão</h3>
        <p class="modal-sub">O endereço atual do cliente será mantido. Informe um motivo (opcional) que ficará registrado para o motorista.</p>
        <div class="field full">
          <label>Motivo da recusa</label>
          <textarea v-model="formRecusar.observacao" rows="3" placeholder="Ex.: CEP inválido, endereço duplicado..."></textarea>
        </div>
        <div class="modal-botoes">
          <button class="btn btn-secondary" @click="fecharRecusar" :disabled="processandoId">Cancelar</button>
          <button class="btn btn-danger" @click="confirmarRecusar" :disabled="processandoId">
            {{ processandoId ? 'Recusando...' : '✕ Recusar' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { api } from '../api'

const diffCamposCliente = [
  { key: 'nome_razao_social', label: 'Nome / Razão Social' },
  { key: 'telefone', label: 'Telefone' },
  { key: 'pessoa_contato', label: 'Pessoa de contato' },
]

const camposEndereco = [
  { key: 'rua', label: 'Rua' },
  { key: 'numero', label: 'Número' },
  { key: 'bairro', label: 'Bairro' },
  { key: 'cep', label: 'CEP' },
  { key: 'cidade', label: 'Cidade' },
  { key: 'estado', label: 'UF' },
  { key: 'latitude', label: 'Latitude' },
  { key: 'longitude', label: 'Longitude' },
  { key: 'ponto_referencia', label: 'Ponto de referência' },
  { key: 'observacao', label: 'Observação' },
]

function valStr(v) {
  if (v === null || v === undefined || v === '') return '—'
  return String(v)
}

function enderecosPropostos(alt) {
  return alt.snapshot?.enderecos || []
}
function enderecosAtuais(alt) {
  return alt.cliente_atual?.enderecos || []
}
function enderecoMudou(alt, i) {
  const p = enderecosPropostos(alt)[i]
  const a = enderecosAtuais(alt)[i]
  if (!p) return false
  if (!a) return true
  const keys = ['nome', ...camposEndereco.map(c => c.key), 'contatos']
  for (const k of keys) {
    if (JSON.stringify(p[k] ?? null) !== JSON.stringify(a[k] ?? null)) return true
  }
  return false
}

const statusList = [
  { value: 'pendente', label: 'Pendentes' },
  { value: 'aprovado', label: 'Aprovadas' },
  { value: 'editado', label: 'Editadas' },
  { value: 'recusado', label: 'Recusadas' },
  { value: '', label: 'Todas' },
]

const empresaList = [
  { value: '', label: 'Todas' },
  { value: 'AC', label: 'AC' },
  { value: 'SIN', label: 'SIN' },
]

const alteracoes = ref([])
const contagens = ref({})
const loading = ref(false)
const filtroStatus = ref('pendente')
const filtroEmpresa = ref('')
const processandoId = ref(null)
const msg = ref('')
const msgTipo = ref('ok')

const modalEditar = ref(false)
const modalRecusar = ref(false)
const submissaoAtiva = ref(null)
const formEditar = reactive({})
const formRecusar = reactive({ observacao: '' })

const filtroLabel = computed(() => {
  const s = statusList.find(x => x.value === filtroStatus.value)
  return s ? s.label.toLowerCase() : ''
})

onMounted(() => carregar())

async function carregar() {
  loading.value = true
  try {
    // Busca tudo uma vez (filtrado por empresa) e conta por status localmente
    const todas = await api.clientes.alteracoes.listar(null, filtroEmpresa.value || null)
    contagens.value = {
      pendente: todas.filter(x => x.status === 'pendente').length,
      aprovado: todas.filter(x => x.status === 'aprovado').length,
      editado: todas.filter(x => x.status === 'editado').length,
      recusado: todas.filter(x => x.status === 'recusado').length,
    }
    alteracoes.value = filtroStatus.value
      ? todas.filter(x => x.status === filtroStatus.value)
      : todas
  } finally {
    loading.value = false
  }
}

function mudarFiltro(s) {
  filtroStatus.value = s
  carregar()
}

function mudarFiltroEmpresa(e) {
  filtroEmpresa.value = e
  carregar()
}

function atual(alt, key) {
  // Dados atuais do cliente (enviados pelo backend em cliente_atual)
  const v = alt.cliente_atual?.[key]
  if (v === null || v === undefined) return ''
  return String(v)
}

function novo(alt, key) {
  const v = alt.snapshot?.[key]
  if (v === null || v === undefined) return ''
  return String(v)
}

function mudou(alt, key) {
  // Destaca no "proposto" os campos que de fato diferem do endereco atual
  const a = atual(alt, key).trim()
  const n = novo(alt, key).trim()
  if (n === '') return false
  return a !== n
}

function statusLabel(s) {
  return ({ pendente: 'Pendente', aprovado: 'Aprovada', editado: 'Editada', recusado: 'Recusada' })[s] || s
}

// Exibe nome do usuario com a empresa para identificacao (ex: "Joao (AC)")
function nomeComEmpresa(nome, empresa) {
  const n = nome || ''
  const e = empresa || ''
  return e ? `${n} (${e})` : n
}

function formatarData(iso) {
  if (!iso) return '—'
  try { return new Date(iso).toLocaleString('pt-BR') } catch { return iso }
}

async function aprovar(alt) {
  if (!confirm(`Aprovar a submissão de ${alt.motorista_nome}? O endereço será atualizado.`)) return
  processandoId.value = alt.id
  msg.value = ''
  try {
    await api.clientes.alteracoes.aprovar(alt.id)
    msg.value = 'Submissão aprovada!'
    msgTipo.value = 'ok'
    await carregar()
  } catch (e) {
    msg.value = 'Erro: ' + e.message
    msgTipo.value = 'erro'
  } finally {
    processandoId.value = null
  }
}

function abrirRecusar(alt) {
  submissaoAtiva.value = alt
  formRecusar.observacao = ''
  modalRecusar.value = true
}
function fecharRecusar() {
  modalRecusar.value = false
  submissaoAtiva.value = null
}
async function confirmarRecusar() {
  if (!submissaoAtiva.value) return
  processandoId.value = submissaoAtiva.value.id
  try {
    await api.clientes.alteracoes.recusar(submissaoAtiva.value.id, formRecusar.observacao || null)
    msg.value = 'Submissão recusada.'
    msgTipo.value = 'ok'
    fecharRecusar()
    await carregar()
  } catch (e) {
    msg.value = 'Erro: ' + e.message
    msgTipo.value = 'erro'
  } finally {
    processandoId.value = null
  }
}

function abrirEditar(alt) {
  submissaoAtiva.value = alt
  const s = alt.snapshot || {}
  Object.assign(formEditar, {
    nome_razao_social: s.nome_razao_social || '',
    telefone: s.telefone || '',
    pessoa_contato: s.pessoa_contato || '',
    cep: s.cep || '',
    rua: s.rua || '',
    numero: s.numero || '',
    bairro: s.bairro || '',
    cidade: s.cidade || '',
    estado: s.estado || '',
    latitude: s.latitude,
    longitude: s.longitude,
    ponto_referencia: s.ponto_referencia || '',
    observacao: s.observacao || '',
  })
  modalEditar.value = true
}
function fecharEditar() {
  modalEditar.value = false
  submissaoAtiva.value = null
}
async function salvarEditar() {
  if (!submissaoAtiva.value) return
  processandoId.value = submissaoAtiva.value.id
  try {
    const payload = { ...formEditar }
    // Remove nulls/strings vazias para nao sobrescrever com vazio se_Requeste nao veio preenchido
    Object.keys(payload).forEach(k => {
      if (payload[k] === '' || payload[k] == null) delete payload[k]
    })
    await api.clientes.alteracoes.editar(submissaoAtiva.value.id, payload)
    msg.value = 'Editado e aprovado com sucesso!'
    msgTipo.value = 'ok'
    fecharEditar()
    await carregar()
  } catch (e) {
    msg.value = 'Erro: ' + e.message
    msgTipo.value = 'erro'
  } finally {
    processandoId.value = null
  }
}
</script>

<style scoped>
.page { padding: 1.5rem 1rem 2.5rem; }
.container { max-width: 900px; margin: 0 auto; }
.page-head { margin-bottom: 1rem; }
.page-head h1 { font-size: 1.5rem; font-weight: 700; color: #0f172a; }
.page-head p { color: #64748b; font-size: 0.88rem; margin-top: 0.2rem; }

.filtros-status { display: flex; gap: 0.4rem; margin-bottom: 1rem; flex-wrap: wrap; }
.filtros-empresa { display: flex; align-items: center; gap: 0.4rem; margin: -0.4rem 0 1rem; flex-wrap: wrap; }
.filtro-label { font-size: 0.78rem; font-weight: 600; color: #64748b; }
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

.lista { display: flex; flex-direction: column; gap: 1rem; }
.card { background: #fff; border-radius: 14px; padding: 1.1rem 1.25rem; box-shadow: 0 8px 24px -12px rgba(20,40,90,0.18); border: 1px solid #eef2f8; }
.submissao { border-left: 4px solid #f59e0b; }

.sub-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 1rem; flex-wrap: wrap; margin-bottom: 0.7rem; }
.sub-head h2 { font-size: 1.05rem; font-weight: 700; color: #0f172a; margin-top: 0.3rem; }
.sub-meta { font-size: 0.78rem; color: #64748b; display: flex; flex-direction: column; align-items: flex-end; gap: 0.15rem; }
.campo-row strong { color: #1d2a4d; }

.status-tag { display: inline-block; padding: 0.18rem 0.5rem; border-radius: 6px; font-size: 0.72rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; }
.status-pendente { background: #fef3c7; color: #b45309; }
.status-aprovado { background: #dcfce7; color: #15803d; }
.status-editado { background: #dbeafe; color: #1d4ed8; }
.status-recusado { background: #fee2e2; color: #b91c1c; }

.obs-revisao { padding: 0.55rem 0.75rem; margin: 0.6rem 0; background: #fef2f2; color: #b91c1c; border-radius: 8px; font-size: 0.82rem; border: 1px solid #fecaca; }

.diff-block { margin-top: 0.7rem; background: #f8fafc; border-radius: 10px; padding: 0.75rem; border: 1px solid #eef2f8; }
.diff-block summary { cursor: pointer; font-weight: 600; font-size: 0.85rem; color: #1d2a4d; }
.diff-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0.8rem; margin-top: 0.6rem; }
@media (max-width: 600px) { .diff-grid { grid-template-columns: 1fr; } }
.diff-col h3 { font-size: 0.78rem; font-weight: 700; margin-bottom: 0.35rem; padding-bottom: 0.3rem; border-bottom: 2px solid #e2e8f0; }
.diff-atual h3 { color: #64748b; }
.diff-novo h3 { color: #1d4ed8; }
.diff-col dl { font-size: 0.82rem; }
.diff-col dt { color: #94a3b8; font-size: 0.7rem; text-transform: uppercase; margin-top: 0.3rem; }
.diff-col dd { color: #1d2a4d; margin-left: 0; }
.diff-novo dl > div.changed { background: #efbff8; padding: 0.2rem 0.4rem; border-radius: 5px; margin: 0 -0.4rem; }
.diff-novo dl > div.changed dd { color: #1746dc; font-weight: 600; }
.diff-novo dl > div.changed dt { color: #1d4ed8; }

.snap-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0.3rem 1rem; font-size: 0.82rem; margin-top: 0.5rem; }
.snap-grid dt { color: #94a3b8; font-size: 0.7rem; text-transform: uppercase; }
.snap-grid dd { color: #1d2a4d; margin-left: 0; }

.enderecos-diff { display: flex; flex-direction: column; gap: 0.6rem; margin-top: 0.7rem; }
.endereco-diff-card {
  border: 1px solid #e2e8f0; border-radius: 10px; padding: 0.6rem 0.75rem;
  background: #fff;
}
.endereco-diff-card h4 { font-size: 0.82rem; font-weight: 700; color: #1d2a4d; margin: 0 0 0.35rem; }
.endereco-diff-card dt { color: #94a3b8; font-size: 0.66rem; text-transform: uppercase; display: inline; }
.endereco-diff-card dd { color: #1d2a4d; display: inline; margin-left: 0.3rem; }
.endereco-diff-card.changed {
  background: #fff7ed; border-color: #fdba74;
  box-shadow: 0 0 0 2px rgba(253, 186, 116, 0.25);
}
.endereco-diff-card.changed dd, .endereco-diff-card.changed h4 { color: #c2410c; }
.contatos-diff { margin-top: 0.4rem; font-size: 0.78rem; color: #334155; }
.contatos-diff strong { color: #64748b; font-weight: 600; }
.sem-contato { font-size: 0.75rem; color: #94a3b8; font-style: italic; margin: 0.3rem 0 0; }

.acoes-sub { display: flex; gap: 0.5rem; margin-top: 0.9rem; flex-wrap: wrap; }

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
.modal-overlay { position: fixed; inset: 0; background: rgba(15,23,42,0.55); display: flex; align-items: center; justify-content: center; padding: 1rem; z-index: 1000; backdrop-filter: blur(2px); overflow-y: auto; }
.modal-card { background: #fff; border-radius: 16px; padding: 1.4rem; max-width: 540px; width: 100%; max-height: calc(100vh - 2rem); overflow-y: auto; margin: auto; box-shadow: 0 30px 70px -20px rgba(15,23,42,0.45); }
.modal-card h3 { font-size: 1.1rem; font-weight: 700; color: #0f172a; margin-bottom: 0.3rem; }
.modal-sub { font-size: 0.85rem; color: #64748b; margin-bottom: 0.8rem; }

.form-editar-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 0.4rem 0.7rem; }
.form-editar-grid .full { grid-column: 1 / -1; }
.form-editar-grid .col2 { grid-column: span 2; }
@media (max-width: 600px) { .form-editar-grid { grid-template-columns: 1fr; } .form-editar-grid .col2 { grid-column: auto; } }
.field { margin-bottom: 0.55rem; }
.field label { display: block; font-size: 0.75rem; font-weight: 600; color: #475569; margin-bottom: 0.2rem; }
.field input, .field textarea {
  width: 100%; padding: 0.45rem 0.65rem; border: 1px solid #dbe2ee; border-radius: 7px;
  font-size: 0.88rem; outline: none; background: #fff; box-sizing: border-box; font-family: inherit;
}
.field input:focus, .field textarea:focus { border-color: #1f5bf0; box-shadow: 0 0 0 3px rgba(31,91,240,0.12); }
.field textarea { resize: vertical; min-height: 50px; }

.modal-botoes { display: flex; gap: 0.6rem; justify-content: flex-end; margin-top: 1rem; flex-wrap: wrap; }
.uf { text-transform: uppercase; }
</style>