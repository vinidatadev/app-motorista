<template>
  <div class="page">
    <div class="container">
      <div class="page-head">
        <h1>Cadastrar Novo Cliente</h1>
        <p>Preencha os dados do novo cliente. Os campos marcados com * são obrigatórios.</p>
      </div>

      <section v-if="form" class="card form-card">
        <!-- Dados gerais do cliente -->
        <div class="secao-titulo">
          <h2>Dados do cliente</h2>
        </div>
        <div class="form-grid">
          <div class="field">
            <label>Código (chave para carga em massa)</label>
            <input v-model="form.codigo" placeholder="ex: C100" />
          </div>
          <div class="field col2">
            <label>Nome / Razão Social *</label>
            <input v-model="form.nome_razao_social" placeholder="Nome do cliente" />
          </div>
          <div class="field">
            <label>Telefone</label>
            <input :value="form.telefone" @input="onTelefoneInput" placeholder="(00) 0 0000-0000" />
          </div>
          <div class="field">
            <label>Pessoa de Contato</label>
            <input v-model="form.pessoa_contato" />
          </div>
        </div>

        <!-- Endereços e contatos -->
        <div class="secao-titulo">
          <h2>Endereços e contatos</h2>
          <p>Um cliente pode ter várias lojas/endereços. Cada endereço pode ter vários contatos.</p>
        </div>

        <div class="enderecos">
          <div
            v-for="(end, i) in form.enderecos"
            :key="i"
            class="endereco-card"
          >
            <div class="endereco-head">
              <h3>🏬 {{ end.nome || `Endereço ${i + 1}` }}</h3>
              <button
                class="btn btn-danger btn-sm"
                @click="removerEndereco(i)"
                title="Remover endereço"
              >× Remover</button>
            </div>

            <div class="form-grid">
              <div class="field">
                <label>Nome/Apelido (ex.: Loja 01)</label>
                <input v-model="end.nome" placeholder="Ex.: Loja 01, Filial Centro..." />
              </div>
              <div class="field">
                <label>CEP</label>
                <input v-model="end.cep" />
              </div>
              <div class="field">
                <label>Número</label>
                <input v-model="end.numero" />
              </div>
              <div class="field col2">
                <label>Rua</label>
                <input v-model="end.rua" />
              </div>
              <div class="field">
                <label>Bairro</label>
                <input v-model="end.bairro" />
              </div>
              <div class="field">
                <label>Cidade</label>
                <input v-model="end.cidade" />
              </div>
              <div class="field">
                <label>Estado (UF)</label>
                <input v-model="end.estado" maxlength="2" class="uf" />
              </div>
              <div class="field">
                <label>Latitude</label>
                <input v-model.number="end.latitude" type="number" step="0.00000001" />
              </div>
              <div class="field">
                <label>Longitude</label>
                <input v-model.number="end.longitude" type="number" step="0.00000001" />
              </div>
              <div class="field col2">
                <label>Ponto de Referência</label>
                <input v-model="end.ponto_referencia" placeholder="Ex.: próximo ao shopping..." />
              </div>
              <div class="field full">
                <label>Observação</label>
                <textarea v-model="end.observacao" rows="2" placeholder="Notações relevantes para o motorista..."></textarea>
              </div>
            </div>

            <!-- Contatos do endereço -->
            <div class="contatos">
              <div class="contatos-head">
                <h4>📞 Contatos deste endereço</h4>
                <button class="btn btn-secondary btn-sm" @click="adicionarContato(i)">+ Adicionar contato</button>
              </div>
              <div v-if="!end.contatos.length" class="placeholder-contatos">
                Nenhum contato. Adicione pessoas de contato desta loja/endereço.
              </div>
              <div v-for="(ct, j) in end.contatos" :key="j" class="contato-row">
                <input v-model="ct.nome" placeholder="Nome do contato" class="contato-nome" />
                <input :value="ct.telefone" @input="onContatoTelefoneInput(j, i, $event)" placeholder="(00) 0 0000-0000" class="contato-tel" />
                <button class="btn btn-danger btn-sm" @click="removerContato(i, j)" title="Remover contato">×</button>
              </div>
            </div>
          </div>
        </div>

        <button class="btn btn-secondary mt" @click="adicionarEndereco">➕ Adicionar endereço</button>

        <div class="acoes">
          <button class="btn btn-primary" @click="salvar" :disabled="salvando">
            {{ salvando ? 'Salvando...' : 'Cadastrar cliente' }}
          </button>
          <router-link to="/clientes/pesquisa" class="btn btn-secondary">Cancelar</router-link>
          <span v-if="msg" :class="['msg', msgTipo]">{{ msg }}</span>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { api } from '../api'

