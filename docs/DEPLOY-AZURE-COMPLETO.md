# 🚀 Guia Completo de Deploy no Azure - App Motorista

## 📋 Pré-requisitos

- Conta Azure (pode ser gratuita com US$ 200 de crédito)
- Repositório GitHub com o código
- Git instalado localmente

---

## 🏗️ PARTE 1: Provisionamento da Infraestrutura (Uma única vez)

### 1.1. Abrir o Azure Cloud Shell

1. Acesse: https://portal.azure.com
2. Clique no ícone `>_` (Cloud Shell) no topo da página
3. Selecione **Bash** (não PowerShell)

### 1.2. Clonar o Repositório

```bash
git clone https://github.com/vinidatadev/app-motorista.git
cd app-motorista
```

### 1.3. Editar Variáveis do Script de Setup

```bash
nano scripts/azure-setup.sh
```

**Edite as seguintes variáveis:**
- `POSTGRES_PASSWORD`: Mude para uma senha forte (sem caracteres especiais como `!`)
- `OPENCAGE_KEY`: Cole sua chave OpenCage (opcional)

**Exemplo:**
```bash
POSTGRES_PASSWORD="SenhaForte123ABC"  # ← SEM caracteres especiais!
OPENCAGE_KEY="sua_chave_aqui"
```

Salve: `Ctrl+O` → Enter → `Ctrl+X`

### 1.4. Executar o Script de Setup

```bash
bash scripts/azure-setup.sh
```

⏱️ **Tempo estimado: 5-10 minutos**

O script vai criar:
- ✅ Resource Group (`app-motorista-rg`)
- ✅ Azure Container Registry (ACR)
- ✅ Azure Blob Storage (substitui MinIO)
- ✅ PostgreSQL Flexible Server (FREE por 12 meses)
- ✅ Container Apps Environment
- ✅ Container App (backend)
- ✅ Static Web App (frontend)
- ✅ Service Principal para GitHub Actions

### 1.5. Anotar os Outputs

No final, o script imprime:
- URLs do backend e frontend
- Secrets para o GitHub
- Link para habilitar S3 no Storage

**COPIE TUDO!** Você vai precisar.

---

## 🔐 PARTE 2: Configurar GitHub Secrets

### 2.1. Acessar Configurações do Repositório

Vá em: `https://github.com/SEU-USUARIO/app-motorista/settings/secrets/actions`

### 2.2. Adicionar Variable (aba "Variables")

```
Nome: AZURE_RESOURCE_GROUP
Valor: app-motorista-rg
```

### 2.3. Adicionar Secrets (aba "Secrets")

Clique em **"New repository secret"** para cada um:

```
AZURE_CREDENTIALS
(Cole o JSON completo que o script imprimiu)

ACR_NAME
appmotoristaacr

ACR_USERNAME
appmotoristaacr

ACR_PASSWORD
(Cole a senha que o script imprimiu)

VITE_API_URL
https://app-motorista-backend.XXXXX.centralus.azurecontainerapps.io

CSP_API_URL
(mesmo valor do VITE_API_URL)

CSP_WS_URL
wss://app-motorista-backend.XXXXX.centralus.azurecontainerapps.io

CSP_IMG_SRC
https://appmotoristastg.blob.core.windows.net

AZURE_STATIC_WEB_APPS_API_TOKEN
(Token obtido do comando abaixo no Cloud Shell)
```

**Para obter o token do Static Web Apps:**

No Azure Cloud Shell:
```bash
az staticwebapp secrets list --name app-motorista-swa --resource-group app-motorista-rg --query "properties.apiKey" -o tsv
```

**Secrets opcionais (se tiver chaves):**
```
VITE_MAPBOX_TOKEN
(sua chave Mapbox)

VITE_OPENCAGE_KEY
(sua chave OpenCage)
```

---

## 🔧 PARTE 3: Habilitar Protocolo S3 no Storage (Manual)

1. Acesse o link que o script imprimiu (ou busque `appmotoristastg` no portal)
2. No menu lateral → **Configuration** (em Settings)
3. Procure por **"Allow cross-origin requests (CORS)"** ou configurações de protocolo
4. Habilite o suporte S3 (pode não estar disponível em todas as regiões)
5. Salve

