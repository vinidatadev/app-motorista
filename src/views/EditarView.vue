<template>
  <div class="page">
    <div class="container">
      <div class="page-head">
        <h1>Atualização de Cadastro</h1>
        <p>Selecione o cliente, ajuste dados e geolocalização. Arraste o pin no mapa ou use o GPS.</p>
      </div>

      <!-- Seleção do cliente -->
      <section class="card sel">
        <div class="grid3">
          <div class="field">
            <label>Estado (UF)</label>
            <select v-model="estadoSel" @change="onEstadoChange">
              <option value="">Todos</option>
              <option v-for="uf in estados" :key="uf" :value="uf">{{ uf }}</option>
            </select>
          </div>
          <div class="field">
            <label>Cidade</label>
            <select v-model="cidadeSel" @change="limparSelecao">
              <option value="">Todas</option>
              <option v-for="c in cidadesDisponiveis" :key="c" :value="c">{{ c }}</option>
            </select>
          </div>
          <div class="field">
            <label>Cliente</label>
            <input
              list="lista-clientes-editar"
              v-model="clienteBusca"
              placeholder="Digite para buscar..."
              @change="onClienteSelecionado"
            />
            <datalist id="lista-clientes-editar">
              <option v-for="c in clientesFiltrados" :key="c.id" :value="c.nome_razao_social">
                {{ c.cidade }}/{{ c.estado }}
              </option>
            </datalist>
          </div>
        </div>
      </section>

      <!-- Banner de status (submetido p/ aprovacao) -->
      <div v-if="form && clienteStatus !== 'aprovado'" class="status-banner" :class="'status-' + clienteStatus">
        <span class="status-icon">{{ clienteStatus === 'atualizando' ? '⏳' : '✔' }}</span>
        <div>
          <strong>{{ clienteStatus === 'atualizando' ? 'Endereço submetido para aprovação' : 'Endereço aprovado' }}</strong>
          <span v-if="clienteStatus === 'atualizando' && form.alterado_por_nome">
            — enviado por <strong>{{ nomeComEmpresa(form.alterado_por_nome, form.alterado_por_empresa) }}</strong> em {{ formatarData(form.alterado_em) }}
          </span>
        </div>
      </div>

      <!-- Aviso de bloqueio: já existe alteração pendente de aprovação -->
      <div v-if="somenteLeitura" class="lock-banner">
        🔒 Este cliente já possui uma alteração aguardando aprovação.
        A edição está bloqueada — você poderá editar novamente depois que o aprovador revisar.
      </div>

      <!-- Formulário de edição -->
      <section v-if="form" class="card form-card">
        <fieldset class="fs-lock" :disabled="somenteLeitura">
        <div class="form-grid">
          <div class="field full">
            <label>Nome / Razão Social</label>
            <input v-model="form.nome_razao_social" />
          </div>
          <div class="field">
            <label>Telefone</label>
            <input :value="form.telefone" @input="onTelefoneInput" placeholder="(00) 0 0000-0000" />
          </div>
          <div class="field">
            <label>Pessoa de Contato</label>
            <input v-model="form.pessoa_contato" />
          </div>
          <div class="field">
            <label>CEP</label>
            <input v-model="form.cep" />
          </div>
          <div class="field">
            <label>Número</label>
            <input v-model="form.numero" />
          </div>
          <div class="field col2">
            <label>Rua</label>
            <input v-model="form.rua" />
          </div>
          <div class="field">
            <label>Bairro</label>
            <input v-model="form.bairro" />
          </div>
          <div class="field">
            <label>Cidade</label>
            <input v-model="form.cidade" />
          </div>
          <div class="field">
            <label>Estado (UF)</label>
            <input v-model="form.estado" maxlength="2" class="uf" />
          </div>
          <div class="field col2">
            <label>Ponto de Referência</label>
            <input v-model="form.ponto_referencia" placeholder="Ex.: próximo ao shopping, esquina com a farmácia..." />
          </div>
          <div class="field full">
            <label>Observação</label>
            <textarea v-model="form.observacao" rows="3" placeholder="Notações relevantes para o motorista..."></textarea>
          </div>
        </div>

        <!-- Geolocalização -->
        <div class="geo-section">
          <div class="geo-head">
            <h3>Localização & Mapa</h3>
            <button class="btn btn-secondary" @click="pegarLocalizacao" :disabled="geo.loading">
              {{ geo.loading ? 'Obtendo...' : '📍 Pegar Localização Atual' }}
            </button>
          </div>
          <p class="lat-info">
            Latitude: <strong>{{ form.latitude ?? '—' }}</strong> ·
            Longitude: <strong>{{ form.longitude ?? '—' }}</strong>
            <span v-if="geo.erro" class="erro-inline"> · {{ geo.erro }}</span>
          </p>
          <div ref="mapaEl" class="mapa" id="mapa-editar"></div>
          <div class="mapa-acoes">
            <p class="dica-map">Arraste o marcador para ajustar o endereço (reverse geocoding automático).</p>
            <button class="btn btn-secondary btn-sm" @click="forwardGeocode" :disabled="!form.rua && !form.cidade">
              🎯 Reposicionar pin no endereço digitado
            </button>
          </div>
          <div v-if="haDivergenciaNumero()" class="aviso-divergencia">
            ⚠️ O número digitado (<strong>{{ form.numero }}</strong>) difere da posição do pin no mapa (<strong>{{ numeroDoMapa }}</strong>).
            Ao salvar, você poderá escolher entre manter assim ou reposicionar o pin.
          </div>

          <!-- Endereço completo para colar em Waze/Maps -->
          <div class="endereco-full">
            <label>Endereço completo para navegação</label>
            <div class="endereco-row">
              <input :value="enderecoCompleto" readonly class="endereco-input" />
              <button class="btn btn-secondary btn-sm" @click="copiarEndereco" :disabled="!enderecoCompleto">
                {{ copiado ? '✓ Copiado' : '⧉ Copiar' }}
              </button>
            </div>

            <!-- Linha 1: pela posição do pin no mapa -->
            <div v-if="temCoords" class="nav-group">
              <div class="nav-group-label">
                <span class="dot pin"></span> Pelo pin no mapa
                <span class="nav-coords">{{ numeroDoMapa || 's/ número' }} · {{ enderecoPin.split(',')[0] || 'endereço do pin' }}</span>
              </div>
              <div class="nav-links">
                <a :href="wazeUrl" target="_blank" rel="noopener" class="nav-link waze">Waze ↗</a>
                <a :href="mapsCoordUrl" target="_blank" rel="noopener" class="nav-link maps">Google Maps ↗</a>
                <a :href="osmUrl" target="_blank" rel="noopener" class="nav-link osm">OpenStreetMap ↗</a>
              </div>
            </div>

            <!-- Linha 2: pelo endereço digitado (usa o número que o usuário informou) -->
            <div v-if="enderecoCompleto" class="nav-group" :class="{ divergente: haDivergenciaNumero() }">
              <div class="nav-group-label">
                <span class="dot texto"></span> Pelo endereço digitado
                <span class="nav-coords" v-if="haDivergenciaNumero()">({{ form.numero || 's/ número' }} · pode differ do pin)</span>
              </div>
              <div class="nav-links">
                <a :href="wazeTextoUrl" target="_blank" rel="noopener" class="nav-link waze">Waze ↗</a>
                <a :href="mapsTextoUrl" target="_blank" rel="noopener" class="nav-link maps">Google Maps ↗</a>
                <a :href="osmTextoUrl" target="_blank" rel="noopener" class="nav-link osm">OpenStreetMap ↗</a>
              </div>
            </div>

            <p class="endereco-hint">
              Copie e cole no app, ou clique num link. Os apps de navegação mostrarão o endereço por extenso.
              <strong v-if="haDivergenciaNumero()" style="color:#b45309">Atenção: o número digitado ({{ form.numero }}) difere do pin ({{ numeroDoMapa }}) — escolha a opção desejada.</strong>
            </p>
          </div>
        </div>

        <!-- Fotos do local -->
        <div class="fotos-section">
          <div class="fotos-head">
            <h3>📸 Fotos do local</h3>
            <p class="fotos-hint">Anexe fotos da fachada/entorno para ajudar na entrega.</p>
          </div>
          <div class="fotos-botoes">
            <label class="btn btn-secondary btn-sm" :disabled="uploading">
              📁 Escolher da galeria
              <input type="file" accept="image/jpeg,image/png,image/webp,image/gif" @change="onFotoFile" class="hidden-input" :disabled="uploading" />
            </label>
            <label class="btn btn-secondary btn-sm" :disabled="uploading">
              📷 Tirar foto (câmera)
              <input type="file" accept="image/*" capture="environment" @change="onFotoFile" class="hidden-input" :disabled="uploading" />
            </label>
            <span v-if="uploading" class="upload-msg">Enviando...</span>
          </div>
          <p v-if="fotoErro" class="msg erro">{{ fotoErro }}</p>
          <!-- Galeria -->
          <div v-if="fotos.length" class="fotos-galeria">
            <div v-for="f in fotos" :key="f.id" class="foto-item">
              <img :src="f.url" :alt="`Foto ${f.id}`" loading="lazy" @click="abrirFoto(f.url)" />
              <button class="foto-del" @click="removerFoto(f)" :disabled="uploading" title="Remover foto">×</button>
            </div>
          </div>
          <p v-else class="placeholder-fotos">Nenhuma foto anexada.</p>
        </div>

        <div class="acoes">
          <button class="btn btn-primary" @click="salvar" :disabled="salvando || somenteLeitura">
            {{ salvando ? 'Salvando...' : 'Salvar alterações' }}
          </button>
          <span v-if="msg" :class="['msg', msgTipo]">{{ msg }}</span>
        </div>
        </fieldset>
      </section>

      <section v-else class="card placeholder">
        <div class="empty-icon">📝</div>
        <h3>Selecione um cliente acima</h3>
        <p>Após escolher, o formulário e o mapa serão carregados para edição.</p>
      </section>
    </div>

    <!-- Modal de confirmação de divergência número vs mapa -->
    <div v-if="modal.aberto" class="modal-overlay" role="dialog" aria-modal="true">
      <div class="modal-card">
        <h3>Confirmação de endereço</h3>
        <p class="modal-text">
          O número digitado é <strong>{{ modal.numeroDigitado }}</strong>, mas o pin no mapa está na posição
          correspondente ao número <strong>{{ modal.numeroMapa }}</strong>.
        </p>
        <p class="modal-text">
          Você digitou um número diferente da posição física do pin. Como deseja proceder?
        </p>
        <div v-if="modal.erroRepos" class="erro-repos">{{ modal.erroRepos }}</div>
        <div class="modal-botoes">
          <button class="btn btn-secondary" @click="modalCancelar" :disabled="modal.reposicionando">Cancelar</button>
          <button class="btn btn-outline-blue" @click="modalReposicionar" :disabled="modal.reposicionando">
            {{ modal.reposicionando ? 'Reposicionando...' : '🎯 Reposicionar pin para o número digitado' }}
          </button>
          <button class="btn btn-primary" @click="modalSalvarAssim" :disabled="modal.reposicionando">
            ✓ Salvar assim mesmo
          </button>
        </div>
        <p class="modal-hint">
          “Salvar assim mesmo” mantém o pin onde está e grava o número digitado.
          “Reposicionar” usa o endereço completo para buscar a nova coordenada no mapa.
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch, nextTick, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import L from 'leaflet'
import markerIcon from 'leaflet/dist/images/marker-icon.png'
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png'
import markerShadow from 'leaflet/dist/images/marker-shadow.png'
import { api } from '../api'
import { tileUrl, tileAttribution, tileMaxZoom, reverseGeocode as reverseGeocodeExternal, forwardGeocode as forwardGeocodeExternal } from '../composables/useMapa'

