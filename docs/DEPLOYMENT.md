# Deployment e Infraestrutura

## Execução local (desenvolvimento)

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # Windows
# .venv/bin/activate             # Linux/macOS
pip install -r requirements.txt
copy .env.example .env           # e preencha as variáveis
uvicorn main:app --reload --port 8000
```

Requisitos: PostgreSQL + MinIO acessíveis pelos valores de `DATABASE_URL` e `MINIO_ENDPOINT`. No arranque (lifespan) o backend:
1. Valida que `JWT_SECRET` tem ≥ 32 caracteres (aborta se não tiver).
2. Cria tabelas (`Base.metadata.create_all`) e aplica migrações leves via `ALTER TABLE ... IF NOT EXISTS` + backfill de `empresa` e da permissão `solicitacoes`.
3. Migra o endereço flat existente para a tabela `cliente_enderecos` (idempotente — só quando vazia).
4. Garante o bucket MinIO (`clientes`).
5. Roda o seed demo se `SEED_DEMO=1` (só popula tabelas vazias).

### Frontend

```bash
npm install
npm run dev        # servidor de dev na porta 5173
npm run build      # build de produção para dist/
npm run preview    # serve o build localmente
```

## Docker Compose (ambiente completo)

```bash
docker compose up --build
```

Levanta 4 serviços:

| Serviço | Porta | Observação |
|---|---|---|
| `minio` | 9000 (API), 9001 (console) | `MINIO_USER`/`MINIO_PASSWORD` (default `minioadmin`) |
| `db` | 5432 | PostgreSQL 16, com healthcheck `pg_isready` |
| `backend` | 8000 | build `./backend`, `env_file: ./backend/.env` |
| `frontend` | 80 | build multi-stage, nginx serve o `dist` |

Volumes: `pg_data` (PostgreSQL) e `minio_data` (objetos).

> O `backend/.env` deve apontar para os serviços internos do compose: `DATABASE_URL=postgresql+asyncpg://admin:admin@db:5432/appdb` e `MINIO_ENDPOINT=minio:9000`.

## Variáveis de ambiente

### Backend (`backend/.env`)

| Variável | Obrigatória | Descrição |
|---|---|---|
| `DATABASE_URL` | ✅ | URL asyncpg do PostgreSQL (aceita `postgres://` / `postgresql://`, normaliza automaticamente) |
| `JWT_SECRET` | ✅ | ≥ 32 caracteres. Gerar: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `JWT_EXPIRE_H` | | Validade do token em horas (default 8) |
| `ALLOWED_ORIGINS` | | Lista separada por vírgula (default `http://localhost:5173`) |
| `AZURE_TENANT_ID` / `AZURE_CLIENT_ID` | | Azure AD (opcional; usado para aceitar tokens Microsoft) |
| `MINIO_ENDPOINT` | | Host:porta do MinIO (default `minio:9000`) |
| `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` | | Credenciais (default `minioadmin` — **trocar em produção**) |
| `MINIO_PUBLIC_URL` | | URL pública para acesso (default `http://localhost:9000`). As **presigned URLs de fotos são assinadas contra este host** (e não contra `MINIO_ENDPOINT` interno) — em produção deve ser o host acessível pelo navegador |
| `MINIO_CLIENTES_BUCKET` | | Nome do bucket de fotos (default `clientes`) |
| `OPENCAGE_KEY` | | Chave OpenCage (produção); vazio → fallback Nominatim |
| `SEED_DEMO` | | `1` para carregar dados demo em tabelas vazias (só dev) |
| `ALLOW_SETUP` | | `1` habilita `POST /api/auth/setup` (só dev) |

### Frontend (`.env`, usada no build)

| Variável | Descrição |
|---|---|
| `VITE_API_URL` | URL da API (default `http://localhost:8000`) |
| `VITE_AZURE_CLIENT_ID` / `VITE_AZURE_TENANT_ID` / `VITE_AZURE_REDIRECT_URI` | Azure AD (atualmente **não implementado** no front) |
| `VITE_MAPBOX_TOKEN` | Token Mapbox para tiles (sem ele, usa OSM) |
| `VITE_OPENCAGE_KEY` | Chave OpenCage p/ geocoding no browser |

