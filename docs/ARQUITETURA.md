# Arquitetura

## Visão geral

A aplicação é dividida em **frontend SPA (Vue 3)** e **API REST (FastAPI)**, com **PostgreSQL** como banco relacional e **MinIO** (compatível com S3) para armazenamento de fotos. Um **nginx** serve o build estático do frontend e aplica headers de segurança/CSP.

```
 Navegador (PWA)
   │  HTTPS
   ▼
 ┌─────────────┐      /api/*        ┌──────────────────┐
 │  nginx      │ ─────────────────► │  FastAPI (uvicorn)│
 │ (static+csp)│   /ws/notificacoes │      ▲            │
 └─────────────┘ ◄──── WebSocket ────┘      │           │
                                             ├─► PostgreSQL 16
                                             ├─► MinIO (S3)  ──► fotos (presigned URLs)
                                             └─► OpenCage / Nominatim (geocoding)
```

O frontend conecta um **WebSocket** (`/ws/notificacoes`, autenticado por JWT) para receber notificações em tempo real. O backend também serve os endpoints REST de notificações e solicitações.

## Fluxos principais

### 1. Autenticação

1. Usuário envia `email` + `password` → `POST /api/auth/login` (limitado a 10/min por IP).
2. Backend valida no banco (bcrypt) e retorna um **JWT HS256** com `sub`, `email`, `name`, `role`, `empresa`, `permissions`, `exp`.
3. Frontend guarda o token no `sessionStorage` e o envia como `Authorization: Bearer <token>`.
4. A cada carregamento, o frontend chama `GET /api/auth/me` para **sincronizar** role/permissões com o banco (o token pode estar defasado após mudanças do admin).

O backend também aceita **tokens Azure AD (RS256)**: baixa o JWKS do tenant (`login.microsoftonline.com/{tenant}/discovery/v2.0/keys`), valida audience/issuer e localiza o usuário pelo e-mail (`preferred_username`/`email`/`upn`). A configuração MSAL no frontend (`src/authConfig.js`) **não está implementada** (o login atual é somente local).

### 2. Edição com aprovação de endereço

O modelo de permissões separa **quem pode editar** de **quem pode aprovar**:

- **Admin** ou usuário com permissão `aprovar`: `PUT /api/clientes/{id}` altera o cliente **diretamente** e marca `status_endereco = 'aprovado'`.
- **Motorista** com permissão `editar` (mas sem `aprovar`): a alteração **não** toca o cliente. É gravado um **snapshot** em `cliente_alteracoes` com `status='pendente'` e o cliente fica `status_endereco = 'atualizando'` (bloqueado para novas edições/fotos).

O aprovador então revisa na tela **Aprovações**:

| Ação | Endpoint | Efeito |
|---|---|---|
| Aprovar | `POST /api/alteracoes/{id}/aprovar` | Aplica snapshot (incl. endereços/contatos) ao cliente, volta status p/ `aprovado`, registra revisor, **notifica o motorista** |
| Editar e aprovar | `PUT /api/alteracoes/{id}/editar` | Aprovador ajusta o snapshot e aplica (status `editado`), **notifica o motorista** |
| Recusar | `POST /api/alteracoes/{id}/recusar` | Mantém endereço atual, limpa `alterado_por_*`, registra motivo, **notifica o motorista** |

Ao aprovar/recusar, `alterado_por_*` continua apontando para **quem solicitou** (o motorista) — o revisor fica em `revisado_por_*`.

### 2b. Notificações em tempo real

- Cada usuário autenticado conecta um **WebSocket** (`/ws/notificacoes?token=JWT`). O `ConnectionManager` (`backend/notify.py`) mantém o mapa `user_id → conexões`.
- Ao **submeter** uma alteração, o backend grava uma `Notificacao` (`nova_alteracao`) para os **aprovadores** (admin + usuários com `aprovar` da **mesma empresa** do solicitante) e faz push no WebSocket.
- Ao **aprovar/recusar/editar**, o backend notifica o **motorista** (`aprovada`/`recusada`/`editada`).
- O frontend (`useNotificacoes.js`) mantém o sino atualizado via push + um **refresh periódico** (45 s) e ao abrir o menu — rede de segurança caso o WebSocket caia.

### 2c. Solicitações (cadastro novo / contato atualizado)

