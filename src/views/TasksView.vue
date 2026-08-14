<template>
  <div class="tasks-page">
      <div class="page-header">
        <h2>Minhas Tarefas</h2>
        <button class="btn btn-primary" @click="showForm = true">+ Nova Tarefa</button>
      </div>

      <div v-if="showForm" class="task-form">
        <input
          v-model="newTitle"
          placeholder="Título da tarefa..."
          maxlength="200"
          @keyup.enter="addTask"
          autofocus
        />
        <div class="form-actions">
          <button class="btn btn-primary" @click="addTask" :disabled="saving">
            {{ saving ? 'Salvando...' : 'Salvar' }}
          </button>
          <button class="btn btn-ghost" @click="showForm = false; newTitle = ''">Cancelar</button>
        </div>
      </div>

      <div v-if="errorMsg" class="alert-error">{{ errorMsg }}</div>

      <div v-if="loading" class="state-msg">Carregando tarefas...</div>

      <div v-else-if="tasks.length === 0" class="state-msg muted">
        Nenhuma tarefa ainda. Crie uma acima.
      </div>

      <div v-else class="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>Status</th>
              <th>Título</th>
              <th>Imagem</th>
              <th>Criado em</th>
              <th>Ações</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="task in tasks" :key="task.id" :class="{ done: task.is_completed }">
              <td>
                <span class="badge" :class="task.is_completed ? 'badge-done' : 'badge-pending'">
                  {{ task.is_completed ? 'Concluída' : 'Pendente' }}
                </span>
              </td>
              <td class="task-title">{{ task.title }}</td>
              <td>
                <div class="img-cell">
                  <img v-if="task.image_url" :src="task.image_url" class="task-thumb" @click="openImage(task.image_url)" />
                  <label v-else class="btn-icon upload-label" title="Anexar imagem">
                    📎
                    <input type="file" accept="image/*" hidden @change="e => uploadImage(task, e)" />
                  </label>
                  <button v-if="task.image_url" class="btn-icon danger" title="Remover imagem" @click="removeImage(task)">✕</button>
                </div>
              </td>
              <td class="date">{{ formatDate(task.created_at) }}</td>
              <td class="actions">
                <button class="btn-icon" :title="task.is_completed ? 'Reabrir' : 'Concluir'" @click="toggleTask(task)">
                  {{ task.is_completed ? '↩' : '✓' }}
                </button>
                <button class="btn-icon danger" title="Excluir" @click="deleteTask(task.id)">✕</button>
              </td>
            </tr>
          </tbody>
        </table>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'

const tasks    = ref([])
const loading  = ref(true)
const saving   = ref(false)
const errorMsg = ref('')
const showForm = ref(false)
const newTitle = ref('')

onMounted(fetchTasks)

async function fetchTasks() {
  loading.value = true
  errorMsg.value = ''
  try {
    tasks.value = await api.tasks.list()
  } catch (e) {
    errorMsg.value = 'Erro ao carregar tarefas: ' + e.message
  } finally {
    loading.value = false
  }
}

async function addTask() {
  const title = newTitle.value.trim()
  if (!title) return
  saving.value = true
  errorMsg.value = ''
  try {
    const task = await api.tasks.create(title)
    tasks.value.unshift(task)
    newTitle.value = ''
    showForm.value = false
  } catch (e) {
    errorMsg.value = 'Erro ao criar tarefa: ' + e.message
  } finally {
    saving.value = false
  }
}

async function toggleTask(task) {
  try {
    const updated = await api.tasks.update(task.id, { is_completed: !task.is_completed })
    task.is_completed = updated.is_completed
  } catch (e) {
    errorMsg.value = 'Erro ao atualizar tarefa: ' + e.message
  }
}

async function deleteTask(id) {
  try {
    await api.tasks.remove(id)
    tasks.value = tasks.value.filter(t => t.id !== id)
  } catch (e) {
    errorMsg.value = 'Erro ao excluir tarefa: ' + e.message
  }
}

