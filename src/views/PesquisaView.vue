<template>
  <div class="page">
    <div class="container">
      <div class="page-head">
        <h1>Pesquisa de Clientes</h1>
        <p>Filtre por Estado, Cidade ou diretamente pelo Cliente — independentes entre si.</p>
      </div>

      <div class="grid">
        <!-- Coluna de filtros -->
        <section class="card filtros">
          <h2 class="section-title">Filtros</h2>

          <div class="field">
            <label>Estado (UF)</label>
            <select v-model="estadoSel" @change="onEstadoChange">
              <option value="">Todos</option>
              <option v-for="uf in estados" :key="uf" :value="uf">{{ uf }}</option>
            </select>
          </div>

          <div class="field">
            <label>Cidade</label>
            <select v-model="cidadeSel" @change="onClienteFilterChange">
              <option value="">Todas</option>
              <option v-for="c in cidades" :key="c" :value="c">{{ c }}</option>
            </select>
          </div>

          <div class="field">
            <label>Cliente</label>
            <input
              class="cliente-search"
              list="lista-clientes"
              v-model="clienteBusca"
              placeholder="Digite para buscar..."
              @change="onClienteSelecionado"
            />
            <datalist id="lista-clientes">
              <option v-for="c in clientesFiltrados" :key="c.id" :value="c.nome_razao_social">
                {{ c.cidade }}/{{ c.estado }}
              </option>
            </datalist>
          </div>

          <div class="contador">
            {{ clientesFiltrados.length }} cliente(s) encontrados
          </div>

          <div class="botoes-acao">
            <button v-if="clienteSelecionado && podeEditar" class="btn btn-primary mt" @click="irParaEdicao">
              ✏️ Editar
            </button>
            <button v-if="clienteSelecionado && podeDeletar" class="btn btn-danger mt" @click="excluirCliente">
              🗑 Excluir
            </button>
            <button v-if="clienteSelecionado" class="btn btn-secondary mt" @click="abrirModalContato">
              📞 Solicitar contato atualizado
            </button>
            <button v-if="clienteNaoEncontrado" class="btn btn-secondary mt" @click="abrirModalNovoCliente">
              📋 Não encontrei o cliente — abrir solicitação
            </button>
            <button v-if="podeExportar" class="btn btn-secondary mt" @click="exportarExcel" :disabled="exportando">
              {{ exportando ? 'Gerando...' : '📤 Exportar Excel' }}
            </button>
          </div>
        </section>

        <!-- Painel de detalhe readonly -->
        <section class="card detalhe">
          <div v-if="carregando" class="placeholder">Carregando...</div>

          <div v-else-if="!clienteSelecionado" class="placeholder">
            <div class="empty-icon">👁️</div>
            <h3>Nenhum cliente selecionado</h3>
            <p>Escolha um cliente nos filtros acima (ou pesquise pelo nome) para visualizar o cadastro.</p>
          </div>

          <div v-else class="detalhe-corpo">
            <div class="detalhe-head">
              <div>
                <span class="badge">{{ clienteSelecionado.estado || '--' }}</span>
                <span class="badge soft">{{ clienteSelecionado.cidade || '--' }}</span>
                <span v-if="clienteSelecionado.status_endereco === 'atualizando'" class="badge status-atualizando" title="Dados submetidos para aprovação">
                  ⏳ Atualização pendente
                </span>
              </div>
              <h2>{{ clienteSelecionado.nome_razao_social }}</h2>
            </div>

            <p v-if="clienteSelecionado.status_endereco === 'atualizando' && clienteSelecionado.alterado_por_nome" class="alt-por-info">
              ⏳ Submetido por <strong>{{ nomeComEmpresa(clienteSelecionado.alterado_por_nome, clienteSelecionado.alterado_por_empresa) }}</strong> em {{ formatarData(clienteSelecionado.alterado_em) }} — aguardando aprovação.
            </p>

            <dl class="grid-info">
              <div><dt>Telefone</dt><dd>{{ clienteSelecionado.telefone || '—' }}</dd></div>
              <div><dt>Pessoa de contato</dt><dd>{{ clienteSelecionado.pessoa_contato || '—' }}</dd></div>
              <div class="full">
                <dt>Atualizado por</dt>
                <dd v-if="clienteSelecionado.alterado_por_nome">
                  {{ nomeComEmpresa(clienteSelecionado.alterado_por_nome, clienteSelecionado.alterado_por_empresa) }}
                  <span class="alt-por-data">em {{ formatarData(clienteSelecionado.alterado_em || clienteSelecionado.updated_at) }}</span>
                </dd>
                <dd v-else>{{ formatarData(clienteSelecionado.updated_at) }}</dd>
              </div>
            </dl>

            <!-- Endereços e contatos -->
            <div class="enderecos-readonly">
              <h3>🏬 Endereços e contatos ({{ (clienteSelecionado.enderecos || []).length }})</h3>

              <div
                v-for="(end, i) in clienteSelecionado.enderecos || []"
                :key="end.id || i"
                class="endereco-card"
              >
                <div class="end-card-head">
                  <h4>📍 {{ end.nome || `Endereço ${i + 1}` }}</h4>
                  <span v-if="i === 0" class="tag-principal">Principal</span>
                </div>

                <dl class="end-grid">
                  <div><dt>CEP</dt><dd>{{ end.cep || '—' }}</dd></div>
                  <div><dt>Rua</dt><dd>{{ end.rua || '—' }}</dd></div>
                  <div><dt>Número</dt><dd>{{ end.numero || '—' }}</dd></div>
                  <div><dt>Bairro</dt><dd>{{ end.bairro || '—' }}</dd></div>
                  <div><dt>Cidade</dt><dd>{{ end.cidade || '—' }}</dd></div>
                  <div><dt>UF</dt><dd>{{ end.estado || '—' }}</dd></div>
                  <div v-if="end.latitude != null" class="full"><dt>Coordenadas</dt><dd>{{ end.latitude }}, {{ end.longitude }}</dd></div>
                  <div v-if="end.ponto_referencia" class="full"><dt>Ponto de referência</dt><dd>{{ end.ponto_referencia }}</dd></div>
                  <div v-if="end.observacao" class="full"><dt>Observação</dt><dd class="obs">{{ end.observacao }}</dd></div>
                </dl>

                <!-- Contatos do endereço -->
                <div v-if="(end.contatos || []).length" class="contatos-lista">
                  <div v-for="ct in end.contatos" :key="ct.id" class="contato-chip">
                    <span class="contato-nome">{{ ct.nome }}</span>
                    <span v-if="ct.telefone" class="contato-tel">{{ ct.telefone }}</span>
                  </div>
                </div>
                <p v-else class="sem-contato">Sem contatos cadastrados.</p>

                <!-- Navegação -->
                <div class="endereco-full">
                  <label>Navegar para este endereço</label>
                  <div class="endereco-row">
                    <input :value="montarEndereco(end)" readonly class="endereco-input" />
                    <button class="btn btn-secondary btn-sm" @click="copiarEndereco(end, i)" :disabled="!montarEndereco(end)">
                      {{ copiadoIdx === i ? '✓ Copiado' : '⧉ Copiar' }}
                    </button>
                  </div>
                  <div v-if="temCoords(end) || montarEndereco(end)" class="nav-links">
                    <a :href="wazeUrlDe(end)" target="_blank" rel="noopener" class="nav-link waze" :class="{ disabled: wazeUrlDe(end) === '#' }">Waze ↗</a>
                    <a :href="mapsUrlDe(end)" target="_blank" rel="noopener" class="nav-link maps" :class="{ disabled: mapsUrlDe(end) === '#' }">Google Maps ↗</a>
                    <a :href="osmUrlDe(end)" target="_blank" rel="noopener" class="nav-link osm" :class="{ disabled: osmUrlDe(end) === '#' }">OpenStreetMap ↗</a>
                  </div>
                </div>
              </div>
            </div>

            <!-- Preview do mapa (primeiro endereço com coordenadas) -->
            <div v-if="primeiroComCoords" class="mapa-preview">
              <div ref="mapaEl" class="mapa" id="mapa-pesquisa"></div>
            </div>

            <!-- Fotos do local (somente leitura) -->
            <div v-if="clienteSelecionado.fotos && clienteSelecionado.fotos.length" class="fotos-readonly">
              <h3>📸 Fotos do local</h3>
              <div class="fotos-galeria">
                <a v-for="f in clienteSelecionado.fotos" :key="f.id" :href="f.url" target="_blank" rel="noopener" class="foto-item">
                  <img :src="f.url" :alt="`Foto ${f.id}`" loading="lazy" />
                </a>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  </div>

  <!-- Modal: solicitar cadastro de cliente novo -->
  <div v-if="modalNovo.aberto" class="modal-overlay" @click.self="fecharModalNovo">
    <div class="modal-card">
      <h3>📋 Solicitar cadastro de cliente</h3>
      <p class="modal-sub">Não encontramos esse cliente na base. Abra uma solicitação e o time de cadastro receberá e fará o registro.</p>
      <div class="field">
        <label>Nome do cliente *</label>
        <input v-model="modalNovo.cliente_nome" placeholder="Nome/Razão social informado pelo usuário" />
      </div>
      <div class="field">
        <label>Código (se souber)</label>
        <input v-model="modalNovo.cliente_codigo" placeholder="ex: C100" />
      </div>
      <div class="field">
        <label>Observação / o que você sabe</label>
        <textarea v-model="modalNovo.descricao" rows="3" placeholder="Ex.: o cliente mencionou que tem loja no bairro X, contato (85) 9 0000-0000..."></textarea>
      </div>
      <p v-if="modalNovo.erro" class="msg erro">{{ modalNovo.erro }}</p>
      <div class="modal-botoes">
        <button class="btn btn-secondary" @click="fecharModalNovo">Cancelar</button>
        <button class="btn btn-primary" @click="enviarSolicitacaoNovo" :disabled="modalNovo.enviando || !modalNovo.cliente_nome.trim()">
          {{ modalNovo.enviando ? 'Enviando...' : 'Abrir solicitação' }}
        </button>
      </div>
    </div>
  </div>

  <!-- Modal: solicitar contato atualizado -->
  <div v-if="modalContato.aberto" class="modal-overlay" @click.self="fecharModalContato">
    <div class="modal-card">
      <h3>📞 Solicitar contato atualizado</h3>
      <p class="modal-sub">Cliente: <strong>{{ modalContato.cliente_nome }}</strong></p>
      <div class="field">
        <label>Descrição *</label>
        <textarea v-model="modalContato.descricao" rows="3" placeholder="Ex.: liguei no telefone do cadastro e o número não existe mais — o novo é (85) 9 8888-7777..."></textarea>
      </div>
      <p v-if="modalContato.erro" class="msg erro">{{ modalContato.erro }}</p>
      <div class="modal-botoes">
        <button class="btn btn-secondary" @click="fecharModalContato">Cancelar</button>
        <button class="btn btn-primary" @click="enviarSolicitacaoContato" :disabled="modalContato.enviando || !modalContato.descricao.trim()">
          {{ modalContato.enviando ? 'Enviando...' : 'Abrir solicitação' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, reactive, onMounted, watch, nextTick, onBeforeUnmount } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import L from 'leaflet'
import markerIcon from 'leaflet/dist/images/marker-icon.png'
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png'
import markerShadow from 'leaflet/dist/images/marker-shadow.png'
import { api } from '../api'
import { temPermissao } from '../composables/useAuth'
import { tileUrl, tileAttribution, tileMaxZoom } from '../composables/useMapa'

delete L.Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({
  iconUrl: markerIcon,
  iconRetinaUrl: markerIcon2x,
  shadowUrl: markerShadow
})

const router = useRouter()
const route = useRoute()

// Permissoes (computadas pra reatividade ao login)
const podeEditar = computed(() => temPermissao('editar'))
const podeDeletar = computed(() => temPermissao('deletar'))
const podeExportar = computed(() => temPermissao('exportar'))
const exportando = ref(false)

const carregando = ref(false)
const todos = ref([])
const estados = ref([])

const estadoSel = ref('')
const cidadeSel = ref('')
const clienteBusca = ref('')
const clienteSelecionado = ref(null)

const mapaEl = ref(null)
let map = null
let marker = null

const copiado = ref(false)
const copiadoIdx = ref(-1)
let copiarTimeout = null

// Solicitações (abrir chamado)
const modalNovo = reactive({ aberto: false, cliente_nome: '', cliente_codigo: '', descricao: '', enviando: false, erro: '' })
const modalContato = reactive({ aberto: false, cliente_id: null, cliente_nome: '', descricao: '', enviando: false, erro: '' })

// O usuário digitou uma busca mas não encontrou nenhum cliente
const clienteNaoEncontrado = computed(() =>
  !clienteSelecionado.value && (clienteBusca.value || '').trim().length > 0
)

function abrirModalNovoCliente() {
  modalNovo.cliente_nome = clienteBusca.value.trim()
  modalNovo.cliente_codigo = ''
  modalNovo.descricao = ''
  modalNovo.erro = ''
  modalNovo.aberto = true
}
function fecharModalNovo() { modalNovo.aberto = false }

async function enviarSolicitacaoNovo() {
  if (!modalNovo.cliente_nome.trim()) return
  modalNovo.enviando = true
  modalNovo.erro = ''
  try {
    await api.solicitacoes.criar({
      tipo: 'novo_cliente',
      cliente_codigo: modalNovo.cliente_codigo.trim() || null,
      cliente_nome: modalNovo.cliente_nome.trim(),
      descricao: modalNovo.descricao.trim() || null
    })
    modalNovo.aberto = false
    alert('Solicitação aberta! O time de cadastro foi notificado.')
  } catch (e) {
    modalNovo.erro = e.message
  } finally {
    modalNovo.enviando = false
  }
}

function abrirModalContato() {
  const c = clienteSelecionado.value
  if (!c) return
  modalContato.cliente_id = c.id
  modalContato.cliente_nome = c.nome_razao_social
  modalContato.descricao = ''
  modalContato.erro = ''
  modalContato.aberto = true
}
function fecharModalContato() { modalContato.aberto = false }

async function enviarSolicitacaoContato() {
  if (!modalContato.descricao.trim()) return
  modalContato.enviando = true
  modalContato.erro = ''
  try {
    await api.solicitacoes.criar({
      tipo: 'atualizar_contato',
      cliente_id: modalContato.cliente_id,
      cliente_nome: modalContato.cliente_nome,
      descricao: modalContato.descricao.trim()
    })
    modalContato.aberto = false
    alert('Solicitação aberta! O time foi notificado.')
  } catch (e) {
    modalContato.erro = e.message
  } finally {
    modalContato.enviando = false
  }
}

onMounted(async () => {
  carregando.value = true
  try {
    const [clientes, ufs] = await Promise.all([
      api.clientes.listar(),
      api.locais.estados()
    ])
    todos.value = clientes
    estados.value = ufs
    selecionarPorQuery()
  } finally {
    carregando.value = false
  }
})

// Seleciona um cliente vindo via URL (ex.: /clientes/pesquisa?cliente=ID ou ?codigo=C100),
// usado quando o motorista clica na notificação de solicitação concluída.
function selecionarPorQuery() {
  const id = route.query.cliente
  const cod = route.query.codigo
  const alvo = id
    ? todos.value.find(c => c.id === id)
    : cod
      ? todos.value.find(c => c.codigo === cod)
      : null
  if (!alvo) return
  estadoSel.value = alvo.estado || ''
  cidadeSel.value = alvo.cidade || ''
  clienteBusca.value = alvo.nome_razao_social
  clienteSelecionado.value = alvo
}

// Se o usuário já está na página e a URL muda (ex.: clicou em outra notificação)
watch(() => route.query.cliente, () => { if (todos.value.length) selecionarPorQuery() })
watch(() => route.query.codigo, () => { if (todos.value.length) selecionarPorQuery() })

const cidades = computed(() => {
  const src = estadoSel.value
    ? todos.value.filter(c => c.estado === estadoSel.value)
    : todos.value
  return src
    .map(c => c.cidade)
    .filter(Boolean)
    .filter((v, i, arr) => arr.indexOf(v) === i)
    .sort()
})

const clientesFiltrados = computed(() => {
  return todos.value.filter(c =>
    (!estadoSel.value || c.estado === estadoSel.value) &&
    (!cidadeSel.value || c.cidade === cidadeSel.value)
  )
})

const temCoords = (end) => end && end.latitude != null && end.longitude != null

// Primeiro endereço com coordenadas (para o mapa preview)
const primeiroComCoords = computed(() => {
  const c = clienteSelecionado.value
  if (!c) return null
  return (c.enderecos || []).find(temCoords) || null
})

function montarEndereco(end) {
  if (!end) return ''
  const partes = [
    [end.rua, end.numero].filter(Boolean).join(', '),
    end.bairro,
    [end.cidade, end.estado].filter(Boolean).join(' - '),
    end.cep
  ].filter(Boolean)
  return partes.join(', ') + (partes.length ? ', Brasil' : '')
}

function wazeUrlDe(end) {
  if (!end) return '#'
  const texto = montarEndereco(end)
  if (temCoords(end)) return `https://waze.com/ul?ll=${end.latitude},${end.longitude}${texto ? `&q=${encodeURIComponent(texto)}` : ''}&navigate=yes`
  if (texto) return `https://waze.com/ul?q=${encodeURIComponent(texto)}&navigate=yes`
  return '#'
}

function mapsUrlDe(end) {
  if (!end) return '#'
  const texto = montarEndereco(end)
  if (texto) return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(texto)}`
  if (temCoords(end)) return `https://www.google.com/maps/search/?api=1&query=${end.latitude},${end.longitude}`
  return '#'
}

