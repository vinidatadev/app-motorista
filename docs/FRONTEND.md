# Frontend — Vue 3 + Vite + Tailwind

## Visão geral

SPA em Vue 3 (Composition API) com Vue Router, Tailwind CSS e Leaflet para mapas. Build via Vite (com plugin PWA). O frontend roda servido por nginx (build estático) ou pelo servidor de dev do Vite (porta 5173).

## Bootstrap e estrutura

- `src/main.js` — cria o app, instala o router e monta em `#app`.
- `src/App.vue` — layout global: navbar com links condicionados a permissões, badge de empresa, avatar, botão sair e rodapé com a versão (`__APP_VERSION__` injetada pelo Vite).
- `src/style.css` — importa Leaflet CSS, Tailwind base/components/utilities e corrige o caminho do ícone padrão do Leaflet.
- `public/icon.svg` — ícone usado no `index.html` e no manifesto do PWA.

## Rotas — `src/router/index.js`

| Rota | Nome | Permissão necessária |
|---|---|---|
| `/` | — | redireciona para `/login` |
| `/login` | login | pública |
| `/clientes/pesquisa` | pesquisa | `visualizar` |
| `/clientes/editar` | editar | `editar` |
| `/clientes/cadastrar` | cadastrar | `criar` |
| `/clientes/carga` | carga | `carga` |
| `/aprovacoes` | aprovacoes | `aprovar` |
| `/admin/usuarios` | usuarios | admin |
| `/sem-acesso` | sem-acesso | pública |

### Guard de navegação (`router.beforeEach`)

1. Rota com `meta.auth`? Se não houver token válido → redireciona para `/login` com `redirect`.
2. Restaura a sessão a partir do token (`carregarSessao`, síncrono).
3. Sincroniza permissões com o backend **uma vez por sessão** (`sincronizarPermissoes` + flag `permSincronizadas`).
4. Se `meta.admin` e usuário não for admin → `/sem-acesso`.
5. Se `meta.perm` e usuário não tiver a permissão → `/sem-acesso`.

> Observação: a flag `permSincronizadas` é global do módulo e **nunca é resetada no logout**. Como `loginComToken` também chama `sincronizarPermissoes`, o comportamento prático é correto, mas vale revisar para tornar o guard mais previsível em cenários de troca de usuário.

## Camada de API — `src/api.js`

- `BASE_URL` = `import.meta.env.VITE_API_URL` (default `http://localhost:8000`).
- Token salvo em `sessionStorage` sob a chave `local_token`.
- Funções utilitárias: `saveLocalToken`, `getLocalToken`, `clearLocalToken`, `decodeTokenPayload` (base64), `isTokenValid` (checa `exp`).
- `request(method, path, body)` — centraliza `fetch` com header JSON + Bearer token, converte erros da API (campo `detail`) em `Error` legível.
- Objetos de acesso:
  - `api.auth` — `me`, `login`
  - `api.locais` — `estados`, `cidades`
  - `api.clientes` — `listar`, `obter`, `criar`, `atualizar`, `remover`, `uploadFoto` (FormData), `deletarFoto`, `alteracoes.{listar,aprovar,recusar,editar,historico}`, `exportar` (blob), `previewCarga`, `aplicarCarga`
  - `api.users` — `listar`, `criar`, `atualizar`, `remover`

## Composables

### `src/composables/useAuth.js`
Estado reativo global da sessão:
- `usuario` (`ref`), `autenticado` (`computed`).
- `carregarSessao()` — restaura do token (síncrono; não chama a API).
- `sincronizarPermissoes()` — chama `GET /api/auth/me` e atualiza role/permissões no estado (resolve o caso de admin alterar permissões sem novo login).
- `loginComToken(token)` — salva o token, restaura sessão e sincroniza permissões.
- `logout()` — limpa token e estado.
- `temPermissao(perm)` — admin sempre `true`; senão verifica `permissions`.
- `isAdmin()` — checa `role === 'admin'`.

