# App Motorista — Documentação do Projeto

Sistema web de **gestão e atualização de cadastro de clientes** para equipes de motoristas, com fluxo de **aprovação de endereços**, **carga em massa via Excel**, **fotos do local**, **geolocalização** e **navegação** (Waze / Google Maps / OpenStreetMap).

- **Frontend:** Vue 3 + Vite + Tailwind CSS + Leaflet (PWA).
- **Backend:** Python 3.12 + FastAPI + SQLAlchemy (async) + PostgreSQL.
- **Storage:** MinIO (S3) para fotos dos clientes.
- **Autenticação:** JWT local (bcrypt) e suporte a Azure AD (Microsoft) no backend.
- **Geocoding:** OpenCage (produção) com fallback para Nominatim/OSM (dev).

---

## Índice da documentação

| Documento | Conteúdo |
|---|---|
| [ARQUITETURA.md](./ARQUITETURA.md) | Visão geral da arquitetura, fluxo de dados e modelo de permissões |
| [API.md](./API.md) | Referência completa da API REST (endpoints, autenticação, payloads) |
| [FRONTEND.md](./FRONTEND.md) | Estrutura do frontend, rotas, views e composables |
| [DEPLOYMENT.md](./DEPLOYMENT.md) | Docker, Nginx, PWA, variáveis de ambiente e implantação |
| [ANALISE-ERROS.md](./ANALISE-ERROS.md) | Análise de erros encontrados e recomendações |

## Resumo rápido

1. **Login** — usuário autentica com e-mail/senha (`POST /api/auth/login`). O token JWT armazena `role`, `empresa` (AC/SIN) e permissões granulares.
2. **Pesquisa** — filtra clientes por estado/cidade/nome, visualiza dados, fotos, mapa e links de navegação.
3. **Editar** — motorista edita o cadastro e **submete para aprovação** (se não tiver permissão `aprovar`). Quem tem `aprovar`/admin edita direto.
4. **Aprovações** — aprovador revisa o diff (atual × proposto), aprova, edita antes de aprovar ou recusa.
5. **Cadastrar** — cria novos clientes com geocodificação automática do endereço.
6. **Carga Excel** — upload de `.xlsx` com preview (novos × alterados) e aplicação em lote (upsert por `codigo`).
7. **Admin de usuários** — cria/edita usuários, define empresa, role e permissões granulares.

## Stack e versões

| Camada | Tecnologia | Versão principal |
|---|---|---|
| Frontend | Vue 3 / Vite / Tailwind | `package.json` v2.0.0 |
| Mapas | Leaflet + Mapbox/OSM tiles | leaflet ^1.9.4 |
| Backend | FastAPI / uvicorn | v2.0.0 (`main.py`) |
| ORM | SQLAlchemy 2 (async) | 2.0.30 |
| Banco | PostgreSQL | 16-alpine (docker) |
| Object storage | MinIO | latest (docker) |
| Auth | PyJWT + bcrypt (+ Azure AD opcional) | PyJWT 2.8.0 |

## Estrutura de diretórios

```
app-motorista/
├── backend/                 # API FastAPI
│   ├── main.py              # App, lifespan (migrações + seed), CORS, health
│   ├── database.py          # Engine async + sessão + Base
│   ├── models.py            # User, Cliente, ClienteAlteracao, ClienteFoto
│   ├── auth.py              # JWT local, Azure AD (JWKS), dependências de authz
│   ├── limiter.py           # Rate limiting (slowapi) por IP real
│   ├── geocode.py           # Forward geocoding (OpenCage → Nominatim)
│   ├── storage.py           # MinIO/S3: upload, delete, presign, validação de imagem
│   ├── seed.py              # Dados demo (SEED_DEMO=1)
│   ├── routes/
│   │   ├── auth.py          # /api/auth (login, setup, me)
│   │   ├── users.py         # /api/users (CRUD, admin)
│   │   └── clientes.py      # /api/clientes, /locais, /alteracoes, carga, fotos
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── src/                     # Frontend Vue 3
│   ├── main.js              # Bootstrap
│   ├── App.vue              # Layout (navbar com permissões, footer versão)
│   ├── api.js               # Cliente HTTP central (fetch + token)
│   ├── authConfig.js        # (Inativo) config MSAL p/ Azure AD
│   ├── router/index.js      # Rotas + guard de autenticação/permissão
│   ├── composables/
│   │   ├── useAuth.js       # Sessão reativa, permissões, login/logout
│   │   └── useMapa.js       # Tiles, forward/reverse geocoding
│   └── views/
│       ├── LoginView.vue
│       ├── PesquisaView.vue
│       ├── EditarView.vue
│       ├── CadastrarView.vue
│       ├── CargaView.vue
│       ├── AprovacoesView.vue
│       ├── AdminView.vue
│       └── SemAcessoView.vue
├── public/icon.svg          # Ícone do PWA
├── Dockerfile               # Build frontend multi-stage (node → nginx)
├── docker-compose.yml       # minio + db + backend + frontend
├── nginx.conf               # Nginx produção (CSP rígido + HSTS)
├── nginx.local.conf         # Nginx dev (CSP liberado)
├── vite.config.js           # Vite + PWA + versão
├── tailwind.config.js
└── package.json
```

## Credenciais demo (dev, SEED_DEMO=1)

| Papel | E-mail | Senha | Permissões | Empresa |
|---|---|---|---|---|
| Admin | `admin@app.com` | `admin123` | tudo | AC |
| Visualizador | `vis@app.com` | `vis123` | visualizar | SIN |
| Editor | `editor@app.com` | `edit123` | visualizar, editar | AC |
| Cadastros | `full@app.com` | `full123` | visualizar, editar, criar, exportar | SIN |
| Aprovador | `aprov@app.com` | `aprov123` | visualizar, aprovar | AC |
| Gestor | `gest@app.com` | `gest123` | tudo (granular) | SIN |

> Em produção **não** use `SEED_DEMO=1`. Crie o primeiro admin via `POST /api/auth/setup` com `ALLOW_SETUP=1`.