async function uploadImage(task, event) {
  const file = event.target.files[0]
  if (!file) return
  try {
    const updated = await api.tasks.uploadImage(task.id, file)
    task.image_url = updated.image_url
  } catch (e) {
    errorMsg.value = 'Erro ao enviar imagem: ' + e.message
  }
}

async function removeImage(task) {
  try {
    const updated = await api.tasks.removeImage(task.id)
    task.image_url = updated.image_url
  } catch (e) {
    errorMsg.value = 'Erro ao remover imagem: ' + e.message
  }
}

function openImage(url) {
  window.open(url, '_blank')
}

function formatDate(iso) {
  return new Date(iso).toLocaleDateString('pt-BR', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit'
  })
}
</script>

<style scoped>
.tasks-page { display: flex; flex-direction: column; }

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}
.page-header h2 { font-size: 1.4rem; color: #1a1a2e; }

.task-form {
  background: #fff;
  border-radius: 10px;
  padding: 1.2rem;
  margin-bottom: 1.5rem;
  box-shadow: 0 2px 8px rgba(0,0,0,.06);
}
.task-form input {
  width: 100%;
  padding: .65rem 1rem;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: .95rem;
  outline: none;
  margin-bottom: .75rem;
}
.task-form input:focus { border-color: #0078d4; }
.form-actions { display: flex; gap: .5rem; }

.alert-error {
  background: #fff0f0;
  border: 1px solid #fcc;
  color: #c0392b;
  border-radius: 8px;
  padding: .75rem 1rem;
  margin-bottom: 1rem;
  font-size: .9rem;
}

.btn {
  padding: .5rem 1.2rem;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: .9rem;
  font-weight: 500;
  transition: opacity .2s;
}
.btn:hover:not(:disabled) { opacity: .85; }
.btn:disabled { opacity: .5; cursor: not-allowed; }
.btn-primary { background: #0078d4; color: #fff; }
.btn-ghost { background: transparent; color: #666; }

.table-wrapper {
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 2px 8px rgba(0,0,0,.06);
  overflow: hidden;
}
table { width: 100%; border-collapse: collapse; }
thead { background: #f8f9fb; }
th {
  text-align: left;
  padding: .9rem 1.2rem;
  font-size: .8rem;
  text-transform: uppercase;
  color: #888;
  letter-spacing: .5px;
  border-bottom: 1px solid #eee;
}
td {
  padding: .9rem 1.2rem;
  border-bottom: 1px solid #f0f0f0;
  font-size: .9rem;
  color: #333;
}
tr:last-child td { border-bottom: none; }
tr.done .task-title { text-decoration: line-through; color: #aaa; }

.badge {
  display: inline-block;
  padding: .25rem .7rem;
  border-radius: 20px;
  font-size: .75rem;
  font-weight: 600;
}
.badge-pending { background: #fff3cd; color: #856404; }
.badge-done { background: #d1e7dd; color: #0a5c36; }

.date { font-size: .8rem; color: #999; }
.actions { display: flex; gap: .4rem; }

.btn-icon {
  background: none;
  border: 1px solid #ddd;
  border-radius: 6px;
  width: 32px;
  height: 32px;
  cursor: pointer;
  font-size: .9rem;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all .2s;
}
.btn-icon:hover { background: #f0f7ff; border-color: #0078d4; color: #0078d4; }
.btn-icon.danger:hover { background: #fff0f0; border-color: #e74c3c; color: #e74c3c; }

.state-msg {
  text-align: center;
  padding: 3rem;
  color: #666;
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 2px 8px rgba(0,0,0,.06);
}
.state-msg.muted { color: #aaa; }

.img-cell { display: flex; align-items: center; gap: .4rem; }
.task-thumb {
  width: 40px;
  height: 40px;
  object-fit: cover;
  border-radius: 6px;
  cursor: pointer;
  border: 1px solid #eee;
}
.upload-label { cursor: pointer; }
</style>
