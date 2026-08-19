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

> ⚠️ A CSP de produção tem `connect-src` **hardcoded** com `https://backend.devlopplay.site` (e `wss://backend.devlopplay.site` para o WebSocket) e `img-src` com `http://localhost:9000` (fotos do MinIO). Ao implantar em outro domínio, atualize estes valores — senão chamadas à API, notificações e fotos serão bloqueadas pelo browser.

### nginx.local.conf (dev)
CSP liberada: permite `http://localhost:8000` (+ `ws://localhost:8000` para o WebSocket), fotos do MinIO em `http://localhost:9000`, tiles Mapbox/OSM, OpenCage e Nominatim.

## Implantação (EasyPanel / VPS)

1. Suba os serviços com `docker compose up --build` (ou via painel, usando os Dockerfiles).
2. Configure o domínio com HTTPS (o nginx assume `listen 80`; o TLS fica a cargo do proxy reverso/painel).
3. Defina `NGINX_CONF=nginx.conf` para produção.
4. Ajuste a CSP (`connect-src` + `wss://` + `img-src` do MinIO) para o domínio real da API/fotos.
5. No `backend/.env`:
   - `JWT_SECRET` forte (≥ 32 chars).
   - `MINIO_ACCESS_KEY`/`MINIO_SECRET_KEY` fora do padrão.
   - `MINIO_PUBLIC_URL` com o host público acessível pelo navegador (base das presigned URLs das fotos).
   - `SEED_DEMO=` vazio e `ALLOW_SETUP=` vazio.
   - Crie o primeiro admin com `ALLOW_SETUP=1` temporário + `POST /api/auth/setup`, e depois desative.
6. `ALLOWED_ORIGINS` com o domínio real do frontend.

> **WebSocket em produção:** o WebSocket (`/ws/notificacoes`) precisa de **upgrade** habilitado no proxy reverso/painel. Traefik/EasyPanel/nginx habilitam por padrão; se usar outro proxy, garanta `Upgrade`/`Connection: upgrade`. Em HTTPS o frontend usa `wss://`.

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