function osmUrlDe(end) {
  if (!end) return '#'
  if (temCoords(end)) return `https://www.openstreetmap.org/?mlat=${end.latitude}&mlon=${end.longitude}#map=17/${end.latitude}/${end.longitude}`
  const texto = montarEndereco(end)
  if (texto) return `https://www.openstreetmap.org/search?query=${encodeURIComponent(texto)}`
  return '#'
}

async function copiarEndereco(end, i) {
  const texto = montarEndereco(end)
  if (!texto) return
  try {
    await navigator.clipboard.writeText(texto)
  } catch {
    const ta = document.createElement('textarea')
    ta.value = texto
    document.body.appendChild(ta)
    ta.select()
    try { document.execCommand('copy') } catch {}
    document.body.removeChild(ta)
  }
  copiadoIdx.value = i
  clearTimeout(copiarTimeout)
  copiarTimeout = setTimeout(() => { copiadoIdx.value = -1 }, 2000)
}

function onEstadoChange() {
  if (cidadeSel.value && !cidades.value.includes(cidadeSel.value)) {
    cidadeSel.value = ''
  }
  clienteBusca.value = ''
  clienteSelecionado.value = null
}

function onClienteFilterChange() {
  clienteBusca.value = ''
  clienteSelecionado.value = null
}