// Corrige caminho dos ícones padrão do Leaflet quando empacotado pelo Vite
delete L.Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({
  iconUrl: markerIcon,
  iconRetinaUrl: markerIcon2x,
  shadowUrl: markerShadow
})

const route = useRoute()

const estados = ref([])
const todosClientes = ref([])
const estadoSel = ref('')
const cidadeSel = ref('')
const clienteId = ref('')
const clienteBusca = ref('')

const form = ref(null)
const salvando = ref(false)
const msg = ref('')
const msgTipo = ref('ok')

// Número que o mapa "entendeu" para a posição atual do pin (vindo do reverse geocode).
// Usado para detectar divergência quando o usuário digita um número diferente.
const numeroDoMapa = ref('')
// Estado do modal de confirmação de divergência no salvar
const modal = reactive({
  aberto: false,
  numeroMapa: '',
  numeroDigitado: '',
  latitudeMapa: null,
  longitudeMapa: null,
  resolve: null,
  reposicionando: false,
  erroRepos: ''
})

const mapaEl = ref(null)
let map = null

// Copiar endereço completo
const copiado = ref(false)
let copiarTimeout = null
let marker = null
let geocodingTimeout = null

const geo = reactive({ loading: false, erro: '' })

// Fotos
const fotos = ref([])
const uploading = ref(false)
const fotoErro = ref('')