> **Nota:** Se não encontrar a opção, o Storage funcionará apenas via Blob API (que já está funcionando).

---

## 🚢 PARTE 4: Deploy do Backend

### 4.1. Fazer o Primeiro Deploy

No seu **computador local** (não no Cloud Shell):

```bash
git pull origin main
git tag v1.0.0
git push origin v1.0.0
```

Isso dispara o workflow: `Deploy Azure Container Apps`

### 4.2. Acompanhar o Deploy

Vá em: `https://github.com/SEU-USUARIO/app-motorista/actions`

⏱️ **Tempo estimado: 3-5 minutos**

Aguarde ficar **verde ✅**

### 4.3. Verificar se o Backend Subiu

Acesse no navegador:
```
https://app-motorista-backend.XXXXX.centralus.azurecontainerapps.io/health
```

Deve retornar:
```json
{
  "status": "healthy"
}
```

---

## 🌐 PARTE 5: Deploy do Frontend

O frontend já foi deployado automaticamente pelo Azure quando você conectou o repositório!

### 5.1. Verificar a URL do Frontend

No portal Azure:
1. Busque por `app-motorista-swa`
2. Na página Overview, copie a **URL** (algo como `https://gentle-plant-XXXXX.azurestaticapps.net`)

### 5.2. Testar o Frontend

Abra a URL no navegador. Deve aparecer a tela de login! 🎉

---

## 👤 PARTE 6: Criar o Primeiro Usuário Admin

### 6.1. Usar o Postman/Insomnia

**Requisição:**
```
POST https://app-motorista-backend.XXXXX.centralus.azurecontainerapps.io/api/auth/setup

Headers:
Content-Type: application/json

Body (JSON):
{
  "email": "admin@empresa.com",
  "password": "SenhaForte123!",
  "name": "Administrador",
  "empresa": "AC"
}
```

**Resposta esperada:**
```json
{
  "user": {
    "id": "...",
    "email": "admin@empresa.com",
    "name": "Administrador",
    "role": "admin",
    "empresa": "AC"
  },
  "token": "eyJ..."
}
```

### 6.2. Ou via curl (Azure Cloud Shell)

```bash
curl -X POST https://app-motorista-backend.XXXXX.centralus.azurecontainerapps.io/api/auth/setup \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@empresa.com",
    "password": "SenhaForte123!",
    "name": "Administrador",
    "empresa": "AC"
  }'
```

### 6.3. Fazer Login no Frontend

1. Acesse a URL do frontend
2. Use o email e senha que criou
3. Pronto! Você está dentro! 🎉

---

## 🔒 PARTE 7: Desativar o Endpoint de Setup (IMPORTANTE!)

Depois de criar o admin, **desative** o endpoint para ninguém mais poder criar admins:

No **Azure Cloud Shell**:

```bash
az containerapp update --name app-motorista-backend --resource-group app-motorista-rg \
  --set-env-vars "ALLOW_SETUP="
```

---

## 📊 PARTE 8: Ajustes de Performance (Opcional)

### 8.1. Expandir para 200 Usuários Simultâneos

Quando o uso crescer, aumente os recursos:

```bash
az containerapp update --name app-motorista-backend --resource-group app-motorista-rg \
  --cpu 1 --memory 2Gi --min-replicas 2 --max-replicas 5
```

**Custo:** ~US$ 60-90/mês

### 8.2. Habilitar Scale Agendado (Economiza fora do expediente)

No portal Azure:
1. Vá em `app-motorista-backend`
2. Menu lateral → **Scale**
3. Configure regras por horário (ex: 2 réplicas durante o dia, 0 à noite)

---

## 🔄 PARTE 9: Atualizações Futuras

### 9.1. Atualizar o Backend

```bash
git add .
git commit -m "feat: nova funcionalidade"
git push origin main
git tag v1.1.0
git push origin v1.1.0
```

O workflow roda automaticamente!

### 9.2. Atualizar o Frontend

```bash
git add .
git commit -m "feat: nova tela"
git push origin main
```

