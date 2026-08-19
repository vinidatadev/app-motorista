#!/usr/bin/env bash
# ============================================================================
# App Motorista — Provisionamento no Azure (conta Free / US$ 200)
# Estrategia: COMECE NO GRATIS e EXPANDA depois.
# ============================================================================
#
# COMO USAR (Azure Cloud Shell: https://shell.azure.com, bash):
#   1. Abra o Cloud Shell e rode:  bash scripts/azure-setup.sh
#   2. Ao final o script imprime URLs, o backend/.env e os secrets do GitHub.
#
# AVISO: o script cria recursos pagos. Com a conta Free (US$ 200) o consumo
# cabe no credito, mas MONITORE o custo no portal (Custos > Analise de custo).
#
# ----------------------------------------------------------------------------
# ESTRATEGIA DE CUSTO (tudo começa no minimo e sobe quando precisar):
#
#   FRONTEND  -> Azure Static Web Apps (TIER GRATUITO, US$ 0) + CDN.
#                O frontend e 100% estatico (Vue + nginx), nao precisa de
#                Container App. Aguenta picos grandes de graca via CDN.
#
#   BACKEND   -> Container App com SCALE-TO-ZERO (min-replicas: 0).
#                Paga SOMENTE enquanto estiver sendo acessado. Esporadico =
#                quase US$ 0. Quando crescer, suba min-replicas (veja "EXPANDIR").
#
#   BANCO     -> PostgreSQL Flexible Server no TIER GRATUITO (12 meses, US$ 0).
#                Apos 12 meses, migre para B2s ou pague o B1ms.
#
#   FOTOS     -> Azure Blob Storage (custa centavos por GB).
#   REGISTRY  -> ACR SKU Basic (~US$ 5/mes fixo).
#
#   CUSTO INICIAL APROX.: ~US$ 5-15/mes (ACR + Blob + uso esporadico do back).
#   Quando expandir para 200 usuarios simultaneos: ~US$ 50-80/mes.
#
# ----------------------------------------------------------------------------
# EXPANDIR DEPOIS (sem mudar a aplicacao — so infra):
#   a) Backend com mais capacidade (pico de 200 simultaneos):
#        az containerapp update --name $BACKEND_APP --resource-group $RESOURCE_GROUP \
#          --cpu 1 --memory 2Gi --min-replicas 2 --max-replicas 5
#      (ou programe scale por horario comercial para economizar: scale rules)
#   b) Banco pago (apos os 12 meses gratuitos):
#        az postgres flexible-server update --resource-group $RESOURCE_GROUP \
#          --name $POSTGRES_SERVER --tier Burstable --sku-name Standard_B2s
#   c) Precisa de mais? Container Apps sobe replicas sozinho (HPA) ate --max-replicas.
# ============================================================================

# ----------------------------------------------------------------------------
# VARIAVEIS — edite ANTES de rodar (valores entre aspas):
# ----------------------------------------------------------------------------
RESOURCE_GROUP="app-motorista-rg"
# Regiao. Se o PostgreSQL der "location restricted", troque para outra com
# mais disponibilidade. Opcoes com tier gratuito do Flexible Server:
#   eastus2 | centralus | westus2 | eastus | southcentralus | canadacentral
# (Nao use brasilsouth: tem menos recursos no tier gratuito.)
LOCATION="eastus"
ACR_NAME="appmotoristaacr"             # globalmente unico: minusculas, sem hifen
STORAGE_ACCOUNT="appmotoristastg"      # globalmente unico: minusculas
POSTGRES_SERVER="app-motorista-pg"     # globalmente unico
POSTGRES_DB="appdb"
POSTGRES_USER="motorista"              # sem "@" nem espacos
POSTGRES_PASSWORD="TroqueEstaSenha123!" # 8+ chars: maiuscula, minuscula, numero, simbolo
BACKEND_APP="app-motorista-backend"    # nome do container app do backend
FRONTEND_SWA_NAME="app-motorista-swa"  # nome do Static Web Apps (so letras/numeros/hifen)
# URL publica onde o Static Web Apps vai morar (opcional). Vazio = usa <hash>.azurestaticapps.net
# Se tiver dominio proprio, preencha ex.: "app.motoristas.empresa.com.br"
FRONTEND_CUSTOM_DOMAIN=""
OPENCAGE_KEY=""                        # sua chave OpenCage (opcional; vazio = fallback Nominatim)
GH_SP_NAME="app-motorista-ghactions"   # service principal do GitHub Actions

set -euo pipefail

# ---------- 1. Login e assinatura ----------
echo "==> Verificando login..."
az account show >/dev/null 2>&1 || az login
SUB_ID=$(az account show --query id -o tsv)
SUB_NAME=$(az account show --query name -o tsv)
echo "    Subscription: $SUB_NAME ($SUB_ID)"