// Mapeia nome de estado (Nominatim) -> sigla UF
const UF_POR_NOME = {
  'Acre':'AC','Alagoas':'AL','Amapá':'AP','Amazonas':'AM','Bahia':'BA','Ceará':'CE',
  'Distrito Federal':'DF','Espírito Santo':'ES','Goiás':'GO','Maranhão':'MA',
  'Mato Grosso':'MT','Mato Grosso do Sul':'MS','Minas Gerais':'MG','Pará':'PA',
  'Paraíba':'PB','Paraná':'PR','Pernambuco':'PE','Piauí':'PI','Rio de Janeiro':'RJ',
  'Rio Grande do Norte':'RN','Rio Grande do Sul':'RS','Rondônia':'RO','Roraima':'RR',
  'Santa Catarina':'SC','São Paulo':'SP','Sergipe':'SE','Tocantins':'TO'
}

onMounted(async () => {
  try {
    const [c, ufs] = await Promise.all([
      api.clientes.listar(),
      api.locais.estados()
    ])
    todosClientes.value = c
    estados.value = ufs
  } catch (e) {
    msg.value = 'Falha ao carregar clientes: ' + e.message
    msgTipo.value = 'erro'
  }

  // Pré-seleção via query ?cliente=ID
  const preId = route.query.cliente
  if (preId) {
    const enc = todosClientes.value.find(x => x.id === preId)
    if (enc) {
      estadoSel.value = enc.estado || ''
      cidadeSel.value = enc.cidade || ''
      clienteBusca.value = enc.nome_razao_social
      clienteId.value = enc.id
      await carregarCliente()
    }
  }
})

const cidadesDisponiveis = computed(() => {
  const src = estadoSel.value
    ? todosClientes.value.filter(c => c.estado === estadoSel.value)
    : todosClientes.value
  return [...new Set(src.map(c => c.cidade).filter(Boolean))].sort()
})

const clientesFiltrados = computed(() =>
  todosClientes.value.filter(c =>
    (!estadoSel.value || c.estado === estadoSel.value) &&
    (!cidadeSel.value || c.cidade === cidadeSel.value)
  )
)

