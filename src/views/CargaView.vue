<template>
  <div class="page">
    <div class="container">
      <div class="page-head">
        <h1>Carga em Massa via Excel</h1>
        <p>
          Suba uma planilha .xlsx com clientes. A coluna <strong>codigo</strong> é a chave:
          se já existe, o registro é atualizado; se não, é criado.
        </p>
        <p class="sub">
          📍 Uma linha por <strong>endereço</strong>: o mesmo código pode repetir em várias linhas
          (uma por loja/endereço). Cada linha pode ter até 3 contatos
          (colunas <code>contato1_nome</code> ... <code>contato3_telefone</code>).
        </p>
      </div>

      <!-- Download do template -->
      <section class="card">
        <h2 class="section-title">1. Baixar template (opcional)</h2>
        <p class="hint">Use este modelo com as colunas corretas para preencher e reenviar.</p>
        <button class="btn btn-secondary" @click="baixarTemplate">📥 Baixar template .xlsx</button>
      </section>

      <!-- Upload -->
      <section class="card">
        <h2 class="section-title">2. Selecionar planilha</h2>
        <div class="upload-zone" @click="$refs.fileInput.click()" @dragover.prevent="dragOver = true" @dragleave="dragOver = false" @drop.prevent="onDrop">
          <input ref="fileInput" type="file" accept=".xlsx,.xls" @change="onFileChange" class="hidden" />
          <div class="upload-inner" :class="{ over: dragOver }">
            <div class="upload-icon">📊</div>
            <p v-if="!arquivo">Clique ou arraste um arquivo .xlsx aqui</p>
            <p v-else class="file-name">📄 {{ arquivo.name }} ({{ Math.round(arquivo.size / 1024) }} KB)</p>
          </div>
        </div>
        <button v-if="arquivo" class="btn btn-primary mt" @click="preview" :disabled="processando">
          {{ processando ? 'Processando...' : '🔍 Analisar planilha' }}
        </button>
        <span v-if="erro" class="msg erro">{{ erro }}</span>
      </section>

      <!-- Preview -->
      <section v-if="previewData" class="card">
        <h2 class="section-title">3. Preview da carga</h2>
        <div class="resumo">
          <div class="resumo-item">
            <span class="resumo-num">{{ previewData.total_linhas }}</span>
            <span>Total de linhas</span>
          </div>
          <div class="resumo-item novo">
            <span class="resumo-num">{{ previewData.quantidade_novos }}</span>
            <span>Novos (inserir)</span>
          </div>
          <div class="resumo-item alterado">
            <span class="resumo-num">{{ previewData.quantidade_alterados }}</span>
            <span>Alterar (atualizar)</span>
          </div>
        </div>

        <!-- Novos -->
        <div v-if="previewData.novos.length" class="grupo">
          <h3 class="grupo-title novo">➕ Novos clientes ({{ previewData.novos.length }})</h3>
          <div class="table-wrap">
            <table class="table">
              <thead>
                <tr>
                  <th>Codigo</th><th>Nome</th><th>Telefone</th><th>Endereços</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(n, i) in previewData.novos" :key="i">
                  <td><code>{{ n.codigo || '—' }}</code></td>
                  <td><strong>{{ n.nome_razao_social }}</strong></td>
                  <td>{{ n.telefone || '—' }}</td>
                  <td>
                    <div v-for="(e, k) in n.enderecos || []" :key="k" class="endresumo">
                      <span class="chip">{{ e.nome || `Endereço ${k + 1}` }}</span>
                      <span class="endlinha">{{ [e.rua, e.numero].filter(Boolean).join(', ') || '—' }} · {{ e.cidade || '' }} {{ e.estado || '' }}</span>
                      <span v-if="(e.contatos || []).length" class="endcontatos">📞 {{ e.contatos.map(c => c.nome).join(', ') }}</span>
                    </div>
                    <span v-if="!n.enderecos || !n.enderecos.length" class="muted">sem endereço</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Alterados -->
        <div v-if="previewData.alterados.length" class="grupo">
          <h3 class="grupo-title alterado">✏️ Alterações ({{ previewData.alterados.length }})</h3>
          <div class="table-wrap">
            <table class="table">
              <thead>
                <tr>
                  <th>Codigo</th><th>Nome</th><th>Campos alterados</th><th>De → Para</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(a, i) in previewData.alterados" :key="i">
                  <td><code>{{ a.codigo }}</code></td>
                  <td><strong>{{ a.nome_razao_social }}</strong></td>
                  <td>
                    <span v-for="(_, campo) in a.mudancas" :key="campo" class="chip">{{ campo }}</span>
                  </td>
                  <td>
                    <div v-for="(m, campo) in a.mudancas" :key="campo" class="diff">
                      <code>{{ m.de ?? '∅' }}</code> → <code>{{ m.para ?? '∅' }}</code>
                    </div>
                    <div v-if="a.enderecos && a.enderecos.length" class="endresumo-wrap">
                      <div v-for="(e, k) in a.enderecos" :key="k" class="endresumo">
                        <span class="chip">{{ e.nome || `Endereço ${k + 1}` }}</span>
                        <span class="endlinha">{{ [e.rua, e.numero].filter(Boolean).join(', ') || '—' }} · {{ e.cidade || '' }} {{ e.estado || '' }}</span>
                        <span v-if="(e.contatos || []).length" class="endcontatos">📞 {{ e.contatos.map(c => c.nome).join(', ') }}</span>
                      </div>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="acoes">
          <button class="btn btn-primary" @click="aplicar" :disabled="aplicando">
            {{ aplicando ? 'Aplicando...' : `✓ Confirmar e aplicar (${previewData.total_linhas})` }}
          </button>
          <button class="btn btn-secondary" @click="limpar">Cancelar</button>
          <span v-if="aplicarResult" :class="['msg', 'ok']">
            ✓ {{ aplicarResult.inseridos }} inseridos, {{ aplicarResult.atualizados }} atualizados
          </span>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { api } from '../api'