function onClienteSelecionado() {
  const nome = clienteBusca.value.trim()
  if (!nome) { clienteSelecionado.value = null; return }
  const enc = clientesFiltrados.value.find(c => c.nome_razao_social === nome)
  clienteSelecionado.value = enc || null
}

watch(clientesFiltrados, () => {
  if (clienteBusca.value) onClienteSelecionado()
})

// Inicializa/atualiza o mapa preview quando o cliente selecionado muda
watch(clienteSelecionado, async () => {
  await nextTick()
  if (primeiroComCoords.value) {
    inicializarMapa(primeiroComCoords.value)
  } else {
    destruirMapa()
  }
})

function inicializarMapa(end) {
  destruirMapa()
  if (!mapaEl.value) return
  const lat = Number(end.latitude)
  const lng = Number(end.longitude)
  map = L.map('mapa-pesquisa', { dragging: true, scrollWheelZoom: false }).setView([lat, lng], 16)
  L.tileLayer(tileUrl(), {
    attribution: tileAttribution(),
    maxZoom: tileMaxZoom()
  }).addTo(map)
  marker = L.marker([lat, lng], { draggable: false }).addTo(map)
}

function destruirMapa() {
  if (map) { map.remove(); map = null; marker = null }
}

onBeforeUnmount(destruirMapa)