function onEstadoChange() {
  if (cidadeSel.value && !cidadesDisponiveis.value.includes(cidadeSel.value)) {
    cidadeSel.value = ''
  }
  limparSelecao()
}
function limparSelecao() {
  clienteBusca.value = ''
  if (clienteId.value) {
    clienteId.value = ''
    form.value = null
    destruirMapa()
  }
}

function onClienteSelecionado() {
  const nome = clienteBusca.value.trim()
  if (!nome) {
    clienteId.value = ''
    form.value = null
    destruirMapa()
    return
  }
  const enc = clientesFiltrados.value.find(c => c.nome_razao_social === nome)
  if (enc) {
    clienteId.value = enc.id
    carregarCliente()
  } else {
    clienteId.value = ''
    form.value = null
    destruirMapa()
  }
}

async function carregarCliente() {
  if (!clienteId.value) return
  try {
    const c = await api.clientes.obter(clienteId.value)
    form.value = {
      nome_razao_social: c.nome_razao_social ?? '',
      telefone: c.telefone ?? '',
      pessoa_contato: c.pessoa_contato ?? '',
      cep: c.cep ?? '',
      rua: c.rua ?? '',
      numero: c.numero ?? '',
      bairro: c.bairro ?? '',
      cidade: c.cidade ?? '',
      estado: (c.estado ?? '').toUpperCase(),
      latitude: c.latitude ?? null,
      longitude: c.longitude ?? null,
      ponto_referencia: c.ponto_referencia ?? '',
      observacao: c.observacao ?? '',
      status_endereco: c.status_endereco ?? 'aprovado',
      alterado_por_nome: c.alterado_por_nome ?? null,
      alterado_por_empresa: c.alterado_por_empresa ?? null,
      alterado_em: c.alterado_em ?? null
    }
    // Assume que o número carregado é o que corresponde à posição atual do pin
    numeroDoMapa.value = c.numero ?? ''
    // Fotos anexas (separadas do form — enviadas por endpoint proprio)
    fotos.value = (c.fotos || []).slice()
    fotoErro.value = ''
    msg.value = ''
    await nextTick()
    inicializarMapa()

    // Auto-geocoding: se o cliente nao tem coords mas tem endereco,
    // busca a coordenada e posiciona o pin (nao grava nada — so visual).
    if ((c.latitude == null || c.longitude == null) && (c.rua || c.cidade || c.cep)) {
      msg.value = 'Buscando localização no mapa a partir do endereço...'
      msgTipo.value = 'ok'
      const r = await forwardGeocode()
      if (r) {
        msg.value = 'Localização sugerida pelo endereço. Ajuste o pin se necessário e salve.'
        msgTipo.value = 'ok'
      } else {
        msg.value = 'Não foi possível localizar o endereço no mapa. Ajuste o pin manualmente.'
        msgTipo.value = 'erro'
      }
    }
  } catch (e) {
    msg.value = 'Erro ao carregar cliente: ' + e.message
    msgTipo.value = 'erro'
  }
}

function inicializarMapa() {
  if (!mapaEl.value) return
  if (map) { map.remove(); map = null; marker = null }

  const temCoords = form.value.latitude != null && form.value.longitude != null
  const centro = temCoords
    ? [Number(form.value.latitude), Number(form.value.longitude)]
    : [-15.7801, -47.9292] // centro do Brasil
  const zoom = temCoords ? 16 : 4

  map = L.map('mapa-editar').setView(centro, zoom)
  L.tileLayer(tileUrl(), {
    attribution: tileAttribution(),
    maxZoom: tileMaxZoom()
  }).addTo(map)

  marker = temCoords
    ? L.marker(centro, { draggable: !somenteLeitura.value }).addTo(map)
    : L.marker(centro, { draggable: !somenteLeitura.value, opacity: 0 }).addTo(map)

  marker.on('dragend', async () => {
    const ll = marker.getLatLng()
    setarCoordenadas(ll.lat, ll.lng)
    if (marker.options.opacity === 0) marker.setOpacity(1)
    await reverseGeocode(ll.lat, ll.lng)
  })
}

function destruirMapa() {
  if (map) { map.remove(); map = null; marker = null }
}

onBeforeUnmount(destruirMapa)

function setarCoordenadas(lat, lng) {
  if (!form.value) return
  form.value.latitude = Number(lat.toFixed(8))
  form.value.longitude = Number(lng.toFixed(8))
}

function pegarLocalizacao() {
  if (!navigator.geolocation) {
    geo.erro = 'Geolocalização não suportada neste navegador.'
    return
  }
  geo.loading = true
  geo.erro = ''
  navigator.geolocation.getCurrentPosition(
    async (pos) => {
      geo.loading = false
      const lat = pos.coords.latitude
      const lng = pos.coords.longitude
      setarCoordenadas(lat, lng)
      if (!map) inicializarMapa()
      map.setView([lat, lng], 17)
      if (!marker) {
        marker = L.marker([lat, lng], { draggable: true }).addTo(map)
        marker.on('dragend', async () => {
          const ll = marker.getLatLng()
          setarCoordenadas(ll.lat, ll.lng)
          await reverseGeocode(ll.lat, ll.lng)
        })
      } else {
        marker.setLatLng([lat, lng])
        marker.setOpacity(1)
      }
      await reverseGeocode(lat, lng)
    },
    (err) => {
      geo.loading = false
      geo.erro = 'Não foi possível obter a localização: ' + err.message
    },
    { enableHighAccuracy: true, timeout: 10000 }
  )
}

