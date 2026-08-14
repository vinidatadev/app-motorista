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
                <span v-if="clienteSelecionado.status_endereco === 'atualizando'" class="badge status-atualizando" title="Endereço submetido para aprovação">
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
              <div><dt>CEP</dt><dd>{{ clienteSelecionado.cep || '—' }}</dd></div>
              <div><dt>Rua</dt><dd>{{ clienteSelecionado.rua || '—' }}</dd></div>
              <div><dt>Número</dt><dd>{{ clienteSelecionado.numero || '—' }}</dd></div>
              <div><dt>Bairro</dt><dd>{{ clienteSelecionado.bairro || '—' }}</dd></div>
              <div class="full"><dt>Localização</dt>
                <dd>
                  {{ clienteSelecionado.latitude ?? '—' }}, {{ clienteSelecionado.longitude ?? '—' }}
                </dd>
              </div>
              <div class="full">
                <dt>Atualizado por</dt>
                <dd v-if="clienteSelecionado.alterado_por_nome">
                  {{ nomeComEmpresa(clienteSelecionado.alterado_por_nome, clienteSelecionado.alterado_por_empresa) }}
                  <span class="alt-por-data">em {{ formatarData(clienteSelecionado.alterado_em || clienteSelecionado.updated_at) }}</span>
                </dd>
                <dd v-else>{{ formatarData(clienteSelecionado.updated_at) }}</dd>
              </div>
              <div v-if="clienteSelecionado.ponto_referencia" class="full"><dt>Ponto de referência</dt><dd>{{ clienteSelecionado.ponto_referencia }}</dd></div>
              <div v-if="clienteSelecionado.observacao" class="full"><dt>Observação</dt><dd class="obs">{{ clienteSelecionado.observacao }}</dd></div>
            </dl>

            <!-- Fotos do local (somente leitura) -->
            <div v-if="clienteSelecionado.fotos && clienteSelecionado.fotos.length" class="fotos-readonly">
              <h3>📸 Fotos do local</h3>
              <div class="fotos-galeria">
                <a v-for="f in clienteSelecionado.fotos" :key="f.id" :href="f.url" target="_blank" rel="noopener" class="foto-item">
                  <img :src="f.url" :alt="`Foto ${f.id}`" loading="lazy" />
                </a>
              </div>
            </div>

            <!-- Preview do mapa (read-only) -->
            <div v-if="temCoords(clienteSelecionado)" class="mapa-preview">
              <div ref="mapaEl" class="mapa" id="mapa-pesquisa"></div>
            </div>

            <!-- Endereço completo para navegação -->
            <div class="endereco-full">
              <label>Endereço completo para navegação</label>
              <div class="endereco-row">
                <input :value="enderecoCompleto" readonly class="endereco-input" />
                <button class="btn btn-secondary btn-sm" @click="copiarEndereco" :disabled="!enderecoCompleto">
                  {{ copiado ? '✓ Copiado' : '⧉ Copiar' }}
                </button>
              </div>

              <!-- Pelo pin no mapa -->
              <div v-if="temCoords(clienteSelecionado)" class="nav-group">
                <div class="nav-group-label">
                  <span class="dot pin"></span> Pelo pin no mapa
                  <span class="nav-coords">{{ clienteSelecionado.numero || 's/ número' }} · {{ (enderecoCompleto.split(',')[0]) || 'endereço' }}</span>
                </div>
                <div class="nav-links">
                  <a :href="wazeUrl" target="_blank" rel="noopener" class="nav-link waze">Waze ↗</a>
                  <a :href="mapsCoordUrl" target="_blank" rel="noopener" class="nav-link maps">Google Maps ↗</a>
                  <a :href="osmUrl" target="_blank" rel="noopener" class="nav-link osm">OpenStreetMap ↗</a>
                </div>
              </div>

              <!-- Pelo endereço digitado -->
              <div v-if="enderecoCompleto" class="nav-group">
                <div class="nav-group-label">
                  <span class="dot texto"></span> Pelo endereço completo
                </div>
                <div class="nav-links">
                  <a :href="wazeTextoUrl" target="_blank" rel="noopener" class="nav-link waze">Waze ↗</a>
                  <a :href="mapsTextoUrl" target="_blank" rel="noopener" class="nav-link maps">Google Maps ↗</a>
                  <a :href="osmTextoUrl" target="_blank" rel="noopener" class="nav-link osm">OpenStreetMap ↗</a>
                </div>
              </div>

              <p class="endereco-hint">Copie e cole no app de navegação, ou clique num link. Os apps mostrarão o endereço por extenso (não as coordenadas numéricas).</p>
            </div>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
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
let copiarTimeout = null

onMounted(async () => {
  carregando.value = true
  try {
    const [clientes, ufs] = await Promise.all([
      api.clientes.listar(),
      api.locais.estados()
    ])
    todos.value = clientes
    estados.value = ufs
  } finally {
    carregando.value = false
  }
})

