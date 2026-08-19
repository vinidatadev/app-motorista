# API — Referência completa

Base URL: `/api` (servida pelo FastAPI na porta 8000). Health check em `/health` (fora do prefixo).

Autenticação: enviar `Authorization: Bearer <token>` (JWT local HS256 ou token Azure RS256).

> **Sem docs interativas:** `docs_url=None` e `redoc_url=None` (desativadas em `main.py`).

---

## Autenticação — `/api/auth`

### `GET /api/auth/me`
Retorna os dados **atuais** do usuário (lidos do banco — role/permissões frescas).

```json
{ "email": "editor@app.com", "name": "Editor Demo", "role": "user",
  "empresa": "AC", "permissions": ["visualizar", "editar"], "provider": "local" }
```
Protegido por: qualquer usuário autenticado.

### `POST /api/auth/login`
Rate limit: **10/min por IP**. Body:
```json
{ "email": "editor@app.com", "password": "edit123" }
```
Retorna `{ access_token, token_type, name, role, empresa, permissions }`.

### `POST /api/auth/setup`
Rate limit: **5/min por IP**. Cria o **primeiro admin**. Só funciona com `ALLOW_SETUP=1` **e** enquanto a tabela `users` estiver vazia. Body:
```json
{ "email": "admin@empresa.com", "name": "Admin", "password": "senha-forte" }
```
Após o primeiro uso (usuários criados), retorna `403 "Setup já realizado"`.

---

## Usuários — `/api/users`