- Na **Pesquisa**, o usuário abre uma `Solicitacao` (`novo_cliente` quando não acha o cliente, ou `atualizar_contato` quando os contatos estão desatualizados).
- O **time de solicitações** (permissão `solicitacoes` + admin) é notificado (`nova_solicitacao`) e atende na tela **Solicitações**: inicia, conclui (com nota e opcionalmente o `cliente_codigo` cadastrado) ou recusa.
- Ao **concluir/recusar**, o solicitante recebe a notificação de volta; se vinculado a um cliente, a notificação abre o cliente na **Pesquisa**.

### 3. Carga em massa (Excel)

1. Usuário com permissão `carga` envia `.xlsx` (máx. 5 MB, máx. 2.000 linhas) em `POST /api/clientes/carga/preview`.
2. O backend lê a planilha, mapeia colunas por nome (primeira linha) e devolve:
   - `novos` (código inexistente → insert)
   - `alterados` (código existente → comparação campo a campo com `de`/`para`)
3. `POST /api/clientes/carga/aplicar` executa o **upsert por `codigo`**, com **geocodificação automática** para registros sem lat/lng (limitada a 50 por request, 1s de intervalo para respeitar o rate limit do Nominatim).
4. **Formato: uma linha por endereço.** O mesmo `codigo` pode repetir em várias linhas — cada linha vira um endereço do cliente, com até 3 contatos (colunas `contato1..3_nome/telefone`). Ao aplicar, os endereços são substituídos (o primeiro vira o espelho flat).

### 4. Geocoding

| Provedor | Uso | Quando |
|---|---|---|
| **OpenCage** | Forward (endereço→lat/lng) e reverse (lat/lng→endereço) | Chave definida (produção) |
| **Nominatim/OSM** | Fallback gratuito | Sem chave (dev local) |

A chave é usada em dois lugares: no **backend** (`OPENCAGE_KEY` → `geocode.py`) e no **frontend** (`VITE_OPENCAGE_KEY` → `useMapa.js`), que faz reverse geocoding direto do browser ao arrastar o pin.

## Modelo de dados

### users
| Campo | Tipo | Notas |
|---|---|---|
| id | UUID (PK) | |
| email | String(254), unique | Chave de identificação p/ login e Azure |
| name | String(200) | |
| password_hash | String? | Só p/ `auth_provider='local'` |
| auth_provider | String(20) | `local` \| `microsoft` |
| role | String(20) | `admin` \| `user` |
| empresa | String(10) | `AC` \| `SIN` (obrigatório) |
| permissions | ARRAY(String) | `visualizar, editar, criar, deletar, carga, exportar, aprovar, solicitacoes` |
| is_active | Boolean | |
| created_at | DateTime(tz) | |

### clientes
| Campo | Tipo | Notas |
|---|---|---|
| id | UUID (PK) | |
| codigo | String(50), unique | Chave do upsert em carga |
| nome_razao_social | String(150) | |
| telefone / pessoa_contato | String | Contato principal do cliente |
| cep / rua / numero / bairro / cidade / estado | String | **Espelho do primeiro endereço** (compatibilidade com filtros/exportação) |
| latitude / longitude | Numeric | **Espelho do primeiro endereço** |
| ponto_referencia / observacao | String | Campos livres (também espelhados do 1º endereço) |
| status_endereco | String(20) | `aprovado` \| `atualizando` |
| alterado_por_user_id / alterado_por_nome / alterado_por_empresa / alterado_em | — | Quem solicitou a última alteração |
| updated_at | DateTime(tz) | Auto (SQLAlchemy `onupdate`) |

> **Modelo normalizado de endereços/contatos:** os dados de endereço vivem em `cliente_enderecos` (vários por cliente) e os contatos em `cliente_contatos` (vários por endereço). Os campos flat de `clientes` apenas **espelham o primeiro endereço** para não quebrar filtros, exportação e a carga em massa — a fonte de verdade é a tabela de endereços.

### cliente_enderecos
| Campo | Tipo | Notas |
|---|---|---|
| id | UUID (PK) | |
| cliente_id | UUID | Dono do endereço |
| nome | String(100)? | Apelido (ex.: "Loja 01", "Filial Centro") |
| ordem | Integer | 0 = principal |
| cep / rua / numero / bairro / cidade / estado | String | Endereço |
| latitude / longitude | Numeric | Coordenadas |
| ponto_referencia / observacao | String | Campos livres |
| created_at / updated_at | DateTime(tz) | |

### cliente_contatos
| Campo | Tipo | Notas |
|---|---|---|
| id | UUID (PK) | |
| endereco_id | UUID | Endereço ao qual pertence |
| nome | String(100) | Nome do contato |
| telefone | String(20)? | Telefone |
| created_at | DateTime(tz) | |