# ---------- 2. Resource Group ----------
echo "==> Criando Resource Group..."
az group create --name "$RESOURCE_GROUP" --location "$LOCATION" -o none

# ---------- 3. Azure Container Registry (ACR) ----------
echo "==> Criando Azure Container Registry (SKU Basic)..."
az acr create --resource-group "$RESOURCE_GROUP" --name "$ACR_NAME" \
    --sku Basic --admin-enabled -o none
ACR_PASSWORD=$(az acr credential show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" \
    --query passwords[0].value -o tsv)

# ---------- 4. Storage Account + S3-compatible API (substitui o MinIO) ----------
echo "==> Criando Storage Account e habilitando S3-compatible API..."
az storage account create --resource-group "$RESOURCE_GROUP" --name "$STORAGE_ACCOUNT" \
    --location "$LOCATION" --sku Standard_LRS --kind StorageV2 \
    --min-tls-version TLS1_2 -o none
az storage account update --resource-group "$RESOURCE_GROUP" --name "$STORAGE_ACCOUNT" \
    --enable-hierarchical-namespace false -o none 2>/dev/null || true
# Protocolo S3: tenta habilitar por CLI; se a versao nao suportar a flag, orienta no portal.
if ! az storage account show --resource-group "$RESOURCE_GROUP" --name "$STORAGE_ACCOUNT" \
        --query "properties.isSkuConversionBlocked" -o tsv >/dev/null 2>&1; then :; fi
if az storage account update --resource-group "$RESOURCE_GROUP" --name "$STORAGE_ACCOUNT" \
        --enable-s3-protocol true -o none 2>/dev/null; then
    echo "    S3 protocol habilitado por CLI."
else
    echo "    ATENCAO: nao consegui habilitar o protocolo S3 por CLI."
    echo "    Faca manualmente no portal:"
    echo "      Storage account '$STORAGE_ACCOUNT' > Settings > Properties >"
    echo "      'Allow S3 protocol' = Enabled > Save"
fi
STORAGE_KEY=$(az storage account keys list --account-name "$STORAGE_ACCOUNT" \
    --resource-group "$RESOURCE_GROUP" --query "[0].value" -o tsv)
az storage container create --account-name "$STORAGE_ACCOUNT" \
    --account-key "$STORAGE_KEY" --name clientes -o none
echo "    Storage OK. Endpoint S3: https://$STORAGE_ACCOUNT.blob.core.windows.net"

# ---------- 5. PostgreSQL Flexible Server (TIER GRATUITO 12 meses) ----------
echo "==> Criando PostgreSQL Flexible Server (TIER GRATUITO, 12 meses)..."
# O tier gratuito so existe em determinadas regioes. Tenta criar; se a regiao
# estiver restrita, tenta automaticamente outras regioes da lista.
POSTGRES_CREATED=""
for try_loc in "$LOCATION" westus2 centralus eastus2 southcentralus canadacentral; do
    echo "    Tentando criar PostgreSQL em $try_loc ..."
    if az postgres flexible-server create \
        --resource-group "$RESOURCE_GROUP" \
        --name "$POSTGRES_SERVER" \
        --location "$try_loc" \
        --admin-user "$POSTGRES_USER" \
        --admin-password "$POSTGRES_PASSWORD" \
        --tier Burstable --sku-name Standard_B1ms --storage-size 32 --storage-auto-grow enabled \
        --version 16 --public-access All --yes -o none 2>/dev/null; then
        POSTGRES_CREATED="yes"
        echo "    PostgreSQL criado em $try_loc."
        break
    else
        echo "    Falhou em $try_loc (restrito ou indisponivel). Tentando proxima..."
    fi
done

if [ -z "$POSTGRES_CREATED" ]; then
    echo ""
    echo "ERRO: nao consegui criar o PostgreSQL em nenhuma regiao testada."
    echo "Isso pode ser limite de cota da sua conta Free. Opcoes:"
    echo "  1. Crie o PostgreSQL manualmente no portal (qualquer regiao que aceite) e reexecute"
    echo "     o script com a variavel POSTGRES_SERVER apontando para o servidor existente."
    echo "  2. Aumente a cota em: https://portal.azure.com -> Ajuda e suporte -> Nova solicitação de suporte."
    echo ""
    echo "Os recursos criados ate aqui (ACR, Storage) permanecem. Para remover tudo:"
    echo "  az group delete --name $RESOURCE_GROUP --yes --no-wait"
    exit 1
fi

# Tenta aplicar o tier gratuito (ignora erro se a regiao nao suportar)
az postgres flexible-server update --resource-group "$RESOURCE_GROUP" \
    --name "$POSTGRES_SERVER" --tier Burstable --sku-name Standard_B1ms \
    --high-availability Disabled -o none 2>/dev/null || true
echo "    DICA: no portal (Overview do servidor) voce pode aplicar o TIER GRATUITO (12 meses)."

echo "==> Criando database $POSTGRES_DB no PostgreSQL..."
az postgres flexible-server db create \
    --resource-group "$RESOURCE_GROUP" --server-name "$POSTGRES_SERVER" \
    --database-name "$POSTGRES_DB" -o none

# ---------- 6. Container Apps Environment + BACKEND (scale-to-zero) ----------
echo "==> Criando Container Apps Environment + BACKEND (scale-to-zero)..."
LA_WORKSPACE="$RESOURCE_GROUP-logs"
LA_ID=$(az monitor log-analytics workspace create --resource-group "$RESOURCE_GROUP" \
    --workspace-name "$LA_WORKSPACE" --location "$LOCATION" --query id -o tsv)
LA_KEY=$(az monitor log-analytics workspace get-shared-keys \
    --resource-group "$RESOURCE_GROUP" --workspace-name "$LA_WORKSPACE" --query primarySharedKey -o tsv)
az containerapp env create --resource-group "$RESOURCE_GROUP" --name app-motorista-env \
    --location "$LOCATION" \
    --logs-workspace-id "$LA_ID" --logs-workspace-key "$LA_KEY" -o none

JWT_SECRET=$(openssl rand -hex 32)
DATABASE_URL="postgresql+asyncpg://$POSTGRES_USER:$POSTGRES_PASSWORD@$POSTGRES_SERVER.postgres.database.azure.com:5432/$POSTGRES_DB?sslmode=require"
MINIO_ENDPOINT="$STORAGE_ACCOUNT.blob.core.windows.net"        # sem https (o backend completa)
MINIO_PUBLIC_URL="https://$STORAGE_ACCOUNT.blob.core.windows.net"

# Backend criado com placeholder; o GitHub Actions substitui pela imagem real.
# min-replicas 0 = SCALE-TO-ZERO: paga so enquanto e acessado. Expandir depois:
#   az containerapp update --name $BACKEND_APP --resource-group $RESOURCE_GROUP \
#     --cpu 1 --memory 2Gi --min-replicas 2 --max-replicas 5
az containerapp create \
    --name "$BACKEND_APP" --resource-group "$RESOURCE_GROUP" --environment app-motorista-env \
    --image mcr.microsoft.com/azuredocs/aks-helloworld:latest \
    --target-port 8000 --ingress external --transport auto \
    --cpu 0.5 --memory 1.0Gi --min-replicas 0 --max-replicas 4 \
    --registry-server "$ACR_NAME.azurecr.io" \
    --registry-username "$ACR_NAME" --registry-password "$ACR_PASSWORD" \
    --env-vars \
        "DATABASE_URL=$DATABASE_URL" \
        "JWT_SECRET=$JWT_SECRET" \
        "JWT_EXPIRE_H=8" \
        "ALLOWED_ORIGINS=http://localhost:5173" \
        "MINIO_ENDPOINT=$MINIO_ENDPOINT" \
        "MINIO_ACCESS_KEY=$STORAGE_ACCOUNT" \
        "MINIO_SECRET_KEY=$STORAGE_KEY" \
        "MINIO_PUBLIC_URL=$MINIO_PUBLIC_URL" \
        "MINIO_CLIENTES_BUCKET=clientes" \
        "OPENCAGE_KEY=$OPENCAGE_KEY" \
        "ALLOW_SETUP=1" \
    -o none
BACKEND_FQDN=$(az containerapp show --name "$BACKEND_APP" --resource-group "$RESOURCE_GROUP" \
    --query properties.configuration.ingress.fqdn -o tsv)

# Depois do primeiro deploy, desative o setup (ALLOW_SETUP -> vazio):
#   az containerapp update --name $BACKEND_APP --resource-group $RESOURCE_GROUP \
#     --set properties.template.containers[0].env[10].value=

# ---------- 7. FRONTEND como Static Web Apps (TIER GRATUITO) ----------
echo "==> Criando FRONTEND como Azure Static Web Apps (TIER GRATUITO)..."
echo "    NOTA: o Static Web Apps precisa de um repositorio GitHub. Este script cria o recurso;"
echo "    voce conecta o repositorio e o deploy do frontend passa a ser automatico no push."
# Cria o Static Web Apps (a conexao com o GitHub e feita pelo portal/CLI apos isso)
az staticwebapp create \
    --name "$FRONTEND_SWA_NAME" --resource-group "$RESOURCE_GROUP" \
    --location "$LOCATION" --sku Free \
    --login-with-aad 2>/dev/null \
    || az staticwebapp create --name "$FRONTEND_SWA_NAME" --resource-group "$RESOURCE_GROUP" \
        --location "$LOCATION" --sku Free -o none
echo "    Static Web Apps OK (criado, aguardando conexao do repositorio)."

# ---------- 8. Service Principal para o GitHub Actions ----------
echo "==> Criando Service Principal para o GitHub Actions..."
SP_JSON=$(az ad sp create-for-rbac --name "$GH_SP_NAME" \
    --role Contributor \
    --scopes "/subscriptions/$SUB_ID/resourceGroups/$RESOURCE_GROUP" \
    --sdk-auth 2>/dev/null || az ad sp create-for-rbac --name "$GH_SP_NAME" \
    --role Contributor --scopes "/subscriptions/$SUB_ID/resourceGroups/$RESOURCE_GROUP")

# ---------- 9. Resumo e proximos passos ----------
echo ""
echo "============================================================"
echo "  SETUP CONCLUIDO — App Motorista no Azure (modo gratuito)"
echo "============================================================"
echo ""
echo "URLs:"
echo "  Backend  (API/Swagger):   https://$BACKEND_FQDN"
echo "  Backend  (WebSocket):     wss://$BACKEND_FQDN"
echo "  Frontend:                 (Static Web Apps — aparecera apos conectar o repo no portal)"
echo ""
echo "SECRETS para o GitHub Actions (Settings > Secrets and variables > Actions):"
echo "  VAR  AZURE_RESOURCE_GROUP = $RESOURCE_GROUP"
echo "  secret AZURE_CREDENTIALS  = $(echo "$SP_JSON" | tr -d '\n')"
echo "  secret ACR_NAME           = $ACR_NAME"
echo "  secret ACR_USERNAME       = $ACR_NAME"
echo "  secret ACR_PASSWORD       = $ACR_PASSWORD"
echo "  secret VITE_API_URL       = https://$BACKEND_FQDN"
echo "  secret CSP_API_URL        = https://$BACKEND_FQDN"
echo "  secret CSP_WS_URL         = wss://$BACKEND_FQDN"
echo "  secret CSP_IMG_SRC        = $MINIO_PUBLIC_URL"
echo "  secret VITE_MAPBOX_TOKEN  = (sua chave Mapbox)"
echo "  secret VITE_OPENCAGE_KEY  = (sua chave OpenCage)"
echo ""
echo "backend/.env (exemplo completo em backend/.env.azure.example):"
echo "  DATABASE_URL=$DATABASE_URL"
echo "  MINIO_ENDPOINT=$MINIO_ENDPOINT"
echo "  MINIO_ACCESS_KEY=$STORAGE_ACCOUNT"
echo "  MINIO_SECRET_KEY=$STORAGE_KEY"
echo "  MINIO_PUBLIC_URL=$MINIO_PUBLIC_URL"
echo ""
echo "PROXIMOS PASSOS:"
echo "  1. No portal do Azure, abra o recurso '$FRONTEND_SWA_NAME' (Static Web Apps)"
echo "     e conecte o repositorio GitHub -> branch main -> pasta / (build: npm run build)."
echo "     O frontend passa a deployar automaticamente a cada push (US$ 0)."
echo "  2. Configure os secrets acima no GitHub e rode o workflow 'Deploy Azure Container Apps'"
echo "     (ou crie tag: git tag v0.1.0 && git push --tags) para subir o BACKEND."
echo "  3. Acesse o backend e crie o admin: POST https://$BACKEND_FQDN/api/auth/setup"
echo "     (ALLOW_SETUP=1 ja esta habilitado)."
echo "  4. Depois DESATIVE o setup:"
echo "     az containerapp update --name $BACKEND_APP --resource-group $RESOURCE_GROUP \\"
echo "       --set properties.template.containers[0].env[10].value="
echo ""
echo "EXPANSAO FUTURA (quando o uso crescer):"
echo "  - Backend p/ 200 simultaneos (cold start zero):"
echo "      az containerapp update --name $BACKEND_APP --resource-group $RESOURCE_GROUP \\"
echo "        --cpu 1 --memory 2Gi --min-replicas 2 --max-replicas 5"
echo "  - Banco pago (apos os 12 meses gratuitos):"
echo "      az postgres flexible-server update --resource-group $RESOURCE_GROUP \\"
echo "        --name $POSTGRES_SERVER --tier Burstable --sku-name Standard_B2s"
echo "  - Sempre que precisar, o Container Apps escala sozinho ate --max-replicas."
echo "============================================================"