#!/usr/bin/env bash
# Continuação do setup - rode este script após o erro do database
set -euo pipefail

# Variáveis (devem ser as MESMAS que você usou antes)
RESOURCE_GROUP="app-motorista-rg"
LOCATION="centralus"  # ← foi a região que funcionou no seu caso
ACR_NAME="appmotoristaacr"
STORAGE_ACCOUNT="appmotoristastg"
POSTGRES_SERVER="app-motorista-pg"
POSTGRES_DB="appdb"
POSTGRES_USER="motorista"
POSTGRES_PASSWORD="TroqueEstaSenha123!"  # ← MESMA senha que usou antes
BACKEND_APP="app-motorista-backend"
FRONTEND_SWA_NAME="app-motorista-swa"
OPENCAGE_KEY=""
GH_SP_NAME="app-motorista-ghactions"

SUB_ID=$(az account show --query id -o tsv)

# Criar database (com o parâmetro correto)
echo "==> Criando database $POSTGRES_DB no PostgreSQL..."
az postgres flexible-server db create \
    --resource-group "$RESOURCE_GROUP" \
    --server-name "$POSTGRES_SERVER" \
    --name "$POSTGRES_DB" -o none

# Pegar credenciais já criadas
ACR_PASSWORD=$(az acr credential show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" \
    --query passwords[0].value -o tsv)
STORAGE_KEY=$(az storage account keys list --account-name "$STORAGE_ACCOUNT" \
    --resource-group "$RESOURCE_GROUP" --query "[0].value" -o tsv)

# Container Apps Environment + BACKEND
echo "==> Criando Container Apps Environment + BACKEND (scale-to-zero)..."
LA_WORKSPACE="$RESOURCE_GROUP-logs"

# Verifica se já existe o workspace
if ! az monitor log-analytics workspace show --resource-group "$RESOURCE_GROUP" \
    --workspace-name "$LA_WORKSPACE" >/dev/null 2>&1; then
    echo "    Criando Log Analytics workspace..."
    az monitor log-analytics workspace create --resource-group "$RESOURCE_GROUP" \
        --workspace-name "$LA_WORKSPACE" --location "$LOCATION" -o none
fi

LA_CUSTOMER_ID=$(az monitor log-analytics workspace show --resource-group "$RESOURCE_GROUP" \
    --workspace-name "$LA_WORKSPACE" --query customerId -o tsv | tr -d '[:space:]')
LA_KEY=$(az monitor log-analytics workspace get-shared-keys \
    --resource-group "$RESOURCE_GROUP" --workspace-name "$LA_WORKSPACE" \
    --query primarySharedKey -o tsv | tr -d '[:space:]')

# Verifica se já existe o environment
if ! az containerapp env show --resource-group "$RESOURCE_GROUP" --name app-motorista-env >/dev/null 2>&1; then
    echo "    Criando Container Apps environment..."
    az containerapp env create --resource-group "$RESOURCE_GROUP" --name app-motorista-env \
        --location "$LOCATION" \
        --logs-workspace-id "$LA_CUSTOMER_ID" --logs-workspace-key "$LA_KEY" -o none
fi

JWT_SECRET=$(openssl rand -hex 32)
DATABASE_URL="postgresql+asyncpg://$POSTGRES_USER:$POSTGRES_PASSWORD@$POSTGRES_SERVER.postgres.database.azure.com:5432/$POSTGRES_DB?sslmode=require"
MINIO_ENDPOINT="$STORAGE_ACCOUNT.blob.core.windows.net"
MINIO_PUBLIC_URL="https://$STORAGE_ACCOUNT.blob.core.windows.net"

# Backend (verifica se já existe)
if ! az containerapp show --resource-group "$RESOURCE_GROUP" --name "$BACKEND_APP" >/dev/null 2>&1; then
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
fi

BACKEND_FQDN=$(az containerapp show --name "$BACKEND_APP" --resource-group "$RESOURCE_GROUP" \
    --query properties.configuration.ingress.fqdn -o tsv)

# Frontend (Static Web Apps)
echo "==> Criando FRONTEND como Azure Static Web Apps (TIER GRATUITO)..."
if ! az staticwebapp show --resource-group "$RESOURCE_GROUP" --name "$FRONTEND_SWA_NAME" >/dev/null 2>&1; then
    az staticwebapp create \
        --name "$FRONTEND_SWA_NAME" --resource-group "$RESOURCE_GROUP" \
        --location "$LOCATION" --sku Free -o none 2>/dev/null || true
fi

# Service Principal (verifica se já existe)
echo "==> Criando/recuperando Service Principal para o GitHub Actions..."
if SP_JSON=$(az ad sp list --display-name "$GH_SP_NAME" --query "[0]" 2>/dev/null) && [ "$SP_JSON" != "null" ] && [ -n "$SP_JSON" ]; then
    echo "    Service Principal já existe. Criando nova credencial..."
    SP_APP_ID=$(echo "$SP_JSON" | jq -r .appId)
    SP_CREDS=$(az ad sp credential reset --id "$SP_APP_ID" --append)
    SP_JSON=$(az ad sp show --id "$SP_APP_ID" --query "{clientId: appId, clientSecret: null, subscriptionId: '$SUB_ID', tenantId: appOwnerOrganizationId}")
    # Mescla a senha nova no JSON
    CLIENT_SECRET=$(echo "$SP_CREDS" | jq -r .password)
    SP_JSON=$(echo "$SP_JSON" | jq --arg secret "$CLIENT_SECRET" '.clientSecret = $secret')
else
    echo "    Criando novo Service Principal..."
    SP_JSON=$(az ad sp create-for-rbac --name "$GH_SP_NAME" \
        --role Contributor \
        --scopes "/subscriptions/$SUB_ID/resourceGroups/$RESOURCE_GROUP" \
        --sdk-auth 2>/dev/null || az ad sp create-for-rbac --name "$GH_SP_NAME" \
        --role Contributor --scopes "/subscriptions/$SUB_ID/resourceGroups/$RESOURCE_GROUP")
fi

# Resumo
echo ""
echo "============================================================"
echo "  SETUP CONCLUIDO — App Motorista no Azure"
echo "============================================================"
echo ""
echo "URLs:"
echo "  Backend  (API/Swagger):   https://$BACKEND_FQDN"
echo "  Backend  (WebSocket):     wss://$BACKEND_FQDN"
echo "  Frontend:                 (Static Web Apps — aparecera apos conectar o repo no portal)"
echo ""
echo "HABILITE O PROTOCOLO S3 MANUALMENTE:"
echo "  1. Va em: https://portal.azure.com/#@/resource/subscriptions/$SUB_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Storage/storageAccounts/$STORAGE_ACCOUNT"
echo "  2. Settings > Configuration > Allow S3 protocol = Enabled > Save"
echo ""
echo "SECRETS para o GitHub Actions (Settings > Secrets and variables > Actions):"
echo ""
echo "Variables:"
echo "  AZURE_RESOURCE_GROUP = $RESOURCE_GROUP"
echo ""
echo "Secrets (copie e cole cada um):"
echo "  AZURE_CREDENTIALS = $(echo "$SP_JSON" | tr -d '\n')"
echo ""
echo "  ACR_NAME = $ACR_NAME"
echo "  ACR_USERNAME = $ACR_NAME"
echo "  ACR_PASSWORD = $ACR_PASSWORD"
echo ""
echo "  VITE_API_URL = https://$BACKEND_FQDN"
echo "  CSP_API_URL = https://$BACKEND_FQDN"
echo "  CSP_WS_URL = wss://$BACKEND_FQDN"
echo "  CSP_IMG_SRC = $MINIO_PUBLIC_URL"
echo ""
echo "  VITE_MAPBOX_TOKEN = (sua chave Mapbox - opcional)"
echo "  VITE_OPENCAGE_KEY = (sua chave OpenCage - opcional)"
echo ""
echo "PROXIMOS PASSOS:"
echo "  1. Habilite o protocolo S3 no Storage Account (link acima)"
echo "  2. Configure os secrets no GitHub: https://github.com/vinidatadev/app-motorista/settings/secrets/actions"
echo "  3. No portal do Azure, conecte o Static Web Apps ao repositorio GitHub"
echo "  4. Rode o workflow de deploy: git tag v0.1.0 && git push origin v0.1.0"
echo "  5. Crie o admin: POST https://$BACKEND_FQDN/api/auth/setup"
echo "  6. Desative o setup:"
echo "     az containerapp update --name $BACKEND_APP --resource-group $RESOURCE_GROUP \\"
echo "       --set 'properties.template.containers[0].env[?(@.name==\"ALLOW_SETUP\")].value=' "
echo "============================================================"
