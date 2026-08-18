// Notificações em tempo real (WebSocket) + lista persistida no backend.
// Estado é singleton (módulo) para ser compartilhado entre App.vue e outras telas.
import { ref, computed } from 'vue'
import { getLocalToken, api } from '../api'

export const notificacoes = ref([])
const conectado = ref(false)
let socket = null
let desconectar = false
let reconectarTimeout = null
let tentativa = 0

export const naoLidas = computed(() =>
  notificacoes.value.filter(n => !n.lida).length
)

export const conectadoWs = conectado

function urlWs() {
  const base = import.meta.env.VITE_API_URL || 'http://localhost:8000'
  const url = new URL(base)
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  url.pathname = '/ws/notificacoes'
  const token = getLocalToken()
  if (token) url.searchParams.set('token', token)
  return url.toString()
}

// Toque de notificação (Web Audio, sem arquivo). Um contexto único é criado e
// retomado no primeiro gesto do usuário (política de autoplay dos navegadores) —
// depois disso, o som toca normalmente sem o aviso "AudioContext was not allowed
// to start". Dois tons curtos, mais perceptível mas sem incomodar.
let audioCtx = null
let audioDesbloqueado = false

function iniciarAudio() {
  const Ctx = window.AudioContext || window.webkitAudioContext
  if (!Ctx) return
  if (!audioCtx) {
    try { audioCtx = new Ctx() } catch { return }
  }
  if (audioCtx.state === 'suspended') {
    audioCtx.resume().catch(() => {})
  }
  audioDesbloqueado = true
}

// Desbloqueia o áudio no primeiro gesto (clique/toque/tecla) — uma vez só.
if (typeof window !== 'undefined') {
  window.addEventListener('pointerdown', iniciarAudio, { once: true })
  window.addEventListener('keydown', iniciarAudio, { once: true })
}

function tocarSom() {
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext
    if (!Ctx) return
    if (!audioCtx) {
      try { audioCtx = new Ctx() } catch { return }
    }
    if (audioCtx.state === 'suspended') audioCtx.resume().catch(() => {})
    const ctx = audioCtx
    const t0 = ctx.currentTime

    const nota = (freq, start, dur) => {
      const osc = ctx.createOscillator()
      const gain = ctx.createGain()
      osc.connect(gain).connect(ctx.destination)
      osc.type = 'sine'
      osc.frequency.value = freq
      gain.gain.setValueAtTime(0.0001, t0 + start)
      gain.gain.exponentialRampToValueAtTime(0.22, t0 + start + 0.02)
      gain.gain.exponentialRampToValueAtTime(0.0001, t0 + start + dur)
      osc.start(t0 + start)
      osc.stop(t0 + start + dur + 0.05)
    }

    // "Ding-dong" curto e agradável (A5 + E6)
    nota(880, 0, 0.3)
    nota(1318.5, 0.2, 0.45)
  } catch { /* áudio indisponível — ignora */ }
}

async function carregar() {
  try {
    const data = await api.notificacoes.listar()
    notificacoes.value = data.notificacoes || []
  } catch { /* ignora erros de rede — o WS cuida do tempo real */ }
}

function agendarReconexao() {
  if (desconectar) return
  clearTimeout(reconectarTimeout)
  const delay = Math.min(30000, 3000 * Math.pow(1.5, tentativa))
  tentativa += 1
  reconectarTimeout = setTimeout(conectar, delay)
}

function conectar() {
  desconectar = false
  if (socket && socket.readyState < 2) return // já conectando/conectado
  const token = getLocalToken()
  if (!token) return

  try {
    socket = new WebSocket(urlWs())
  } catch {
    agendarReconexao()
    return
  }

  socket.onopen = () => {
    conectado.value = true
    tentativa = 0
  }
  socket.onmessage = (evt) => {
    try {
      const msg = JSON.parse(evt.data)
      if (msg.event === 'init') {
        carregar()
      } else if (msg.event === 'nova_notificacao' && msg.notificacao) {
        if (!notificacoes.value.some(n => n.id === msg.notificacao.id)) {
          notificacoes.value.unshift(msg.notificacao)
        }
        tocarSom()
      }
    } catch { /* ignora payload inválido */ }
  }
  socket.onclose = () => {
    conectado.value = false
    socket = null
    agendarReconexao()
  }
  socket.onerror = () => {
    try { socket && socket.close() } catch {}
  }
}

function parar() {
  desconectar = true
  clearTimeout(reconectarTimeout)
  if (socket) {
    try { socket.close() } catch {}
    socket = null
  }
  conectado.value = false
}

async function marcarLida(n) {
  if (!n || n.lida) return
  n.lida = true
  try { await api.notificacoes.marcarLida(n.id) } catch { n.lida = false }
}

async function marcarTodasLidas() {
  notificacoes.value.forEach(n => { n.lida = true })
  try { await api.notificacoes.marcarTodasLidas() } catch {}
}

// Liga o WS + carrega a lista (chamado após login / refresh autenticado)
export function iniciarNotificacoes() {
  carregar()
  conectar()
}

// Desliga WS e limpa estado (chamado no logout)
export function pararNotificacoes() {
  parar()
  notificacoes.value = []
}

export { carregar, marcarLida, marcarTodasLidas }