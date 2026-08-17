<template>
  <div class="login-page">
    <div class="login-card">
      <div class="logo-badge">AM</div>
      <h1>App Motorista</h1>
      <p class="sub">Acesse o painel de gestão de clientes</p>

      <form @submit.prevent="entrar" class="mt-6 space-y-3">
        <div class="field">
          <label>Usuário (e-mail)</label>
          <input v-model="email" type="email" autocomplete="email" required placeholder="admin@app.com" />
        </div>
        <div class="field">
          <label>Senha</label>
          <input v-model="senha" type="password" autocomplete="current-password" required placeholder="••••••" />
        </div>
        <button class="btn btn-primary w-full" type="submit" :disabled="loading">
          {{ loading ? 'Entrando...' : 'Entrar' }}
        </button>
      </form>

      <p v-if="erro" class="erro" role="alert">{{ erro }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import { loginComToken } from '../composables/useAuth'

const route = useRoute()
const router = useRouter()

const email = ref('')
const senha = ref('')
const loading = ref(false)
const erro = ref('')

async function entrar() {
  loading.value = true
  erro.value = ''
  try {
    const res = await api.auth.login(email.value, senha.value)
    loginComToken(res.access_token)
    const redirect = route.query.redirect || '/clientes/pesquisa'
    router.replace(redirect)
  } catch (e) {
    erro.value = e.message || 'Credenciais inválidas'
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1.25rem;
  background:
    radial-gradient(1200px 600px at 80% -10%, rgba(52,121,251,0.25), transparent 60%),
    radial-gradient(1000px 500px at 10% 110%, rgba(23,70,220,0.25), transparent 60%),
    linear-gradient(180deg, #0b1220, #152454);
}
.login-card {
  width: 100%;
  max-width: 420px;
  background: #fff;
  border-radius: 18px;
  padding: 2.2rem 2rem;
  box-shadow: 0 24px 60px -20px rgba(0, 0, 0, 0.5);
  text-align: center;
}
.logo-badge {
  width: 56px; height: 56px; margin: 0 auto 0.75rem;
  border-radius: 14px;
  background: linear-gradient(135deg, #3479fb, #1746dc);
  color: white; font-weight: 800; font-size: 1.1rem;
  display: inline-flex; align-items: center; justify-content: center;
}
h1 { font-size: 1.6rem; font-weight: 700; color: #0f172a; letter-spacing: -0.02em; }
.sub { color: #64748b; font-size: 0.92rem; margin-top: 0.25rem; }

.field { text-align: left; }
.field label { display: block; font-size: 0.8rem; font-weight: 600; color: #475569; margin-bottom: 0.3rem; }
.field input {
  width: 100%; padding: 0.7rem 0.85rem;
  border: 1px solid #dbe2ee; border-radius: 10px;
  font-size: 0.95rem; outline: none; transition: all 0.15s;
}
.field input:focus { border-color: #1f5bf0; box-shadow: 0 0 0 4px rgba(31,91,240,0.15); }

.btn-primary {
  background: linear-gradient(135deg, #3479fb, #1746dc);
  color: white; font-weight: 600; padding: 0.8rem 1rem;
  border: none; border-radius: 10px; cursor: pointer; font-size: 0.95rem;
  box-shadow: 0 10px 20px -8px rgba(23,70,220,0.7);
  transition: transform 0.1s, opacity 0.15s;
}
.btn-primary:hover { opacity: 0.95; }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.w-full { width: 100%; }

.erro {
  margin-top: 1rem; padding: 0.6rem 0.8rem; border-radius: 8px;
  background: #fef2f2; color: #b91c1c; font-size: 0.85rem; border: 1px solid #fecaca;
}
.dica {
  margin-top: 1.25rem; padding: 0.75rem; border-radius: 10px;
  background: #f1f7ff; color: #1e3a8a; font-size: 0.78rem; text-align: left;
  border: 1px solid #d9eaff;
}
.mt-6 { margin-top: 1.5rem; }
.space-y-3 > * + * { margin-top: 0.75rem; }
</style>