const router = useRouter()
const route = useRoute()
const salvando = ref(false)
const msg = ref('')
const msgTipo = ref('ok')

const novoEndereco = () => ({
  nome: '', cep: '', rua: '', numero: '', bairro: '', cidade: '', estado: '',
  latitude: null, longitude: null, ponto_referencia: '', observacao: '',
  contatos: []
})

const novoContato = () => ({ nome: '', telefone: '' })

const formInit = () => ({
  codigo: '', nome_razao_social: '', telefone: '', pessoa_contato: '',
  enderecos: [novoEndereco()]
})
const form = ref(formInit())

// Pré-preenchimento vindo de uma solicitação concluída (ex.: /cadastrar?nome=..&codigo=..&obs=..)
if (route.query.nome || route.query.codigo || route.query.obs) {
  const pre = {
    nome_razao_social: route.query.nome || '',
    codigo: route.query.codigo || '',
    observacao: route.query.obs || ''
  }
  form.value = {
    ...formInit(),
    nome_razao_social: pre.nome_razao_social,
    codigo: pre.codigo,
    enderecos: [{ ...novoEndereco(), observacao: pre.observacao }]
  }
}

function adicionarEndereco() {
  form.value.enderecos.push(novoEndereco())
}
function removerEndereco(i) {
  if (form.value.enderecos.length <= 1) {
    msg.value = 'O cliente precisa de pelo menos um endereço.'
    msgTipo.value = 'erro'
    return
  }
  form.value.enderecos.splice(i, 1)
}
function adicionarContato(i) {
  form.value.enderecos[i].contatos.push(novoContato())
}
function removerContato(i, j) {
  form.value.enderecos[i].contatos.splice(j, 1)
}

// Máscara de telefone (XX) 9 9999-9999
function mascararTelefone(v) {
  const digitos = (v || '').replace(/\D/g, '').slice(0, 11)
  let out = ''
  if (digitos.length > 0) out = '(' + digitos.slice(0, 2)
  if (digitos.length >= 2) out += ') '
  if (digitos.length > 2) {
    const rest = digitos.slice(2)
    if (rest.length > 9) {
      out += rest.slice(0, 1) + ' ' + rest.slice(1, 5) + '-' + rest.slice(5, 9)
    } else if (rest.length > 4) {
      out += rest.slice(0, rest.length - 4) + '-' + rest.slice(rest.length - 4)
    } else {
      out += rest
    }
  }
  return out
}

function onTelefoneInput(evt) {
  form.value.telefone = mascararTelefone(evt.target.value)
}

function onContatoTelefoneInput(i, j, evt) {
  form.value.enderecos[i].contatos[j].telefone = mascararTelefone(evt.target.value)
}