> ⚠️ Variáveis `VITE_*` são **embutidas no bundle** e ficam visíveis no browser. Chaves usadas no frontend são públicas por natureza (Mapbox/OpenCage têm quotas gratuitas, mas cuidado com uso indevido).

## Dockerfile do frontend

Multi-stage:
1. `node:20-alpine` — `npm ci` + `npm run build` (args `VITE_API_URL`, `VITE_MAPBOX_TOKEN`, `VITE_OPENCAGE_KEY`).
2. `nginx:alpine` — copia `dist/` e a conf do nginx escolhida via `ARG NGINX_CONF` (`nginx.conf` prod | `nginx.local.conf` dev).

## Nginx

### nginx.conf (produção)
- **HSTS** via `map $scheme $hsts_header` (só envia em HTTPS).
- Headers: `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`, **CSP rígido**, `Strict-Transport-Security`.
- `sw.js` sem cache (o browser sempre busca a versão nova do PWA).
- Assets com hash → cache 1 ano (`immutable`).
- HTML nunca cacheado (`expires -1`) — mantém CSP/atualizações sempre frescas.
- SPA fallback: `try_files $uri $uri/ /index.html`.

> A CSP de produção usa os placeholders `__CSP_API_URL__` / `__CSP_WS_URL__` / `__CSP_IMG_SRC__`, substituídos **em tempo de build** pelos args `CSP_API_URL` / `CSP_WS_URL` / `CSP_IMG_SRC` (defaults: `https://backend.devlopplay.site`, `wss://backend.devlopplay.site`, `http://localhost:9000`). Ao implantar em outro domínio, informe estes args — senão chamadas à API, notificações e fotos serão bloqueadas pelo browser.

### nginx.local.conf (dev)
CSP liberada: permite `http://localhost:8000` (+ `ws://localhost:8000` para o WebSocket), fotos do MinIO em `http://localhost:9000`, tiles Mapbox/OSM, OpenCage e Nominatim.

## CI/CD com GitHub Actions + Docker Hub

O pipeline builda as 2 imagens e publica no Docker Hub a cada push na `main`:

```
git push main
   └─ GitHub Actions (.github/workflows/docker-build.yml)
        ├─ vinidatadev/app-motorista-backend:{latest, <sha>}
        └─ vinidatadev/app-motorista-frontend:{latest, <sha>}   (nginx + dist, CSP parametrizada)
```

**Secrets necessárias** (Settings > Secrets and variables > Actions):

| Secret | Valor |
|---|---|
| `DOCKERHUB_USERNAME` | usuário do Docker Hub |
| `DOCKERHUB_TOKEN` | token de acesso (Account Settings > Security) |
| `VITE_API_URL` | ex.: `https://backend.seudominio.com` |
| `VITE_MAPBOX_TOKEN` | token Mapbox (público no bundle) |
| `VITE_OPENCAGE_KEY` | chave OpenCage |
| `CSP_API_URL` | ex.: `https://backend.seudominio.com` |
| `CSP_WS_URL` | ex.: `wss://backend.seudominio.com` |
| `CSP_IMG_SRC` | ex.: `https://storage.seudominio.com` (MinIO público ou Blob) |

> ⚠️ As `VITE_*` e `CSP_*` são **embutidas no bundle/imagem em tempo de build**.
> Cada ambiente (teste no EasyPanel, produção no Azure) precisa do **seu próprio build**
> com os valores certos, ou você aceita uma única imagem "produção".

### Subindo/atualizando na VPS (EasyPanel ou qualquer servidor com Docker)

```bash
cp .env.example .env                      # preencha MINIO_USER etc. (opcional, tem defaults)
cp backend/.env.example backend/.env      # DATABASE_URL interno, MINIO_*, JWT_SECRET...

docker compose -f docker-compose.prod.yml pull          # baixa as imagens novas
docker compose -f docker-compose.prod.yml up -d         # sobe/atualiza
```