import { temPermissao } from '../composables/useAuth'

const arquivo = ref(null)
const previewData = ref(null)
const aplicarResult = ref(null)
const processando = ref(false)
const aplicando = ref(false)
const erro = ref('')
const dragOver = ref(false)

function onFileChange(e) {
  const f = e.target.files[0]
  if (f) { arquivo.value = f; erro.value = ''; previewData.value = null; aplicarResult.value = null }
}

function onDrop(e) {
  dragOver.value = false
  const f = e.dataTransfer.files[0]
  if (f) { arquivo.value = f; erro.value = ''; previewData.value = null; aplicarResult.value = null }
}

async function preview() {
  if (!arquivo.value) return
  processando.value = true
  erro.value = ''
  previewData.value = null
  aplicarResult.value = null
  try {
    previewData.value = await api.clientes.previewCarga(arquivo.value)
  } catch (e) {
    erro.value = e.message
  } finally {
    processando.value = false
  }
}

async function aplicar() {
  if (!arquivo.value) return
  aplicando.value = true
  erro.value = ''
  try {
    aplicarResult.value = await api.clientes.aplicarCarga(arquivo.value)
    previewData.value = null
    arquivo.value = null
  } catch (e) {
    erro.value = e.message
  } finally {
    aplicando.value = false
  }
}

function limpar() {
  arquivo.value = null
  previewData.value = null
  aplicarResult.value = null
  erro.value = ''
}