Todas as rotas exigem **role admin**.

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/users/` | Lista usuários |
| POST | `/api/users/` | Cria usuário (rate limit 10/min) |
| PATCH | `/api/users/{id}` | Atualiza usuário |
| DELETE | `/api/users/{id}` | Remove usuário (impossível remover a si mesmo) |

### POST body
```json
{
  "email": "novo@empresa.com",
  "name": "Novo Usuário",
  "auth_provider": "local",            // "local" | "microsoft"
  "role": "user",                      // "admin" | "user"
  "empresa": "AC",                     // "AC" | "SIN"
  "permissions": ["visualizar", "editar"],
  "password": "min-8-caracteres"       // obrigatório se auth_provider="local"
}
```

### PATCH body (todos opcionais)
`name`, `role`, `empresa`, `permissions`, `is_active`, `password`.
Regras: ao virar admin, permissões são limpas; `password` re-hashiza a senha.

---

## Clientes — `/api/clientes`

### `GET /api/clientes`
Lista clientes (filtros opcionais: `?estado=SP&cidade=São Paulo`). Exige `visualizar`.
Cada cliente retorna os campos de nível cliente (incluindo o **espelho** do primeiro endereço em `cep`/`rua`/...) e a lista `enderecos` (cada um com sua `contatos`).

### `GET /api/clientes/export`
Gera `.xlsx` (OpenPyXL) com os mesmos filtros. Exige `exportar`. Saída no formato da carga (uma linha por endereço).

### `POST /api/clientes`
Cria cliente (rate limit 30/min). Exige `criar`. Se lat/lng vazios e houver endereço, faz **geocoding automático**. `codigo` duplicado → `409`.

Body: `codigo`, `nome_razao_social` (obrigatório), `telefone`, `pessoa_contato` e `enderecos` (lista opcional):

```json
{
  "codigo": "C100",
  "nome_razao_social": "Exemplo Ltda",
  "telefone": "(11) 9 9999-9999",
  "pessoa_contato": "João",
  "enderecos": [
    {
      "nome": "Loja 01",
      "cep": "01000-000", "rua": "Av. Paulista", "numero": "1500",
      "bairro": "Bela Vista", "cidade": "São Paulo", "estado": "SP",
      "latitude": -23.561414, "longitude": -46.656015,
      "ponto_referencia": null, "observacao": null,
      "contatos": [ { "nome": "Fulano", "telefone": "(11) 9 1111-2222" } ]
    }
  ]
}
```

Regras:
- O **primeiro endereço** da lista é espelhado nos campos flat do cliente (`cep`, `rua`, `numero`, `bairro`, `cidade`, `estado`, `latitude`, `longitude`, `ponto_referencia`, `observacao`) para manter compatibilidade com filtros/exportação.
- Latitude validada entre `-90` e `90`; longitude entre `-180` e `180` (422 com mensagem clara em vez de erro de banco).

### `GET /api/clientes/{id}`
Detalhe do cliente com `fotos` (presigned URLs, 1h) e `enderecos` (cada um com `contatos`). Exige `visualizar`.

### `PUT /api/clientes/{id}`
Atualiza cliente (rate limit 60/min). Exige `editar`. Aceita os campos de nível cliente e/ou a lista `enderecos` (se enviada, **substitui** todos os endereços/contatos).

Comportamento depende da permissão do usuário autenticado:
- **Admin ou quem tem `aprovar`**: aplica direto; `status_endereco` volta a `aprovado`.
- **Demais (motorista)**: grava **submissão pendente** (snapshot em `cliente_alteracoes`, incluindo `enderecos`) e marca o cliente como `atualizando`.

Regras:
- Se o cliente já estiver `atualizando` → `409` (bloqueado até revisão).
- Submissões pendentes anteriores do mesmo cliente são removidas (mantém só a mais nova).
- Geocoding automático quando lat/lng ausentes.

### `DELETE /api/clientes/{id}`
Exclui cliente, removendo fotos do MinIO antes. Exige `deletar`.

### Fotos
| Método | Rota | Descrição |
|---|---|---|
| POST | `/api/clientes/{id}/fotos` | Upload (rate 20/min). Exige `editar`. JPEG/PNG/GIF/WEBP ≤ 5 MB, valida magic bytes. Bloqueado se cliente `atualizando` |
| DELETE | `/api/clientes/{id}/fotos/{fotoId}` | Remove foto (MinIO + banco). Exige `editar`. Bloqueado se cliente `atualizando` |

### Histórico
`GET /api/clientes/{id}/alteracoes` — histórico de submissões do cliente (ordem desc). Exige `visualizar`.

### Carga em massa
| Método | Rota | Descrição |
|---|---|---|
| POST | `/api/clientes/carga/preview` | Rate 10/min. Exige `carga`. Retorna preview (novos × alterados com diff) |
| POST | `/api/clientes/carga/aplicar` | Rate 5/min. Exige `carga`. Executa upsert por `codigo` |

Limites: arquivo ≤ 5 MB, ≤ 2.000 linhas (validado no aplicar), geocoding ≤ 50 registros/request.

**Formato da planilha (uma linha por endereço):** o mesmo `codigo` pode repetir em várias linhas — cada linha vira um endereço do cliente. Colunas:

```
codigo, nome_razao_social, telefone, pessoa_contato,
endereco_apelido, cep, rua, numero, bairro, cidade, estado,
latitude, longitude, ponto_referencia, observacao,
contato1_nome, contato1_telefone,
contato2_nome, contato2_telefone,
contato3_nome, contato3_telefone
```

Ao aplicar, os endereços do cliente são **substituídos** pelos da planilha (o primeiro vira o espelho flat).

`preview` retorna:
```json
{
  "total_linhas": 10,
  "novos": [ { "codigo": "C100", "nome_razao_social": "...", "enderecos": [ ... ] } ],
  "alterados": [ { "codigo": "C001", "nome_razao_social": "...",
                   "mudancas": { "telefone": { "de": "antigo", "para": "novo" }, "enderecos": { "de": "2 endereço(s)", "para": "3 endereço(s)" } },
                   "enderecos": [ ... ], "id": "uuid" } ],
  "quantidade_novos": 6,
  "quantidade_alterados": 4
}
```

`aplicar` retorna `{ "inseridos": n, "atualizados": n, "geocoded": n, "total": n }`.

---

## Locais — `/api/locais`

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/locais/estados` | Lista UFs distintas presentes em clientes. Exige `visualizar` |
| GET | `/api/locais/cidades?estado=SP` | Lista cidades distintas de uma UF. Exige `visualizar` |

---

## Submissões (aprovações) — `/api/alteracoes`

Todas exigem a permissão **`aprovar`**.

### `GET /api/alteracoes`
Lista submissões (mais recentes primeiro). Filtros:
- `?status=pendente|aprovado|recusado|editado`
- `?empresa=AC|SIN` (filtra pela empresa do **solicitante**)

Cada item traz:
```json
{
  "id": "uuid", "cliente_id": "uuid",
  "cliente_codigo": "C001", "cliente_nome": "Supermercado Bom Preço",
  "snapshot": { "rua": "...", "numero": "1500", ..., "enderecos": [ { "nome": "Loja 01", "rua": "...", "contatos": [ ... ] } ] },
  "cliente_atual": { "rua": "...", "numero": "1400", ..., "enderecos": [ ... ] },
  "motorista_nome": "Joao", "motorista_empresa": "AC",
  "status": "pendente",
  "observacao_revisao": null,
  "created_at": "2026-08-17T10:00:00+00:00",
  "revisado_at": null, "revisado_por_nome": null, "revisado_por_empresa": null
}
```

