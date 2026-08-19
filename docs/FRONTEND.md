# Frontend — Vue 3 + Vite + Tailwind

## Visão geral

SPA em Vue 3 (Composition API) com Vue Router, Tailwind CSS e Leaflet para mapas. Build via Vite (com plugin PWA). O frontend roda servido por nginx (build estático) ou pelo servidor de dev do Vite (porta 5173).

## Bootstrap e estrutura

- `src/main.js` — cria o app, instala o router e monta em `#app`.
- `src/App.vue` — layout global: navbar com links condicionados a permissões, **sino de notificações** (badge, dropdown, som e navegação ao clicar), badge de empresa, avatar, botão sair e rodapé com a versão (`__APP_VERSION__` injetada pelo Vite).
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
| `/solicitacoes` | solicitacoes | autenticado (time vê todas; demais veem as suas) |
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
  - `api.notificacoes` — `listar`, `marcarLida`, `marcarTodasLidas`
  - `api.solicitacoes` — `listar`, `criar`, `status`

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

### `src/composables/useNotificacoes.js`
Estado singleton das notificações:
- `notificacoes` (`ref`), `naoLidas` (`computed`).
- `iniciarNotificacoes()` — conecta o **WebSocket** (`/ws/notificacoes?token=JWT`), carrega a lista e inicia um **refresh periódico** (45 s).
- `pararNotificacoes()` — fecha o WebSocket e limpa o estado (chamado no logout).
- `marcarLida(n)` / `marcarTodasLidas()`.
- **Som**: ao chegar notificação toca um "ding-dong" (Web Audio). O `AudioContext` é criado/retomado no primeiro gesto do usuário (política de autoplay dos navegadores).
- Reconexão automática com backoff se o WebSocket cair.

## Views

### LoginView
Formulário e-mail/senha → `api.auth.login` → `loginComToken` → redireciona para `route.query.redirect` ou `/clientes/pesquisa`.

### PesquisaView
- Filtros independentes: UF, cidade, busca por nome (`datalist`).
- Painel de detalhe readonly: badges de estado/cidade, status de "atualização pendente", **todos os endereços** (cada um com CEP/rua/número/bairro/cidade/UF, coordenadas, ponto de referência e **contatos**), **fotos** (links), **mapa preview** (Leaflet) e **endereço completo** com links de navegação (Waze/Google/OSM) por endereço.
- Ações: Editar (se `editar`), Excluir (se `deletar`), Exportar Excel (se `exportar`).
- **Solicitações:** botão "📋 Não encontrei o cliente — abrir solicitação" (quando a busca não acha nada) e "📞 Solicitar contato atualizado" (quando o cliente existe), ambos com modal de descrição.
- Seleção via URL `?cliente=ID` ou `?codigo=C100` (usado ao clicar na notificação de solicitação concluída).

### EditarView
- Seleção do cliente (UF → cidade → busca), com pré-seleção via `?cliente=id`.
- **Abas de endereços**: o cliente pode ter N lojas/endereços; cada aba tem seu próprio formulário, mapa e lista de **contatos** (vários por endereço). Botões "+ Adicionar" e "× Remover".
- Mapa interativo por endereço ativo:
  - Arrastar pin → atualiza lat/lng → **reverse geocoding** (debounce 600 ms) preenche rua/numero/cep/cidade/estado.
  - Botão "Pegar Localização Atual" (Geolocation API).
  - Botão "Reposicionar pin no endereço digitado" (forward geocoding).
  - **Detecção de divergência** número digitado × número do pin → modal de confirmação antes de salvar.
- Fotos: upload da galeria ou câmera (`capture="environment"`), visualização e exclusão.
- Bloqueio em modo `somenteLeitura` quando cliente está `atualizando` (alteração pendente).
- Salvar → `PUT /api/clientes/{id}` (envia a lista completa de `enderecos`); se o usuário não tem `aprovar`, o backend cria a submissão e o banner informa "Submissão enviada para aprovação".

### CadastrarView
- Formulário de criação com máscara de telefone, validação de **coordenadas** (lat/lng dentro da faixa), **endereços dinâmicos** (add/remove) e **contatos por endereço**.
- Pré-preenchimento via `?nome=&codigo=&obs=` (quando o time clica em "Cadastrar cliente" a partir de uma solicitação concluída). Redireciona para `?retorno=` após sucesso (default: pesquisa).

### CargaView
- Download de **template**, upload por clique/arrastar e soltar, preview (cards de resumo novos × alterados com diff `de → para` e endereços), e confirmação da aplicação.
- Exibe contadores de resultado ao aplicar.
- Template com as colunas do novo formato (uma linha por endereço + contatos).

### AprovacoesView
- Filtros por status (pendente/aprovado/editada/recusada/todas, com contagens) e por empresa do solicitante (AC/SIN).
- Card por submissão: status, autor, data, diff **atual × proposto** (inclui endereços e contatos, destacando alterações), snapshot de já revisadas.
- Ações para pendentes: **Editar e aprovar** (modal com formulário), **Aprovar**, **Recusar** (modal com motivo).

### SolicitacoesView
- Lista de solicitações com filtros por status (contagens) e tipo (cadastro/contato).
- **Time** (perm `solicitacoes` ou admin): vê todas e pode **Iniciar atendimento**, **Concluir** (com nota e código do cliente cadastrado) ou **Recusar** (com motivo). Botões "➕ Cadastrar cliente" e "✏️ Editar cliente" aparecem logo que a solicitação chega.
- **Usuários comuns**: veem somente as próprias solicitações e o status.

### AdminView
- CRUD de usuários: formulário com nome, e-mail, role, empresa, senha, ativo e **checkboxes de permissões granulares** (incluindo `solicitacoes`).
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