async function salvar() {
  if (!form.value.nome_razao_social) {
    msg.value = 'Nome/Razão Social é obrigatório'
    msgTipo.value = 'erro'
    return
  }
  salvando.value = true
  msg.value = ''
  try {
    const payload = {
      ...form.value,
      estado: (form.value.estado || '').toUpperCase(),
      enderecos: form.value.enderecos.map(e => ({
        nome: e.nome || null,
        cep: e.cep || null,
        rua: e.rua || null,
        numero: e.numero || null,
        bairro: e.bairro || null,
        cidade: e.cidade || null,
        estado: (e.estado || '').toUpperCase() || null,
        latitude: e.latitude === '' ? null : e.latitude,
        longitude: e.longitude === '' ? null : e.longitude,
        ponto_referencia: e.ponto_referencia || null,
        observacao: e.observacao || null,
        contatos: e.contatos
          .filter(c => (c.nome || '').trim())
          .map(c => ({ nome: c.nome.trim(), telefone: c.telefone || null }))
      }))
    }
    if (!payload.codigo) delete payload.codigo
    await api.clientes.criar(payload)
    msg.value = 'Cliente cadastrado com sucesso!'
    msgTipo.value = 'ok'
    form.value = formInit()
    setTimeout(() => router.push('/clientes/pesquisa'), 1200)
  } catch (e) {
    msg.value = 'Erro: ' + e.message
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
.page-head h1 { font-size: 1.5rem; font-weight: 700; color: #0f172a; }
.page-head p { color: #64748b; font-size: 0.88rem; margin-top: 0.2rem; }

.card { background: #fff; border-radius: 16px; padding: 1.25rem; box-shadow: 0 10px 30px -12px rgba(20,40,90,0.18); border: 1px solid #eef2f8; }
.secao-titulo { margin-top: 0.5rem; margin-bottom: 0.9rem; padding-bottom: 0.6rem; border-bottom: 1px solid #eef2f8; }
.secao-titulo h2 { font-size: 1.05rem; font-weight: 700; color: #1d2a4d; }
.secao-titulo p { font-size: 0.78rem; color: #94a3b8; margin-top: 0.15rem; }

.form-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 0.4rem 0.9rem; }
.col2 { grid-column: span 2; }
.full { grid-column: 1 / -1; }
@media (max-width: 720px) { .form-grid { grid-template-columns: 1fr; } .col2 { grid-column: auto; } }
.field { margin-bottom: 0.8rem; }
.field label { display: block; font-size: 0.78rem; font-weight: 600; color: #475569; margin-bottom: 0.3rem; }
.field input, .field textarea {
  width: 100%; padding: 0.5rem 0.7rem; border: 1px solid #dbe2ee; border-radius: 8px;
  font-size: 0.9rem; outline: none; background: #fff; transition: all 0.15s;
  box-sizing: border-box; font-family: inherit;
}
.field input:focus, .field textarea:focus { border-color: #1f5bf0; box-shadow: 0 0 0 4px rgba(31,91,240,0.12); }
.field textarea { resize: vertical; min-height: 50px; }
.uf { text-transform: uppercase; }

.enderecos { display: flex; flex-direction: column; gap: 1rem; }
.endereco-card {
  border: 1px solid #dbe2ee; border-radius: 12px; padding: 1rem 1.1rem;
  background: #fafcff;
}
.endereco-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.7rem; }
.endereco-head h3 { font-size: 0.98rem; font-weight: 700; color: #1d2a4d; }

.contatos { margin-top: 0.9rem; padding-top: 0.8rem; border-top: 1px dashed #dbe2ee; }
.contatos-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.5rem; flex-wrap: wrap; gap: 0.4rem; }
.contatos-head h4 { font-size: 0.88rem; font-weight: 700; color: #1d2a4d; }
.placeholder-contatos { font-size: 0.8rem; color: #94a3b8; font-style: italic; }
.contato-row { display: flex; gap: 0.5rem; align-items: center; margin-bottom: 0.45rem; }
.contato-nome { flex: 1; }
.contato-tel { width: 190px; }
.contato-row input {
  padding: 0.45rem 0.65rem; border: 1px solid #dbe2ee; border-radius: 8px;
  font-size: 0.88rem; outline: none; background: #fff; box-sizing: border-box;
}
.contato-row input:focus { border-color: #1f5bf0; box-shadow: 0 0 0 3px rgba(31,91,240,0.12); }
@media (max-width: 600px) { .contato-row { flex-wrap: wrap; } .contato-tel { width: 100%; } }

.acoes { display: flex; align-items: center; gap: 0.7rem; margin-top: 1.1rem; flex-wrap: wrap; }
.mt { margin-top: 0.8rem; }
.msg { font-size: 0.85rem; }
.msg.ok { color: #15803d; }
.msg.erro { color: #b91c1c; }
.btn { padding: 0.55rem 1rem; border-radius: 9px; cursor: pointer; font-weight: 600; font-size: 0.88rem; border: none; text-decoration: none; display: inline-block; }
.btn-primary { background: linear-gradient(135deg, #3479fb, #1746dc); color: #fff; box-shadow: 0 8px 18px -8px rgba(23,70,220,0.6); }
.btn-secondary { background: #eef6ff; color: #1746dc; border: 1px solid #bcdcff; }
.btn-danger { background: #fee2e2; color: #b91c1c; border: 1px solid #fecaca; }
.btn-sm { padding: 0.35rem 0.7rem; font-size: 0.78rem; }
.btn:disabled { opacity: 0.6; cursor: not-allowed; }
</style>