O `snapshot` e o `cliente_atual` agora incluem a chave `enderecos` (conjunto completo de endereços/contatos propostos × atuais) para o diff. Ao aprovar/editar, os endereços do snapshot são aplicados.

### `POST /api/alteracoes/{id}/aprovar`
Aplica o snapshot (incluindo endereços/contatos) ao cliente e marca como `aprovado`. Erro `400` se já não estiver `pendente`. Notifica o motorista solicitante.

### `POST /api/alteracoes/{id}/recusar`
Mantém o endereço atual; registra motivo. Body opcional: `{ "observacao": "motivo" }` (máx. 500 chars). Notifica o motorista solicitante.

### `PUT /api/alteracoes/{id}/editar`
Aprovador ajusta o snapshot antes de aplicar (overrides por cima do snapshot original) e aprova como `editado`. Notifica o motorista solicitante.

---

## Notificações — `/api/notificacoes` + WebSocket

Notificações por usuário, exibidas no sino do frontend. Persistidas no banco e entregues em **tempo real** via WebSocket.

### `GET /api/notificacoes`
Lista as notificações do usuário logado (mais recentes primeiro, máx. 60) e a contagem de não lidas.

```json
{ "nao_lidas": 2, "notificacoes": [ { "id": "uuid", "tipo": "nova_solicitacao", ... } ] }
```

### `POST /api/notificacoes/{id}/ler`
Marca uma notificação como lida.

### `POST /api/notificacoes/ler-todas`
Marca todas como lidas.

### WebSocket — `GET /ws/notificacoes?token=<JWT>`
Conecta o usuário ao push em tempo real. Ao conectar, envia `{ "event": "init", "nao_lidas": n }`. A cada nova notificação, envia `{ "event": "nova_notificacao", "notificacao": { ... } }`.

**Tipos de notificação** (`tipo`): `nova_alteracao` (aprovador tem algo para revisar), `aprovada` / `recusada` / `editada` (resposta ao motorista), `nova_solicitacao` (time tem nova solicitação), `solicitacao_concluida` / `solicitacao_recusada` (resposta ao solicitante).

---

## Solicitações — `/api/solicitacoes`

Solicitações abertas pelos usuários na Pesquisa quando não encontram o cliente (**cadastro novo**) ou quando os contatos estão desatualizados (**atualizar contato**).

### `POST /api/solicitacoes`
Abre uma solicitação (rate limit 20/min). Exige estar autenticado.

```json
{
  "tipo": "novo_cliente",              // "novo_cliente" | "atualizar_contato"
  "cliente_codigo": "C100",            // opcional (novo_cliente)
  "cliente_id": "uuid",                // obrigatório para atualizar_contato
  "cliente_nome": "Mercadinho Nova Era",
  "descricao": "cliente mencionou loja no bairro X..."
}
```

Ao abrir, notifica o **time de solicitações** (permissão `solicitacoes` + admins).

### `GET /api/solicitacoes`
Lista solicitações (mais recentes primeiro). Filtros opcionais: `?status=aberta|em_andamento|concluida|recusada`, `?tipo=novo_cliente|atualizar_contato`.
- **Time** (perm `solicitacoes` ou admin): vê **todas**.
- **Demais usuários**: veem apenas as que abriram.
Resposta: `{ "eh_equipe": true, "solicitacoes": [ ... ] }`.

### `POST /api/solicitacoes/{id}/status`
O time altera o status. Exige `solicitacoes`.

```json
{ "status": "concluida", "observacao_resolucao": "cadastrado como C200", "cliente_codigo": "C200" }
```

- `status`: `em_andamento` | `concluida` | `recusada`.
- Ao **concluir** com `cliente_codigo`, o backend tenta vincular o cliente existente com aquele código (a notificação ao solicitante abre o cliente na Pesquisa).
- Ao **concluir/recusar**, notifica o solicitante.

---

## Health

### `GET /health`
```json
{ "status": "ok", "version": "2.0.0" }
```

---

## Códigos de erro comuns

| Código | Quando |
|---|---|
| 401 | Token ausente/inválido/expirado |
| 403 | Usuário inativo, sem role/permissão, setup desativado |
| 404 | Cliente, usuário, submissão ou foto inexistente |
| 409 | `codigo`/e-mail duplicado; cliente com alteração pendente |
| 422 | Validação de schema; arquivo inválido/limites excedidos |
| 429 | Rate limit excedido (slowapi) |