### `src/composables/useMapa.js`
- `tileUrl()` / `tileAttribution()` / `tileMaxZoom()` — Mapbox se `VITE_MAPBOX_TOKEN`, senão OSM.
- `reverseGeocode(lat, lng)` — OpenCage se `VITE_OPENCAGE_KEY`, senão Nominatim. Retorna `{ cep, rua, numero, bairro, cidade, estado }`.
- `forwardGeocode(query)` — OpenCage/Nominatim. Retorna `{ lat, lng }`.
- `UF_POR_NOME` — mapeia nome do estado para sigla.

## Views

### LoginView
Formulário e-mail/senha → `api.auth.login` → `loginComToken` → redireciona para `route.query.redirect` ou `/clientes/pesquisa`.

### PesquisaView
- Filtros independentes: UF, cidade, busca por nome (`datalist`).
- Painel de detalhe readonly: badges de estado/cidade, status de "atualização pendente", grid de dados, **fotos** (links), **mapa preview** (Leaflet) e **endereço completo** com links de navegação (Waze/Google/OSM) — tanto pelo **pin** (coordenadas + texto) quanto pelo **endereço digitado**.
- Ações: Editar (se `editar`), Excluir (se `deletar`), Exportar Excel (se `exportar`).

### EditarView
- Seleção do cliente (UF → cidade → busca), com pré-seleção via `?cliente=id`.
- Formulário de edição com mapa interativo:
  - Arrastar pin → atualiza lat/lng → **reverse geocoding** (debounce 600 ms) preenche rua/numero/cep/cidade/estado.
  - Botão "Pegar Localização Atual" (Geolocation API).
  - Botão "Reposicionar pin no endereço digitado" (forward geocoding).
  - **Detecção de divergência** número digitado × número do pin → modal de confirmação antes de salvar.
- Fotos: upload da galeria ou câmera (`capture="environment"`), visualização e exclusão.
- Bloqueio em modo `somenteLeitura` quando cliente está `atualizando` (alteração pendente).
- Salvar → `PUT /api/clientes/{id}`; se o usuário não tem `aprovar`, o backend cria a submissão e o banner informa "Submissão enviada para aprovação".

### CadastrarView
Formulário de criação com máscara de telefone, validação mínima e redirecionamento para a pesquisa após sucesso.

### CargaView
- Download de **template**, upload por clique/arrastar e soltar, preview (cards de resumo novos × alterados com diff `de → para`), e confirmação da aplicação.
- Exibe contadores de resultado ao aplicar.

### AprovacoesView
- Filtros por status (pendente/aprovado/editada/recusada/todas, com contagens) e por empresa do solicitante (AC/SIN).
- Card por submissão: status, autor, data, diff **atual × proposto** (destaca campos alterados), snapshot de já revisadas.
- Ações para pendentes: **Editar e aprovar** (modal com formulário), **Aprovar**, **Recusar** (modal com motivo).

### AdminView
- CRUD de usuários: formulário com nome, e-mail, role, empresa, senha, ativo e **checkboxes de permissões granulares**.
- Tabela de usuários com badges de role/empresa/permissões/status, edição e exclusão (impossível excluir a si mesmo).

### SemAcessoView
Tela de acesso negado com permissões atuais e botão "Recarregar" que re-sincroniza com o banco (para quando o admin liberar acesso).

## Mapas (Leaflet)

- Ícones padrão corrigidos via `mergeOptions` com imports do Vite (PesquisaView e EditarView).
- `mapaEl` é um `ref`; o mapa é inicializado pelo `id` do container (`mapa-pesquisa` / `mapa-editar`).
- O mapa é destruído/recriado ao trocar de cliente e em `onBeforeUnmount` (evita vazamento de instâncias).
- Em EditarView o pin é **arrastável** (exceto em modo somente leitura).

## Estilo

- Tailwind (`tailwind.config.js`): paleta `brand` (tons de azul), fonte `Segoe UI`, sombra `card`.
- CSS local em cada view (scoped). Classes utilitárias usadas em modais, badges, tabelas e formulários.

## PWA

- `vite.config.js` com `vite-plugin-pwa` (`registerType: 'autoUpdate'`, manifesto com `icon.svg`).
- `sw.js` e assets gerados no build para `dist/`; nginx evita cache imutável do service worker e cacheia assets com hash por 1 ano.