// Reverse geocoding via Nominatim (OpenStreetMap) — gratuito, sem chave de API
async function reverseGeocode(lat, lng) {
  // Limpa o numero IMEDIATAMENTE (antes do fetch) — garante consistencia
  // mesmo se o geocoder rate-limitar, timeout ou falhar a rede.
  form.value.numero = ''
  numeroDoMapa.value = ''

  clearTimeout(geocodingTimeout)
  geocodingTimeout = setTimeout(async () => {
    try {
      const a = await reverseGeocodeExternal(lat, lng)
      if (!a) return
      if (a.cep) form.value.cep = a.cep
      if (a.rua) form.value.rua = a.rua
      if (a.numero) {
        form.value.numero = a.numero
        numeroDoMapa.value = a.numero
      }
      if (a.bairro) form.value.bairro = a.bairro
      if (a.cidade) form.value.cidade = a.cidade
      if (a.estado) form.value.estado = a.estado
    } catch {
      // ignora erro de rede
    }
  }, 600)
}

// Status do endereco vindo do cliente (p/ badge)
const clienteStatus = computed(() => form.value?.status_endereco || 'aprovado')

// Cliente com alteracao pendente de aprovacao nao pode ser editado
const somenteLeitura = computed(() => form.value?.status_endereco === 'atualizando')

function formatarData(iso) {
  if (!iso) return '—'
  try { return new Date(iso).toLocaleString('pt-BR') } catch { return iso }
}

// Nome do usuario com a empresa para identificacao (ex: "Joao (AC)")
function nomeComEmpresa(nome, empresa) {
  const n = nome || ''
  const e = empresa || ''
  return e ? `${n} (${e})` : n
}

// Endereço completo montado a partir dos campos do formulário (reativo)
const enderecoCompleto = computed(() => {
  const f = form.value
  if (!f) return ''
  const partes = [
    [f.rua, f.numero].filter(Boolean).join(', '),
    f.bairro,
    [f.cidade, f.estado].filter(Boolean).join(' - '),
    f.cep
  ].filter(Boolean)
  return partes.join(', ') + (partes.length ? ', Brasil' : '')
})

// Endereço que o mapa "resolveu" para a posição atual do pin. Usa o numeroDoMapa
// (que pode divergir do digitado) para que o link reflita a posição física exata.
const enderecoPin = computed(() => {
  const f = form.value
  if (!f) return ''
  const num = numeroDoMapa.value || f.numero
  const partes = [
    [f.rua, num].filter(Boolean).join(', '),
    f.bairro,
    [f.cidade, f.estado].filter(Boolean).join(' - '),
    f.cep
  ].filter(Boolean)
  return partes.join(', ') + (partes.length ? ', Brasil' : '')
})

const temCoords = computed(() =>
  form.value && form.value.latitude != null && form.value.longitude != null
)

// Links "pelo pin no mapa": usam a coordenada exata (precisão) mas passam o endereço
// como query textual para o app exibir o nome da rua em vez de só lat/lng.
const wazeUrl = computed(() => {
  const f = form.value
  if (!f || !temCoords.value || !enderecoPin.value) return '#'
  return `https://waze.com/ul?ll=${f.latitude},${f.longitude}&q=${encodeURIComponent(enderecoPin.value)}&navigate=yes`
})

const mapsCoordUrl = computed(() => {
  const f = form.value
  if (!f) return '#'
  // Maps aceita query textual — usa o endereço do pin (mostra endereço, não coords cruas)
  if (enderecoPin.value) return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(enderecoPin.value)}`
  if (temCoords.value) return `https://www.google.com/maps/search/?api=1&query=${f.latitude},${f.longitude}`
  return '#'
})

const osmUrl = computed(() => {
  const f = form.value
  if (!f) return '#'
  if (temCoords.value) return `https://www.openstreetmap.org/?mlat=${f.latitude}&mlon=${f.longitude}#map=17/${f.latitude}/${f.longitude}`
  if (enderecoPin.value) return `https://www.openstreetmap.org/search?query=${encodeURIComponent(enderecoPin.value)}`
  return '#'
})

// URLs pelo endereço digitado (texto) — usam o número informado, não o do pin
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
    // fallback para navegadores sem clipboard API
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

// Máscara de telefone (XX) 9 9999-9999
function onTelefoneInput(evt) {
  const digitos = (evt.target.value || '').replace(/\D/g, '').slice(0, 11)
  let out = ''
  if (digitos.length > 0) out = '(' + digitos.slice(0, 2)
  if (digitos.length >= 2) out += ') '
  if (digitos.length > 2) {
    // 9 obrigatório nowadays em BR; se houver 11 dígitos, formato com 9 extra
    const rest = digitos.slice(2)
    // Se 9 dígitos: 9 9999-9999 (1+4-4); se 8: 9999-9999
    if (rest.length > 9) {
      out += rest.slice(0, 1) + ' ' + rest.slice(1, 5) + '-' + rest.slice(5, 9)
    } else if (rest.length > 4) {
      out += rest.slice(0, rest.length - 4) + '-' + rest.slice(rest.length - 4)
    } else {
      out += rest
    }
  }
  form.value.telefone = out
}