### cliente_alteracoes
| Campo | Tipo | Notas |
|---|---|---|
| id | UUID (PK) | |
| cliente_id | UUID | FK lógica (sem constraint) |
| snapshot | JSON | Campos propostos (inclui `enderecos` com `contatos`) |
| motorista_user_id / nome / empresa | — | Quem solicitou |
| status | String(20) | `pendente` \| `aprovado` \| `recusado` \| `editado` |
| observacao_revisao | String(500)? | Motivo de recusa / obs. da revisão |
| revisado_at / revisado_por_user_id / nome / empresa | — | Quem revisou |
| created_at | DateTime(tz) | |

### cliente_fotos
| Campo | Tipo | Notas |
|---|---|---|
| id | UUID (PK) | |
| cliente_id | UUID | |
| url | String(500) | URL pública armazenada (nunca exposta — serve só p/ extrair bucket/key) |
| created_at | DateTime(tz) | |

> **Nota:** o bucket é **privado**. As fotos são sempre servidas por **presigned URLs** com expiração de 1h geradas pela API (`storage.presign_url`). As URLs são assinadas contra `MINIO_PUBLIC_URL` (host acessível pelo navegador), **não** contra o endpoint interno do Docker.

### notificacoes
| Campo | Tipo | Notas |
|---|---|---|
| id | UUID (PK) | |
| user_id | UUID | Destinatário |
| tipo | String(30) | `nova_alteracao`, `aprovada`, `recusada`, `editada`, `nova_solicitacao`, `solicitacao_concluida`, `solicitacao_recusada` |
| titulo / mensagem | String | Texto exibido no sino |
| link | String(300)? | Rota do frontend ao clicar |
| cliente_id / alteracao_id | UUID? | Referências de contexto |
| lida | Boolean | |
| created_at | DateTime(tz) | |

### solicitacoes
| Campo | Tipo | Notas |
|---|---|---|
| id | UUID (PK) | |
| tipo | String(30) | `novo_cliente` \| `atualizar_contato` |
| status | String(20) | `aberta` \| `em_andamento` \| `concluida` \| `recusada` |
| solicitante_user_id / nome / empresa | — | Quem abriu |
| cliente_id / cliente_codigo / cliente_nome | — | Cliente de contexto |
| descricao | String(5000)? | Detalhes da solicitação |
| resolvido_por_user_id / nome / empresa | — | Quem atendeu |
| observacao_resolucao | String(2000)? | Nota/motivo da resolução |
| created_at / resolvido_at | DateTime(tz) | |

## Autorização

- **Admin**: passa em qualquer rota/verificação.
- **User**: precisa da permissão granular correspondente à ação:
  - `visualizar` → listar, obter, locais, histórico
  - `editar` → atualizar cliente, upload/delete de fotos (gera submissão pendente se não tiver `aprovar`)
  - `aprovar` → aprovar/editar/recusar submissões e editar cliente diretamente
  - `criar` → criar cliente
  - `deletar` → excluir cliente
  - `carga` → preview/aplicar planilha
  - `exportar` → exportar Excel
  - `solicitacoes` → atender/alterar status de solicitações e ver todas (time de solicitações)

As dependências FastAPI `require_user(required_role=...)` e `require_permission(...)` em `backend/auth.py` centralizam essa lógica (ambas re-leem o usuário do banco a cada request — mudanças de permissão valem imediatamente, sem esperar o token expirar).

## Empresas (AC/SIN)

O sistema distingue dois grupos de trabalho por empresa. A empresa é armazenada em `users.empresa`, registrada em `clientes.alterado_por_empresa` e `cliente_alteracoes.motorista_empresa`/`revisado_por_empresa`. A tela de Aprovações permite **filtrar por empresa do solicitante** (`?empresa=AC|SIN`). Não há isolamento obrigatório de dados por empresa nas demais telas (todos com `visualizar` veem os mesmos clientes).

## Considerações de desempenho

- `listar_clientes` carrega fotos, endereços e contatos em **lote** (`WHERE ... IN (...)`) — sem N+1.
- `listar_alteracoes` faz um `JOIN` com clientes e carrega tudo sem paginação — em volumes grandes vale paginar.
- `GET /api/users/` carrega tudo sem paginação — paginar em escala.
- Upload de fotos valida **magic bytes** antes de gravar (JPEG/PNG/GIF/WEBP), impedindo conteúdo arbitrário no bucket.
- WebSocket de notificações mantém 1 conexão por usuário; o `ConnectionManager` é leve (mapa user_id → sockets).