O Static Web Apps deploya automaticamente!

---

## 💰 CUSTOS ESTIMADOS

### Fase 1: Modo Gratuito (12 meses)
- PostgreSQL: **US$ 0** (free tier)
- Static Web Apps: **US$ 0** (free tier)
- Container Apps (scale-to-zero): **~US$ 5/mês** (só quando usado)
- Blob Storage: **~US$ 1/mês**
- ACR: **~US$ 5/mês**

**Total:** ~US$ 10-15/mês

### Fase 2: 200 Usuários Simultâneos
- Container Apps (2 réplicas): **~US$ 60-80/mês**
- Resto igual

**Total:** ~US$ 70-90/mês

### Fase 3: Após 12 Meses (banco pago)
- PostgreSQL B2s: **+US$ 45-60/mês**

**Total:** ~US$ 115-150/mês

---

## 🐛 TROUBLESHOOTING

### Problema: Backend não responde

```bash
# Ver logs
az containerapp logs show --name app-motorista-backend --resource-group app-motorista-rg --tail 50

# Ver status das revisões
az containerapp revision list --name app-motorista-backend --resource-group app-motorista-rg -o table
```

### Problema: Erro de autenticação no ACR

```bash
# Atualizar credenciais
ACR_PASSWORD=$(az acr credential show --name appmotoristaacr --resource-group app-motorista-rg --query "passwords[0].value" -o tsv)

az containerapp registry set --name app-motorista-backend --resource-group app-motorista-rg \
  --server appmotoristaacr.azurecr.io \
  --username appmotoristaacr \
  --password "$ACR_PASSWORD"
```

### Problema: Erro de senha do banco

```bash
# Mudar senha do PostgreSQL
az postgres flexible-server update --resource-group app-motorista-rg --name app-motorista-pg \
  --admin-password "NovaSenhaForte123"

# Atualizar no Container App
az containerapp update --name app-motorista-backend --resource-group app-motorista-rg \
  --set-env-vars "DATABASE_URL=postgresql+asyncpg://motorista:NovaSenhaForte123@app-motorista-pg.postgres.database.azure.com:5432/appdb?sslmode=require"
```

### Problema: Frontend dá 404 ao dar F5

Já foi corrigido com o arquivo `staticwebapp.config.json`! Se ainda acontecer, verifique se o arquivo está no repositório.

---

## 📝 CHECKLIST DE DEPLOY

- [ ] Clonou o repositório no Cloud Shell
- [ ] Editou a senha no `azure-setup.sh`
- [ ] Rodou o script `bash scripts/azure-setup.sh`
- [ ] Copiou todos os outputs (URLs e secrets)
- [ ] Configurou a variable `AZURE_RESOURCE_GROUP` no GitHub
- [ ] Configurou todos os secrets no GitHub
- [ ] Habilitou protocolo S3 no Storage (opcional)
- [ ] Fez o primeiro deploy com `git tag v1.0.0`
- [ ] Verificou que o backend está rodando (`/health`)
- [ ] Verificou que o frontend está acessível
- [ ] Criou o primeiro usuário admin
- [ ] Desativou o endpoint `/api/auth/setup`
- [ ] Testou fazer login no frontend

---

## 🎉 PARABÉNS!

Seu app está 100% funcionando no Azure! 

- **Frontend:** https://gentle-plant-XXXXX.azurestaticapps.net
- **Backend:** https://app-motorista-backend.XXXXX.centralus.azurecontainerapps.io
- **Custo inicial:** ~US$ 10-15/mês

---

## 📞 RECURSOS ÚTEIS

- [Documentação Azure Container Apps](https://learn.microsoft.com/azure/container-apps/)
- [Documentação Azure Static Web Apps](https://learn.microsoft.com/azure/static-web-apps/)
- [Documentação PostgreSQL Flexible Server](https://learn.microsoft.com/azure/postgresql/flexible-server/)
- [Portal Azure](https://portal.azure.com)
- [Azure Cloud Shell](https://shell.azure.com)

---

**Criado em:** 20/08/2026  
**Versão:** 1.0.0  
**Última atualização:** Deploy bem-sucedido com todos os componentes funcionando