const cidades = computed(() => {
  if (estadoSel.value) {
    return todos.value
      .filter(c => c.estado === estadoSel.value)
      .map(c => c.cidade)
      .filter(Boolean)
      .filter((v, i, arr) => arr.indexOf(v) === i)
      .sort()
  }
  return todos.value
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

// Endereço completo montado a partir dos dados do cliente (reativo)
const enderecoCompleto = computed(() => {
  const c = clienteSelecionado.value
  if (!c) return ''
  const partes = [
    [c.rua, c.numero].filter(Boolean).join(', '),
    c.bairro,
    [c.cidade, c.estado].filter(Boolean).join(' - '),
    c.cep
  ].filter(Boolean)
  return partes.join(', ') + (partes.length ? ', Brasil' : '')
})

const temCoords = (c) => c && c.latitude != null && c.longitude != null

// Links "pelo pin no mapa": combinam a coordenada exata (precisão) com o endereço
// textual na query, para o app mostrar o nome do lugar em vez de lat/lng cruas.
const wazeUrl = computed(() => {
  const c = clienteSelecionado.value
  if (!c || !temCoords(c)) return '#'
  const q = enderecoCompleto.value ? `&q=${encodeURIComponent(enderecoCompleto.value)}` : ''
  return `https://waze.com/ul?ll=${c.latitude},${c.longitude}${q}&navigate=yes`
})

const mapsCoordUrl = computed(() => {
  const c = clienteSelecionado.value
  if (!c) return '#'
  if (enderecoCompleto.value) return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(enderecoCompleto.value)}`
  if (temCoords(c)) return `https://www.google.com/maps/search/?api=1&query=${c.latitude},${c.longitude}`
  return '#'
})

const osmUrl = computed(() => {
  const c = clienteSelecionado.value
  if (!c) return '#'
  if (temCoords(c)) return `https://www.openstreetmap.org/?mlat=${c.latitude}&mlon=${c.longitude}#map=17/${c.latitude}/${c.longitude}`
  if (enderecoCompleto.value) return `https://www.openstreetmap.org/search?query=${encodeURIComponent(enderecoCompleto.value)}`
  return '#'
})

const wazeTextoUrl = computed(() => {
  if (!enderecoCompleto.value) return '#'
  return `https://waze.com/ul?q=${encodeURIComponent(enderecoCompleto.value)}&navigate=yes`
})

const mapsTextoUrl = computed(() => {
  if (!enderecoCompleto.value) return '#'
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(enderecoCompleto.value)}`
})

const osmTextoUrl = computed(() => {
  if (!enderecoCompleto.value) return '#'
  return `https://www.openstreetmap.org/search?query=${encodeURIComponent(enderecoCompleto.value)}`
})

async function copiarEndereco() {
  if (!enderecoCompleto.value) return
  try {
    await navigator.clipboard.writeText(enderecoCompleto.value)
  } catch {
    const ta = document.createElement('textarea')
    ta.value = enderecoCompleto.value
    document.body.appendChild(ta)
    ta.select()
    try { document.execCommand('copy') } catch {}
    document.body.removeChild(ta)
  }
  copiado.value = true
  clearTimeout(copiarTimeout)
  copiarTimeout = setTimeout(() => { copiado.value = false }, 2000)
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
watch(clienteSelecionado, async (c) => {
  await nextTick()
  if (c && temCoords(c)) {
    inicializarMapa(c)
  } else {
    destruirMapa()
  }
})

function inicializarMapa(c) {
  destruirMapa()
  if (!mapaEl.value) return
  const lat = Number(c.latitude)
  const lng = Number(c.longitude)
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
.endereco-full {
  margin-top: 1rem; padding: 0.9rem; border-radius: 10px;
  background: #f1f7ff; border: 1px solid #d9eaff;
}
.endereco-full > label {
  display: block; font-size: 0.78rem; font-weight: 600; color: #1e3a8a;
  margin-bottom: 0.4rem; text-transform: uppercase; letter-spacing: 0.04em;
}
.endereco-row { display: flex; gap: 0.5rem; }
.endereco-input {
  flex: 1; padding: 0.5rem 0.7rem; border: 1px solid #bcdcff; border-radius: 8px;
  font-size: 0.85rem; background: #fff; color: #0f172a; outline: none;
}
.endereco-input:focus { border-color: #1f5bf0; box-shadow: 0 0 0 4px rgba(31,91,240,0.12); }

.nav-group { margin-top: 0.7rem; padding: 0.55rem 0.7rem; border-radius: 8px; background: #fff; border: 1px solid #eaf1fb; }
.nav-group-label {
  display: flex; align-items: center; gap: 0.45rem; flex-wrap: wrap;
  font-size: 0.78rem; font-weight: 600; color: #475569;
}
.nav-coords { margin-left: auto; font-size: 0.72rem; color: #94a3b8; font-weight: 400; }
.dot { display: inline-block; width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; }
.dot.pin { background: #33a0ff; }
.dot.texto { background: #f59e0b; }

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

.endereco-hint { font-size: 0.72rem; color: #94a3b8; margin-top: 0.6rem; }

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

/* Mobile: ajustes de espaçamento e input do endereço */
@media (max-width: 540px) {
  .mapa { height: 240px; }
  .endereco-row { flex-direction: column; gap: 0.4rem; }
  .endereco-row .btn-sm { width: 100%; }
  .nav-coords { margin-left: 0; width: 100%; }
}
</style>