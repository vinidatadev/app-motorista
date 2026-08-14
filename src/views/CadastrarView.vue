<template>
  <div class="page">
    <div class="container">
      <div class="page-head">
        <h1>Cadastrar Novo Cliente</h1>
        <p>Preencha os dados do novo cliente. Os campos marcados com * são obrigatórios.</p>
      </div>

      <section v-if="form" class="card form-card">
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
          <div class="field">
            <label>Latitude</label>
            <input v-model.number="form.latitude" type="number" step="0.00000001" />
          </div>
          <div class="field">
            <label>Longitude</label>
            <input v-model.number="form.longitude" type="number" step="0.00000001" />
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
import { useRouter } from 'vue-router'
import { api } from '../api'

const router = useRouter()
const salvando = ref(false)
const msg = ref('')
const msgTipo = ref('ok')

const formInit = () => ({
  codigo: '', nome_razao_social: '', telefone: '', pessoa_contato: '',
  cep: '', rua: '', numero: '', bairro: '', cidade: '', estado: '',
  latitude: null, longitude: null,
  ponto_referencia: '', observacao: ''
})
const form = ref(formInit())

function onTelefoneInput(evt) {
  const digitos = (evt.target.value || '').replace(/\D/g, '').slice(0, 11)
  let out = ''
  if (digitos.length > 0) out = '(' + digitos.slice(0, 2)
  if (digitos.length >= 2) out += ') '
  if (digitos.length > 2) {
    const rest = digitos.slice(2)
    if (rest.length > 4) out += rest.slice(0, rest.length - 4) + '-' + rest.slice(rest.length - 4)
    else out += rest
  }
  form.value.telefone = out
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
      latitude: form.value.latitude === '' ? null : form.value.latitude,
      longitude: form.value.longitude === '' ? null : form.value.longitude
    }
    // Remove codigo vazio (deixa o backend nao gravar)
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
.form-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 0.4rem 0.9rem; }
.col2 { grid-column: span 2; }
@media (max-width: 720px) { .form-grid { grid-template-columns: 1fr; } .col2 { grid-column: auto; } }
.field { margin-bottom: 0.8rem; }
.field label { display: block; font-size: 0.78rem; font-weight: 600; color: #475569; margin-bottom: 0.3rem; }
.field input { width: 100%; padding: 0.5rem 0.7rem; border: 1px solid #dbe2ee; border-radius: 8px; font-size: 0.9rem; outline: none; background: #fff; transition: all 0.15s; }
.field input:focus { border-color: #1f5bf0; box-shadow: 0 0 0 4px rgba(31,91,240,0.12); }
textarea {
  width: 100%; padding: 0.55rem 0.7rem;
  border: 1px solid #dbe2ee; border-radius: 8px;
  font-size: 0.9rem; outline: none; background: #fff;
  resize: vertical; min-height: 60px; font-family: inherit;
  transition: all 0.15s; box-sizing: border-box;
}
textarea:focus { border-color: #1f5bf0; box-shadow: 0 0 0 4px rgba(31,91,240,0.12); }
.uf { text-transform: uppercase; }
.acoes { display: flex; align-items: center; gap: 0.7rem; margin-top: 1.1rem; flex-wrap: wrap; }
.msg { font-size: 0.85rem; }
.msg.ok { color: #15803d; }
.msg.erro { color: #b91c1c; }
.btn { padding: 0.55rem 1rem; border-radius: 9px; cursor: pointer; font-weight: 600; font-size: 0.88rem; border: none; text-decoration: none; display: inline-block; }
.btn-primary { background: linear-gradient(135deg, #3479fb, #1746dc); color: #fff; box-shadow: 0 8px 18px -8px rgba(23,70,220,0.6); }
.btn-secondary { background: #eef6ff; color: #1746dc; border: 1px solid #bcdcff; }
.btn:disabled { opacity: 0.6; cursor: not-allowed; }
</style>