function irParaEdicao() {
  if (!clienteSelecionado.value) return
  router.push({ name: 'editar', query: { cliente: clienteSelecionado.value.id } })
}

async function exportarExcel() {
  exportando.value = true
  try {
    const blob = await api.clientes.exportar({
      estado: estadoSel.value || null,
      cidade: cidadeSel.value || null
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'clientes.xlsx'
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    alert('Erro ao exportar: ' + e.message)
  } finally {
    exportando.value = false
  }
}

async function excluirCliente() {
  const c = clienteSelecionado.value
  if (!c) return
  if (!confirm(`Excluir o cliente "${c.nome_razao_social}"?`)) return
  try {
    await api.clientes.remover(c.id)
    clienteSelecionado.value = null
    clienteBusca.value = ''
    todos.value = todos.value.filter(x => x.id !== c.id)
  } catch (e) {
    alert('Erro ao excluir: ' + e.message)
  }
}

function formatarData(iso) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString('pt-BR')
  } catch { return iso }
}

// Nome do usuario com a empresa para identificacao (ex: "Joao (AC)")
function nomeComEmpresa(nome, empresa) {
  const n = nome || ''
  const e = empresa || ''
  return e ? `${n} (${e})` : n
}
</script>

<style scoped>
.page { padding: 1.5rem 1rem 2.5rem; }
.container { max-width: 1100px; margin: 0 auto; }