// Forward geocoding (OpenCage em produção, Nominatim no fallback dev) —
// reposiciona o pin a partir do endereço digitado
async function forwardGeocode() {
  const f = form.value
  if (!f) return null
  const partes = [f.numero, f.rua, f.bairro, f.cidade, f.estado, 'Brasil'].filter(Boolean)
  if (partes.length < 2) return null
  const q = partes.join(', ')
  try {
    const r = await forwardGeocodeExternal(q)
    if (!r) return null
    setarCoordenadas(r.lat, r.lng)
    if (marker) {
      marker.setLatLng([r.lat, r.lng])
      marker.setOpacity(1)
    }
    if (map) map.setView([r.lat, r.lng], 17)
    // Atualiza o "número do mapa" para o digitado (agora consistente)
    numeroDoMapa.value = f.numero
    return { lat: r.lat, lng: r.lng }
  } catch {
    return null
  }
}

// Verifica divergência entre o número digitado e a posição física do pin
function haDivergenciaNumero() {
  const f = form.value
  if (!f) return false
  const digitado = (f.numero || '').trim()
  const doMapa = (numeroDoMapa.value || '').trim()
  // Só sinaliza divergência quando há número digitado E ele difere do mapa
  if (!digitado) return false
  if (!doMapa) return false
  return digitado !== doMapa
}

function abrirModalDivergencia() {
  return new Promise((resolve) => {
    modal.numeroMapa = numeroDoMapa.value
    modal.numeroDigitado = (form.value.numero || '').trim()
    modal.latitudeMapa = form.value.latitude
    modal.longitudeMapa = form.value.longitude
    modal.erroRepos = ''
    modal.resolve = resolve
    modal.aberto = true
  })
}

function fecharModal(resultado) {
  modal.aberto = false
  if (modal.resolve) {
    modal.resolve(resultado)
    modal.resolve = null
  }
}

async function modalSalvarAssim() {
  fecharModal('salvar')
}

async function modalReposicionar() {
  modal.reposicionando = true
  modal.erroRepos = ''
  const r = await forwardGeocode()
  modal.reposicionando = false
  if (!r) {
    modal.erroRepos = 'Não foi possível encontrar as coordenadas para esse endereço. Salve assim mesmo ou ajuste o pin manualmente.'
    return
  }
  fecharModal('salvar')
}

function modalCancelar() {
  fecharModal('cancelar')
}

// --- Fotos ---
async function onFotoFile(e) {
  const file = e.target.files?.[0]
  e.target.value = ''
  if (!file || !clienteId.value) return
  uploading.value = true
  fotoErro.value = ''
  try {
    const f = await api.clientes.uploadFoto(clienteId.value, file)
    fotos.value = [f, ...fotos.value]
  } catch (err) {
    fotoErro.value = err.message || 'Falha no upload'
  } finally {
    uploading.value = false
  }
}

async function removerFoto(f) {
  if (!confirm('Remover esta foto?')) return
  try {
    await api.clientes.deletarFoto(clienteId.value, f.id)
    fotos.value = fotos.value.filter(x => x.id !== f.id)
  } catch (err) {
    fotoErro.value = err.message || 'Falha ao remover'
  }
}

function abrirFoto(url) {
  window.open(url, '_blank', 'noopener')
}

async function salvar() {
  if (!form.value || !clienteId.value) return
  if (somenteLeitura.value) return

  // Se o número digitado difere da posição física do pin, confirma antes de salvar
  if (haDivergenciaNumero()) {
    const decisao = await abrirModalDivergencia()
    if (decisao !== 'salvar') return // usuário cancelou
  }

  salvando.value = true
  msg.value = ''
  try {
    const payload = {
      ...form.value,
      estado: (form.value.estado || '').toUpperCase(),
      latitude: form.value.latitude === '' ? null : form.value.latitude,
      longitude: form.value.longitude === '' ? null : form.value.longitude
    }
    // Remove campos que sao apenas apresentacao (_backend controla por perms)
    delete payload.status_endereco
    delete payload.alterado_por_nome
    delete payload.alterado_por_empresa
    delete payload.alterado_em
    await api.clientes.atualizar(clienteId.value, payload)
    // Recarrega o cliente para atualizar status/banner pos-save
    await carregarCliente()
    msg.value = clienteStatus.value === 'atualizando'
      ? 'Submissão enviada para aprovação!'
      : 'Cliente atualizado com sucesso!'
    msgTipo.value = 'ok'
  } catch (e) {
    msg.value = 'Erro ao salvar: ' + e.message
    msgTipo.value = 'erro'
  } finally {
    salvando.value = false
  }
}
</script>

<style scoped>
.page { padding: 1.5rem 1rem 2.5rem; }
.container { max-width: 1000px; margin: 0 auto; }