function baixarTemplate() {
  // Gera um CSV simples com as colunas esperadas para preenchimento
  // (uma linha por endereço; repita o codigo para mais endereços).
  const colunas = [
    'codigo','nome_razao_social','telefone','pessoa_contato',
    'endereco_apelido','cep','rua','numero','bairro','cidade','estado','latitude','longitude',
    'ponto_referencia','observacao',
    'contato1_nome','contato1_telefone','contato2_nome','contato2_telefone',
    'contato3_nome','contato3_telefone'
  ]
  const csv = colunas.join(',') + '\n' +
    'C100,Exemplo Ltda,(11) 9 9999-9999,Joao,Loja 01,01000-000,R. Exemplo,100,Cairro,Sao Paulo,SP,-23.5,-46.6,Perto do mercado,,\n' +
    'C100,,,Fulano,Loja 02,02000-000,Av. Outra,200,Centro,Sao Paulo,SP,,,Cicrano,(11) 9 8888-7777,'
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'template_clientes.csv'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
</script>

<style scoped>
.page { padding: 1.5rem 1rem 2.5rem; }
.container { max-width: 1000px; margin: 0 auto; }
.page-head { margin-bottom: 1.25rem; }
.page-head h1 { font-size: 1.5rem; font-weight: 700; color: #0f172a; }
.page-head p { color: #64748b; font-size: 0.88rem; margin-top: 0.2rem; }
.page-head .sub { font-size: 0.82rem; color: #64748b; margin-top: 0.4rem; line-height: 1.5; }
.page-head .sub code { background: #f1f5f9; padding: 0.1rem 0.35rem; border-radius: 4px; font-size: 0.76rem; }
.card { background: #fff; border-radius: 16px; padding: 1.25rem; box-shadow: 0 10px 30px -12px rgba(20,40,90,0.18); border: 1px solid #eef2f8; margin-bottom: 1.1rem; }
.section-title { font-size: 1rem; font-weight: 700; color: #1d2a4d; margin-bottom: 0.9rem; padding-bottom: 0.6rem; border-bottom: 1px solid #eef2f8; }
.hint { font-size: 0.82rem; color: #94a3b8; margin-bottom: 0.7rem; }

.upload-zone { border: 2px dashed #bcdcff; border-radius: 12px; padding: 1.5rem; cursor: pointer; transition: all 0.15s; }
.upload-zone:hover .upload-inner { background: #f1f7ff; }
.upload-inner { border-radius: 10px; padding: 1rem; text-align: center; transition: all 0.15s; }
.upload-inner.over { background: #eef6ff; border-radius: 10px; }
.upload-icon { font-size: 2.5rem; margin-bottom: 0.5rem; }
.upload-inner p { color: #64748b; font-size: 0.9rem; }
.file-name { color: #1f5bf0 !important; font-weight: 600; }
.hidden { display: none; }
.mt { margin-top: 0.8rem; }

.resumo { display: flex; gap: 1rem; margin-bottom: 1.25rem; flex-wrap: wrap; }
.resumo-item { display: flex; flex-direction: column; align-items: center; padding: 0.9rem 1.2rem; border-radius: 12px; background: #f1f5f9; min-width: 120px; }
.resumo-item.novo { background: #dcfce7; }
.resumo-item.alterado { background: #fef3c7; }
.resumo-num { font-size: 1.8rem; font-weight: 700; }
.resumo-item.novo .resumo-num { color: #15803d; }
.resumo-item.alterado .resumo-num { color: #b45309; }
.resumo-item span:last-child { font-size: 0.78rem; color: #64748b; }

.grupo { margin-bottom: 1.25rem; }
.grupo-title { font-size: 0.95rem; font-weight: 700; margin-bottom: 0.5rem; padding-bottom: 0.4rem; border-bottom: 2px solid #eef2f8; }
.grupo-title.novo { color: #15803d; border-color: #dcfce7; }
.grupo-title.alterado { color: #b45309; border-color: #fef3c7; }

.table-wrap { overflow-x: auto; }
.table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
.table th { text-align: left; padding: 0.5rem 0.6rem; border-bottom: 2px solid #eef2f8; color: #64748b; font-weight: 600; font-size: 0.72rem; text-transform: uppercase; }
.table td { padding: 0.5rem 0.6rem; border-bottom: 1px solid #f1f5f9; vertical-align: top; }
.table code { background: #f1f5f9; padding: 0.1rem 0.35rem; border-radius: 4px; font-size: 0.78rem; }
.chip { display: inline-block; padding: 0.1rem 0.4rem; border-radius: 5px; font-size: 0.7rem; font-weight: 600; background: #eef6ff; color: #1746dc; margin: 0.1rem; }
.diff { font-size: 0.75rem; color: #64748b; margin-bottom: 0.15rem; }
.endresumo-wrap { display: flex; flex-direction: column; gap: 0.4rem; margin-top: 0.4rem; }
.endresumo { display: flex; flex-direction: column; gap: 0.1rem; padding: 0.35rem 0.5rem; border-left: 3px solid #d9eaff; background: #fafcff; border-radius: 6px; margin-bottom: 0.3rem; }
.endlinha { font-size: 0.78rem; color: #334155; }
.endcontatos { font-size: 0.72rem; color: #64748b; }
.muted { font-size: 0.75rem; color: #94a3b8; font-style: italic; }

.acoes { display: flex; align-items: center; gap: 0.7rem; margin-top: 1rem; flex-wrap: wrap; }
.msg { font-size: 0.85rem; }
.msg.ok { color: #15803d; font-weight: 600; }
.msg.erro { color: #b91c1c; }
.btn { padding: 0.55rem 1rem; border-radius: 9px; cursor: pointer; font-weight: 600; font-size: 0.88rem; border: none; display: inline-block; }
.btn-primary { background: linear-gradient(135deg, #3479fb, #1746dc); color: #fff; box-shadow: 0 8px 18px -8px rgba(23,70,220,0.6); }
.btn-secondary { background: #eef6ff; color: #1746dc; border: 1px solid #bcdcff; }
.btn:disabled { opacity: 0.6; cursor: not-allowed; }
</style>