Nada é compilado no servidor — só `pull` + `up`. Para pinar uma versão: `IMAGE_TAG=sha-<hash> docker compose -f docker-compose.prod.yml up -d`.

## Azure (produção real — caminho recomendado)

Sua conta Free (US$ 200 de crédito) reproduz fielmente o ambiente de produção. Estratégia:
**comece no mínimo (quase grátis) e expanda conforme o uso crescer** — sem mudar a aplicação.

### Arquitetura (modo gratuito inicial)

| Camada | Serviço Azure | Custo inicial |
|---|---|---|
| Frontend | **Azure Static Web Apps** (tier gratuito + CDN) | **US$ 0** |
| Backend | **Azure Container Apps** com **scale-to-zero** (`min-replicas: 0`) | **~US$ 0** (paga só quando usado) |
| Banco | **PostgreSQL Flexible Server** (tier gratuito 12 meses) | **US$ 0** |
| Fotos | **Azure Blob Storage (S3-compatible API)** | centavos |
| Registry | **ACR** SKU Basic | ~US$ 5/mês |

> O `backend/storage.py` fala com qualquer serviço compatível com S3 (MinIO, Blob S3 API).
> No Azure você elimina o container do MinIO — um ponto a menos pra manter.

### Custo total estimado

| Fase | ~US$/mês |
|---|---|
| **Início (modo gratuito):** SWA + scale-to-zero + Postgres grátis + Blob + ACR | **~US$ 5–15** |
| **Expandido (200 simultâneos, picos no horário comercial):** back com `min-replicas: 2` + scale agendado | **~US$ 50–80** |
| **Banco pago** (após os 12 meses gratuitos, B2s) | +US$ 45–60 |

### Passo a passo (do zero até o app no ar)

**Passo 1 — Provisionar a infraestrutura (uma vez)**