.page-head { margin-bottom: 1.25rem; }
.page-head h1 { font-size: 1.6rem; font-weight: 700; color: #0f172a; letter-spacing: -0.02em; }
.page-head p { color: #64748b; font-size: 0.9rem; margin-top: 0.2rem; }

.grid { display: grid; grid-template-columns: 320px 1fr; gap: 1.25rem; align-items: start; }
@media (max-width: 820px) { .grid { grid-template-columns: 1fr; } }

.card {
  background: #fff; border-radius: 16px; padding: 1.25rem;
  box-shadow: card; border: 1px solid #eef2f8;
}
.section-title { font-size: 1rem; font-weight: 700; color: #1d2a4d; margin-bottom: 0.9rem;
  padding-bottom: 0.6rem; border-bottom: 1px solid #eef2f8; }

.field { margin-bottom: 0.9rem; }
.field label { display: block; font-size: 0.78rem; font-weight: 600; color: #475569; margin-bottom: 0.3rem; }
.field select, .field input {
  width: 100%; padding: 0.55rem 0.7rem;
  border: 1px solid #dbe2ee; border-radius: 8px;
  font-size: 0.9rem; outline: none; background: #fff; transition: all 0.15s;
}
.field select:focus, .field input:focus {
  border-color: #1f5bf0; box-shadow: 0 0 0 4px rgba(31,91,240,0.12);
}
.cliente-search { width: 100%; }

.contador {
  margin-top: 0.4rem; font-size: 0.78rem; color: #64748b;
  background: #f1f7ff; padding: 0.4rem 0.6rem; border-radius: 8px; border: 1px solid #d9eaff;
}

.placeholder { text-align: center; padding: 2.5rem 1rem; color: #94a3b8; }
.placeholder .empty-icon { font-size: 2.2rem; margin-bottom: 0.4rem; }
.placeholder h3 { color: #64748b; font-size: 1rem; margin: 0.2rem 0; }
.placeholder p { font-size: 0.85rem; max-width: 320px; margin: 0 auto; }

.detalhe-head h2 { font-size: 1.25rem; font-weight: 700; color: #0f172a; margin-top: 0.5rem; }
.badge {
  display: inline-block; font-size: 0.72rem; font-weight: 700;
  padding: 0.18rem 0.5rem; border-radius: 6px; background: #1f5bf0; color: #fff; letter-spacing: 0.05em;
}
.badge.soft { background: #d9eaff; color: #1746dc; margin-left: 0.3rem; }
.badge.status-atualizando { background: #fef3c7; color: #b45309; margin-left: 0.3rem; font-weight: 600; }
.alt-por-info {
  margin: 0.55rem 0; padding: 0.55rem 0.75rem; border-radius: 8px;
  background: #fffbeb; color: #92400e; font-size: 0.82rem;
  border: 1px solid #fde68a; line-height: 1.35;
}
.alt-por-data { color: #94a3b8; font-size: 0.75rem; }

.grid-info {
  display: grid; grid-template-columns: 1fr 1fr; gap: 0.9rem 1.25rem;
  margin-top: 1.1rem; margin-bottom: 0;
}
.grid-info > div { padding-bottom: 0.6rem; border-bottom: 1px dashed #eef2f8; }
.grid-info > div.full { grid-column: 1 / -1; }
.grid-info dt { font-size: 0.72rem; color: #94a3b8; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; }
.grid-info dd { font-size: 0.95rem; color: #1d2a4d; margin-top: 0.15rem; }
.grid-info dd.obs { white-space: pre-wrap; line-height: 1.4; }

/* Endereços */
.enderecos-readonly { margin-top: 1.1rem; }
.enderecos-readonly > h3 { font-size: 0.95rem; font-weight: 700; color: #1d2a4d; margin-bottom: 0.6rem; padding-bottom: 0.5rem; border-bottom: 1px solid #eef2f8; }
.endereco-card {
  border: 1px solid #dbe2ee; border-radius: 12px; padding: 0.9rem 1rem;
  margin-bottom: 0.8rem; background: #fafcff;
}
.end-card-head { display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem; }
.end-card-head h4 { font-size: 0.92rem; font-weight: 700; color: #1d2a4d; }
.tag-principal {
  font-size: 0.66rem; font-weight: 700; padding: 0.12rem 0.45rem; border-radius: 5px;
  background: #dbeafe; color: #1d4ed8; letter-spacing: 0.03em; text-transform: uppercase;
}
.end-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0.4rem 1rem; }
.end-grid > div { padding-bottom: 0.35rem; border-bottom: 1px dashed #f1f5f9; }
.end-grid > div.full { grid-column: 1 / -1; }
.end-grid dt { font-size: 0.68rem; color: #94a3b8; font-weight: 600; text-transform: uppercase; }
.end-grid dd { font-size: 0.88rem; color: #1d2a4d; margin: 0.05rem 0 0; }
.end-grid dd.obs { white-space: pre-wrap; line-height: 1.4; }
@media (max-width: 560px) { .end-grid { grid-template-columns: 1fr; } }

.contatos-lista { display: flex; flex-wrap: wrap; gap: 0.4rem; margin-top: 0.6rem; }
.contato-chip {
  display: inline-flex; align-items: center; gap: 0.35rem;
  background: #eef6ff; border: 1px solid #d9eaff; border-radius: 8px;
  padding: 0.25rem 0.6rem; font-size: 0.8rem;
}
.contato-nome { font-weight: 600; color: #1d2a4d; }
.contato-tel { color: #64748b; }
.sem-contato { font-size: 0.78rem; color: #94a3b8; font-style: italic; margin-top: 0.5rem; }

/* Fotos (read-only) */
.fotos-readonly { margin-top: 1.1rem; border-top: 1px solid #eef2f8; padding-top: 0.9rem; }
.fotos-readonly h3 { font-size: 0.95rem; font-weight: 700; color: #1d2a4d; margin-bottom: 0.55rem; }
.fotos-galeria { display: grid; grid-template-columns: repeat(auto-fill, minmax(110px, 1fr)); gap: 0.6rem; margin-bottom: 0.7rem; }
.fotos-galeria .foto-item {
  display: block; border-radius: 10px; overflow: hidden;
  aspect-ratio: 1; background: #f1f5f9; border: 1px solid #e2e8f0;
  cursor: pointer; transition: transform 0.15s;
}
.fotos-galeria .foto-item:hover { transform: scale(1.03); }
.fotos-galeria .foto-item img { width: 100%; height: 100%; object-fit: cover; display: block; }

.mapa-preview { margin-top: 1.1rem; }
.mapa { width: 100%; height: 280px; border-radius: 12px; overflow: hidden; border: 1px solid #e8eaf0; }

/* Endereço completo para navegação */
.endereco-full { margin-top: 0.8rem; padding: 0.8rem; border-radius: 10px; background: #f1f7ff; border: 1px solid #d9eaff; }
.endereco-full > label {
  display: block; font-size: 0.74rem; font-weight: 600; color: #1e3a8a;
  margin-bottom: 0.35rem; text-transform: uppercase; letter-spacing: 0.04em;
}
.endereco-row { display: flex; gap: 0.5rem; }
.endereco-input {
  flex: 1; padding: 0.5rem 0.7rem; border: 1px solid #bcdcff; border-radius: 8px;
  font-size: 0.85rem; background: #fff; color: #0f172a; outline: none;
}
.endereco-input:focus { border-color: #1f5bf0; box-shadow: 0 0 0 4px rgba(31,91,240,0.12); }
.nav-links { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 0.4rem; }
.nav-link {
  display: inline-flex; align-items: center; gap: 0.3rem;
  padding: 0.35rem 0.7rem; border-radius: 7px; font-size: 0.8rem; font-weight: 600;
  text-decoration: none; transition: all 0.15s;
}
.nav-link.waze { background: #33a0ff; color: #fff; }
.nav-link.waze:hover { background: #1d8bf5; }
.nav-link.maps { background: #fff; color: #1d2a4d; border: 1px solid #dbe2ee; }
.nav-link.maps:hover { background: #eef6ff; border-color: #1f5bf0; color: #1f5bf0; }
.nav-link.osm { background: #fff; color: #5a9e4b; border: 1px solid #dbe2ee; }
.nav-link.osm:hover { background: #f0fbec; border-color: #7ebc6f; }
.nav-link.disabled { opacity: 0.5; pointer-events: none; }

.btn { padding: 0.6rem 1rem; border-radius: 9px; cursor: pointer; font-weight: 600; font-size: 0.88rem; }
.btn-primary {
  background: linear-gradient(135deg, #3479fb, #1746dc); color: #fff; border: none;
  box-shadow: 0 10px 20px -8px rgba(23,70,220,0.7);
}
.btn-primary:hover { opacity: 0.95; }
.btn-secondary { background: #eef6ff; color: #1746dc; border: 1px solid #bcdcff; }
.btn-secondary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-danger { background: #fee2e2; color: #b91c1c; border: 1px solid #fecaca; }
.botoes-acao { display: flex; flex-direction: column; gap: 0.4rem; }
.btn-sm { padding: 0.4rem 0.75rem; font-size: 0.8rem; }
.mt { margin-top: 0.5rem; }

/* Modais de solicitação */
.modal-overlay {
  position: fixed; inset: 0; background: rgba(15, 23, 42, 0.55);
  display: flex; align-items: center; justify-content: center; padding: 1rem;
  z-index: 1000; backdrop-filter: blur(2px); overflow-y: auto;
}
.modal-card {
  background: #fff; border-radius: 16px; padding: 1.3rem;
  max-width: 480px; width: 100%; max-height: calc(100vh - 2rem); overflow-y: auto; margin: auto;
  box-shadow: 0 30px 70px -20px rgba(15, 23, 42, 0.45);
  animation: modal-in 0.16s ease-out;
}
.modal-card h3 { font-size: 1.05rem; font-weight: 700; color: #0f172a; margin-bottom: 0.35rem; }
.modal-sub { font-size: 0.82rem; color: #64748b; margin-bottom: 0.8rem; line-height: 1.45; }
.modal-card .field label { display: block; font-size: 0.78rem; font-weight: 600; color: #475569; margin-bottom: 0.3rem; }
.modal-card input, .modal-card textarea {
  width: 100%; padding: 0.5rem 0.7rem; border: 1px solid #dbe2ee; border-radius: 8px;
  font-size: 0.9rem; outline: none; background: #fff; box-sizing: border-box; font-family: inherit;
}
.modal-card input:focus, .modal-card textarea:focus { border-color: #1f5bf0; box-shadow: 0 0 0 4px rgba(31,91,240,0.12); }
.modal-card textarea { resize: vertical; min-height: 70px; }
.modal-botoes { display: flex; gap: 0.6rem; justify-content: flex-end; margin-top: 1rem; flex-wrap: wrap; }
.msg.erro { color: #b91c1c; font-size: 0.82rem; margin-top: 0.4rem; }
@keyframes modal-in {
  from { opacity: 0; transform: translateY(8px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

@media (max-width: 540px) {
  .mapa { height: 240px; }
  .endereco-row { flex-direction: column; gap: 0.4rem; }
  .endereco-row .btn-sm { width: 100%; }
}
</style>