.page-head { margin-bottom: 1rem; }
.page-head h1 { font-size: 1.5rem; font-weight: 700; color: #0f172a; letter-spacing: -0.02em; }
.page-head p { color: #64748b; font-size: 0.9rem; margin-top: 0.2rem; }

.card { background: #fff; border-radius: 16px; padding: 1.1rem 1.25rem; box-shadow: card; border: 1px solid #eef2f8; margin-bottom: 1rem; }

.grid3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.9rem; }
@media (max-width: 720px) { .grid3 { grid-template-columns: 1fr; } }

.field { margin-bottom: 0.8rem; }
.field label { display: block; font-size: 0.78rem; font-weight: 600; color: #475569; margin-bottom: 0.3rem; }
.field input, .field select {
  width: 100%; padding: 0.55rem 0.7rem;
  border: 1px solid #dbe2ee; border-radius: 8px;
  font-size: 0.92rem; outline: none; background: #fff; transition: all 0.15s;
}
.field input:focus, .field select:focus { border-color: #1f5bf0; box-shadow: 0 0 0 4px rgba(31,91,240,0.12); }
.uf { text-transform: uppercase; }

.form-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 0.4rem 0.9rem; }
.col2 { grid-column: span 2; }
.full { grid-column: 1 / -1; }
@media (max-width: 720px) { .form-grid { grid-template-columns: 1fr; } .col2 { grid-column: auto; } }

.geo-section { margin-top: 1.25rem; padding-top: 1rem; border-top: 1px solid #eef2f8; }
.geo-head { display: flex; align-items: center; justify-content: space-between; gap: 1rem; flex-wrap: wrap; }
.geo-head h3 { font-size: 1rem; font-weight: 700; color: #1d2a4d; }

/* Banner de status */
.status-banner {
  display: flex; align-items: center; gap: 0.6rem;
  padding: 0.7rem 0.9rem; border-radius: 10px; margin-bottom: 1rem;
  font-size: 0.88rem; border: 1px solid; line-height: 1.35;
}
.status-banner .status-icon { font-size: 1.3rem; }
.status-atualizando { background: #fffbeb; color: #92400e; border-color: #fde68a; }
.status-aprovado { background: #ecfdf5; color: #065f46; border-color: #a7f3d0; }

/* Modo somente leitura (alteração pendente de aprovação) */
.fs-lock { border: 0; padding: 0; margin: 0; min-width: 0; }
.lock-banner {
  display: flex; align-items: center; gap: 0.6rem;
  padding: 0.7rem 0.9rem; border-radius: 10px; margin-bottom: 1rem;
  font-size: 0.88rem; line-height: 1.35;
  background: #fef2f2; color: #b91c1c; border: 1px solid #fecaca;
}
.lat-info { font-size: 0.85rem; color: #64748b; margin: 0.4rem 0 0.7rem; }
.erro-inline { color: #b91c1c; }

.mapa { width: 100%; height: 360px; border-radius: 12px; overflow: hidden; border: 1px solid #e8eaf0; }
.mapa-acoes { display: flex; align-items: center; justify-content: space-between; gap: 1rem; margin-top: 0.5rem; flex-wrap: wrap; }
.dica-map { font-size: 0.78rem; color: #94a3b8; margin: 0; flex: 1; min-width: 200px; }
.btn-sm { padding: 0.4rem 0.75rem; font-size: 0.8rem; }

.aviso-divergencia {
  margin-top: 0.7rem; padding: 0.6rem 0.8rem; border-radius: 8px;
  background: #fffbeb; border: 1px solid #fde68a; color: #92400e; font-size: 0.82rem; line-height: 1.35;
}

/* Modal de divergência */
.modal-overlay {
  position: fixed; inset: 0; background: rgba(15, 23, 42, 0.55);
  display: flex; align-items: center; justify-content: center; padding: 1rem; z-index: 1000;
  backdrop-filter: blur(2px);
  overflow-y: auto;
}
.modal-card {
  background: #fff; border-radius: 16px; padding: 1.25rem; max-width: 520px; width: 100%;
  box-shadow: 0 30px 70px -20px rgba(15, 23, 42, 0.45);
  animation: modal-in 0.18s ease-out;
  max-height: calc(100vh - 2rem);
  overflow-y: auto;
  margin: auto;
}
.modal-card h3 { font-size: 1.1rem; font-weight: 700; color: #0f172a; margin-bottom: 0.5rem; }
.modal-text { font-size: 0.88rem; color: #334155; margin: 0.35rem 0; line-height: 1.45; }
.erro-repos {
  margin: 0.55rem 0; padding: 0.55rem 0.75rem; border-radius: 8px;
  background: #fef2f2; color: #b91c1c; font-size: 0.82rem; border: 1px solid #fecaca;
}
.modal-botoes { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 0.9rem; }
.modal-botoes .btn { flex: 1 1 200px; min-width: 0; }
.btn-outline-blue { background: #fff; border: 1px solid #1f5bf0; color: #1f5bf0; }
.btn-outline-blue:hover { background: #eef6ff; }
.modal-hint {
  margin-top: 0.75rem; font-size: 0.74rem; color: #94a3b8; line-height: 1.4;
}
@keyframes modal-in {
  from { opacity: 0; transform: translateY(8px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}
/* Mobile: botões em coluna, card ocupa a largura disponível com scroll */
@media (max-width: 540px) {
  .modal-overlay { padding: 0.5rem; }
  .modal-card { padding: 1rem; border-radius: 14px; }
  .modal-botoes .btn { flex: 1 1 100%; }
}

/* Endereço completo para navegação */
.endereco-full {
  margin-top: 0.9rem; padding: 0.9rem; border-radius: 10px;
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

.nav-group { margin-top: 0.7rem; padding: 0.55rem 0.7rem; border-radius: 8px; background: #fff; border: 1px solid #eaf1fb; }
.nav-group.divergente { background: #fffbeb; border-color: #fde68a; }
.nav-group-label {
  display: flex; align-items: center; gap: 0.45rem;
  font-size: 0.78rem; font-weight: 600; color: #475569; flex-wrap: wrap;
}
.nav-coords { margin-left: auto; font-size: 0.72rem; color: #94a3b8; font-weight: 400; }
.dot { display: inline-block; width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; }
.dot.pin { background: #33a0ff; }
.dot.texto { background: #f59e0b; }

.endereco-hint { font-size: 0.72rem; color: #94a3b8; margin-top: 0.6rem; line-height: 1.4; }

/* Fotos do local */
.fotos-section { margin-top: 1.2rem; padding-top: 1rem; border-top: 1px solid #eef2f8; }
.fotos-head h3 { font-size: 1rem; font-weight: 700; color: #1d2a4d; }
.fotos-hint { font-size: 0.78rem; color: #94a3b8; margin-top: 0.15rem; margin-bottom: 0.7rem; }
.fotos-botoes { display: flex; flex-wrap: wrap; gap: 0.5rem; align-items: center; }
.hidden-input { position: absolute; width: 1px; height: 1px; opacity: 0; overflow: hidden; }
.upload-msg { font-size: 0.8rem; color: #64748b; }
.placeholder-fotos { font-size: 0.82rem; color: #94a3b8; font-style: italic; margin-top: 0.7rem; }
.fotos-galeria {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
  gap: 0.6rem;
  margin-top: 0.7rem;
}
.foto-item {
  position: relative;
  border-radius: 10px;
  overflow: hidden;
  aspect-ratio: 1;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  cursor: pointer;
  transition: transform 0.15s;
}
.foto-item:hover { transform: scale(1.03); }
.foto-item img {
  width: 100%; height: 100%;
  object-fit: cover;
  display: block;
}
.foto-del {
  position: absolute; top: 4px; right: 4px;
  width: 24px; height: 24px;
  border-radius: 50%;
  background: rgba(15, 23, 42, 0.7);
  color: #fff; font-size: 1rem; line-height: 1;
  border: none; cursor: pointer;
  display: inline-flex; align-items: center; justify-content: center;
  padding: 0;
  transition: background 0.15s;
}
.foto-del:hover { background: #dc2626; }
.foto-del:disabled { opacity: 0.5; cursor: not-allowed; }

textarea {
  width: 100%; padding: 0.55rem 0.7rem;
  border: 1px solid #dbe2ee; border-radius: 8px;
  font-size: 0.9rem; outline: none; background: #fff;
  resize: vertical; min-height: 60px; font-family: inherit;
  transition: all 0.15s; box-sizing: border-box;
}
textarea:focus { border-color: #1f5bf0; box-shadow: 0 0 0 4px rgba(31,91,240,0.12); }

.acoes { display: flex; align-items: center; gap: 1rem; margin-top: 1.1rem; flex-wrap: wrap; }
.msg { font-size: 0.85rem; }
.msg.ok { color: #15803d; }
.msg.erro { color: #b91c1c; }

.btn { padding: 0.6rem 1rem; border-radius: 9px; cursor: pointer; font-weight: 600; font-size: 0.88rem; border: none; }
.btn-primary { background: linear-gradient(135deg, #3479fb, #1746dc); color: #fff; box-shadow: 0 10px 20px -8px rgba(23,70,220,0.7); }
.btn-secondary { background: #eef6ff; color: #1746dc; border: 1px solid #bcdcff; }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-secondary:disabled { opacity: 0.6; cursor: not-allowed; }

.placeholder { text-align: center; padding: 2.5rem 1rem; color: #94a3b8; }
.placeholder .empty-icon { font-size: 2.2rem; margin-bottom: 0.4rem; }
.placeholder h3 { color: #64748b; font-size: 1rem; margin: 0.2rem 0; }
.placeholder p { font-size: 0.85rem; max-width: 320px; margin: 0 auto; }

/* Mobile: ajustes de espaçamento e input do endereço */
@media (max-width: 540px) {
  .endereco-row { flex-direction: column; gap: 0.4rem; }
  .endereco-row .btn-sm { width: 100%; }
  .nav-coords { margin-left: 0; width: 100%; }
  .mapa { height: 280px; }
  .mapa-acoes { flex-direction: column; align-items: stretch; gap: 0.5rem; }
  .mapa-acoes .dica-map { min-width: 0; }
}
</style>