Abra o [Azure Cloud Shell](https://shell.azure.com) (bash; o `az` já vem) e rode o
script que provisiona tudo: Resource Group, ACR, Storage com API S3, PostgreSQL
(tier gratuito), o Container App do backend (scale-to-zero) e o Static Web Apps
do frontend. Ele imprime no final os secrets prontos para colar no GitHub.

```bash
bash scripts/azure-setup.sh
```

> 💡 Antes de rodar, edite as variáveis no topo do script (senha do Postgres, `OPENCAGE_KEY`, etc.).
> Na conta Free prefira a região `eastus2` (mais serviços free) ao invés de `brasilsouth`.

**Passo 2 — Conectar o frontend (Static Web Apps)**

No portal do Azure, abra o recurso do Static Web Apps e **conecte o repositório GitHub**
(branch `main`, build: `npm run build`, pasta de saída `dist`). O Azure cria e gerencia
o workflow de deploy do frontend — cada `git push` publica a versão nova **gratuitamente**.
A URL do frontend fica em `<hash>.azurestaticapps.net`.

**Passo 3 — Configurar o GitHub (secrets/vars)**

No GitHub (Settings → Secrets and variables → Actions), crie usando os valores que o
script imprimiu:

| Tipo | Nome | Valor |
|---|---|---|
| var | `AZURE_RESOURCE_GROUP` | `app-motorista-rg` |
| secret | `AZURE_CREDENTIALS` | JSON do service principal (impresso) |
| secret | `ACR_NAME` | `appmotoristaacr` |
| secret | `ACR_USERNAME` | `appmotoristaacr` |
| secret | `ACR_PASSWORD` | senha admin do ACR (impressa) |
| secret | `VITE_API_URL` | `https://<backend-fqdn>.azurecontainerapps.io` |
| secret | `VITE_MAPBOX_TOKEN` | sua chave Mapbox |
| secret | `VITE_OPENCAGE_KEY` | sua chave OpenCage |
| secret | `CSP_API_URL` | = `VITE_API_URL` |
| secret | `CSP_WS_URL` | `wss://` + mesmo host |
| secret | `CSP_IMG_SRC` | `https://<conta>.blob.core.windows.net` |

> ⚠️ No modo Static Web Apps, o **backend** usa o workflow `deploy-azure.yml` (abaixo).
> O **frontend** NÃO usa esse workflow — quem deploya é o próprio Static Web Apps
> (workflow automático criado na conexão). A imagem nginx do Dockerfile só é usada
> se você optar por rodar o frontend como Container App (modo alternativo).

**Passo 4 — Deploy do backend**

Rode o workflow **Deploy Azure Container Apps** manualmente (Actions → Run workflow),
ou crie uma tag:

```bash
git tag v0.1.0 && git push --tags
```

O pipeline builda o backend, publica no ACR e atualiza o Container App.

**Passo 5 — Primeiro acesso e primeiros dados**

1. Acesse a URL do **frontend** (Static Web Apps) → veja o app.
2. O backend já vem com `ALLOW_SETUP=1` e `SEED_DEMO` vazio. Crie o admin:
   `POST https://<backend>/api/auth/setup` (ou via UI se exposta).
3. Depois **desative o setup** (senão qualquer um cria admin):
   ```bash
   az containerapp update --name app-motorista-backend --resource-group app-motorista-rg \
     --set properties.template.containers[0].env[10].value=
   ```

**Atualizações futuras:** rode o workflow manualmente ou crie outra tag `v*`. O env do
backend fica no próprio Container App (não muda entre deploys).

> **WebSocket no Container Apps:** suportado por padrão (sem configurar upgrade).
> **WebSocket no Static Web Apps:** o frontend é estático; o WebSocket conecta direto ao
> backend (Container App), então não é afetado.
> **Custo:** monitore o portal (Custos). No modo gratuito (SWA + scale-to-zero + Postgres
> grátis + Blob + ACR) o custo fica em ~US$ 5–15/mês.

### Expandir quando o uso crescer (sem mudar a aplicação)

O setup nasce no mínimo. Para atender 200 usuários simultâneos em consultas curtas
(horário comercial), rode no Cloud Shell:

```bash
# Backend com capacidade + réplicas quentes (sem cold start no pico)
az containerapp update --name app-motorista-backend --resource-group app-motorista-rg \
  --cpu 1 --memory 2Gi --min-replicas 2 --max-replicas 5

# (opcional) Scale agendado por horário comercial para economizar fora do expediente
# Container Apps suporta scale rules por cron; configure no portal (Scale > Rules).

# Banco pago, após os 12 meses gratuitos
az postgres flexible-server update --resource-group app-motorista-rg \
  --name app-motorista-pg --tier Burstable --sku-name Standard_B2s
```

O Container Apps escala sozinho (HPA) até `--max-replicas`. Nada disso toca no código
da aplicação.

## Segurança implementada

- Senhas com **bcrypt** (`hash_password`/`verify_password`).
- **JWT HS256** com segredo validado (≥ 32 chars) e expiração.
- Validação de token Azure com **JWKS + audience/issuer** (quando usado).
- **Rate limiting** por IP real (`slowapi`) em login, setup, criação de usuário/cliente, carga e upload de fotos.
- **CORS** restrito (`ALLOWED_ORIGINS`), métodos e headers limitados.
- Upload de imagem valida **magic bytes** (JPEG/PNG/GIF/WEBP) e limite de 5 MB.
- Bucket MinIO **privado** — acesso só via **presigned URLs** com expiração.
- Backend roda como **usuário não-root** no Dockerfile.
- `docs_url`/`redoc_url` desativados (menos superfície de informação pública).

## Práticas de produção recomendadas

- Adicionar testes automatizados (backend: pytest + httpx/fastapi TestClient; frontend: Vitest) — hoje o projeto **não possui testes**.
- Adicionar lint/typecheck (ex.: ruff/flake8 no backend; eslint/vue-tsc no front) e um script no `package.json`.
- Paginar listas (`/clientes`, `/alteracoes`) e otimizar o carregamento de fotos (hoje N+1).
- Configurar backup do PostgreSQL e políticas de retenção no MinIO.
- Rotacionar chaves (Mapbox/OpenCage) caso algum dia tenham sido expostas em logs ou commits.
- Revisar o rate limit do login (10/min) sob bots — considerar captcha ou bloqueio por conta em caso de força bruta direcionada.