# Análise de Erros e Recomendações

Análise feita sobre a base atual (branch `main`, commit `68b727c`). A build do frontend (`npm run build`) e a compilação dos módulos Python (`py_compile`) passam sem erros — **o projeto compila**. Os problemas abaixo são de lógica, configuração, consistência e boas práticas.

---

## 🔴 1. Bugs funcionais (corrigir primeiro)

### 1.1 — Template de carga baixado é CSV, mas o upload exige `.xlsx`
**Arquivo:** `src/views/CargaView.vue` (função `baixarTemplate`)

O botão "Baixar template .xlsx" gera um arquivo **CSV** (`template_clientes.csv`), mas o input de upload só aceita `.xlsx,.xls` e o backend (`clientes.py`) rejeita qualquer arquivo que não termine em `.xlsx`. Ou seja: o template baixado **não pode ser usado** para fazer a carga.

**Correção sugerida:** gerar um `.xlsx` de verdade com `xlsx`/`exceljs` no front, **ou** aceitar também CSV no backend (`aplicar_carga`/`preview_carga`) e renomear o botão para "Baixar template CSV".

### 1.2 — Fotos não carregam no navegador em deploy via docker-compose
**Arquivo:** `backend/storage.py` (`presign_url` + `_client`)

O bucket é privado e a API devolve **presigned URLs** para exibir as fotos. Porém `_client()` assina usando `MINIO_ENDPOINT` (default `minio:9000` — hostname **interno** do docker). As URLs geradas são `http://minio:9000/clientes/...?...`, e o navegador do usuário **não resolve** o hostname `minio`. Resultado: as fotos quebram (404/DNS) em qualquer instalação com docker-compose.

**Correção sugerida:** assinar as URLs com o host **público** (`MINIO_PUBLIC_URL`, ex. `http://localhost:9000`). Ex.: criar um segundo cliente boto3 (ou parâmetro `endpoint_url` público) usado apenas em `presign_url`, mantendo o endpoint interno para as operações de leitura/escrita.

### 1.3 — CSS inválido remove a sombra dos cards
**Arquivos:** `src/views/PesquisaView.vue:443` e `src/views/EditarView.vue:841`

```css
.card { ... box-shadow: card; ... }
```

`box-shadow: card` **não é CSS válido** (falta `var(--...)` ou o valor real da sombra). O browser descarta a declaração → os cards ficam sem sombra. O Tailwind define `boxShadow.card` na config, mas ele só vale via classes utilitárias (`shadow-card`), não como valor literal de CSS.

**Correção sugerida:** usar o valor real, ex.:
```css
box-shadow: 0 10px 30px -12px rgba(20, 40, 90, 0.25);
```
ou a classe `shadow-card` do Tailwind.

---

## 🟠 2. Segurança / configuração

### 2.1 — Chaves de API em `.env` (gitignored, mas sensíveis)
`backend/.env` e `.env` contêm chaves reais de **OpenCage** e **Mapbox**. Elas estão corretamente no `.gitignore` e **não** estão no repositório (verificado via `git status`). Ainda assim:
- Como são variáveis `VITE_*`, as chaves do frontend ficam **embutidas no bundle** e visíveis a qualquer um que abra o DevTools.
- **Recomendação:** rotacionar as chaves periodicamente; considerar proxy de geocoding pelo backend (hoje o reverse geocoding acontece direto no browser).

### 2.2 — CSP de produção com domínio fixo
**Arquivo:** `nginx.conf:28`

A CSP tem `connect-src ... https://backend.devlopplay.site` **hardcoded**. Implantado em outro domínio, toda chamada à API será bloqueada pelo navegador. Use variável/template no deploy ou documente a necessidade de editar este valor.

### 2.3 — Rate limiting confia no header `X-Forwarded-For` sem validação
**Arquivo:** `backend/limiter.py`

O `key_func` usa o primeiro valor de `X-Forwarded-For`. Se o nginx/proxy reverso não estiver configurado para **substituir/confiar** apenas em proxies conhecidos (`real_ip`/`proxy_set_header`), um atacante pode forjar o header e contornar os limites. Em produção, garanta que o nginx sobrescreva `X-Forwarded-For` e não aceite o valor do cliente.

### 2.4 — Credenciais MinIO padrão
**Arquivo:** `backend/storage.py` + `docker-compose.yml`

Defaults `minioadmin/minioadmin` com warning em log. Em produção, definir `MINIO_ACCESS_KEY`/`MINIO_SECRET_KEY` (e `MINIO_USER`/`MINIO_PASSWORD` no compose).

### 2.5 — Senhas do seed são fracas (só dev)
**Arquivo:** `backend/seed.py` — `admin123`, `vis123`, etc. São intencionais para teste local e só ativadas com `SEED_DEMO=1`, mas vale lembrar de nunca subir produção com esse flag ligado.

---

## 🟡 3. Código morto / redundâncias

| # | Local | Problema |
|---|---|---|
| 3.1 | `backend/auth.py:98-102` | Função `get_current_user` é um **stub que lança `NotImplementedError`** e nunca é usada (as dependências reais são `require_user`/`require_permission`). Remover para evitar que alguém a use por engano. |
| 3.2 | `backend/auth.py:261-263` | `require_permission` tem **`return _dependency` duplicado** (o segundo é inalcançável). |
| 3.3 | `backend/auth.py:220,228` | Variável `token_perms` é atribuída e **nunca usada** em `require_permission`. |
| 3.4 | `backend/auth.py` | `require_user` e `require_permission` **duplicam toda a lógica** de decodificação/validação de token. Extrair uma função comum (`_autenticar(token, db)`) reduz risco de divergência futura. |
| 3.5 | `src/App.vue:59-60` | `carregarSessao()` é chamado **duas vezes seguidas** no `onMounted`. |
| 3.6 | `src/views/CargaView.vue:119` | Import não utilizado: `temPermissao`. |
| 3.7 | `src/authConfig.js` | Arquivo inteiro é **configuração morta** (`msalConfig`/`loginRequest`) — nada o importa. O login Microsoft não está implementado no front, embora o backend aceite tokens Azure. Decidir: implementar MSAL ou remover o arquivo e os placeholders `VITE_AZURE_*`. |
| 3.8 | `src/api.js` | `api.clientes.alteracoes.historico` está definido mas **não é usado** em nenhuma view. |
| 3.9 | `src/router/index.js:22` | Flag `permSincronizadas` (nível de módulo) **nunca é resetada no logout**. Funciona porque `loginComToken` resincroniza, mas é frágil em fluxos de troca de usuário na mesma aba. |
| 3.10 | `docs` do backend | O docstring de `require_permission` não lista a permissão `aprovar`, mas ela existe em `users.PERMISSOES_VALIDAS` e na tela Admin. |

---

## 🟢 4. Inconsistências e melhorias

### 4.1 — Limite de linhas só validado no `aplicar`, não no `preview`
**Arquivo:** `backend/routes/clientes.py`

`preview_carga` não valida `MAX_LINHAS_CARGA` (2.000), mas `aplicar_carga` valida. O usuário pode ver um preview gigante e falhar ao aplicar. Validar também no preview.

### 4.2 — `constr` (Pydantic v2) deprecado
**Arquivo:** `backend/routes/clientes.py`

`constr(...)` funciona, mas é **deprecated** no Pydantic v2 (gera warning). Preferir `Annotated[str, StringConstraints(...)]`. Vale também pinar o Pydantic no `requirements.txt` (hoje vem implicitamente via FastAPI 0.111).

### 4.3 — Carga altera cliente sem limpar pendências
Se um cliente está `status_endereco='atualizando'` (submissão pendente) e um admin executa `aplicar_carga` sobre o mesmo `codigo`, o status permanece `atualizando` e a submissão pendente fica órfã. Considerar: bloquear ou limpar pendências ao atualizar via carga.

### 4.4 — N+1 no carregamento de fotos
`listar_clientes` faz 1 query de fotos por cliente (o próprio código comenta "otimizar depois"). Para listas grandes, carregar fotos em lote (`WHERE cliente_id IN (...)`) e montar um mapa id→fotos.

### 4.5 — Listas sem paginação
`GET /api/clientes`, `GET /api/alteracoes` e `GET /api/users/` carregam tudo. Em escala, paginar.

### 4.6 — Sem testes automatizados
Não há testes (backend nem frontend) nem script de lint/typecheck no `package.json`. Adicionar pelo menos: `pytest` para auth/permissões/fluxo de aprovação/carga e um smoke test de build.

### 4.7 — `AdminView` CSS `col2 { grid-column: span 1; }`
A classe `.col2` do formulário de usuários não expande nada (`span 1`). Provavelmente um resquício de layout — remover a classe ou o estilo.

### 4.8 — Variáveis `token_perms` / payload não reaproveitadas
O payload decodificado do token local contém `permissions`, mas `require_permission` re-lê do banco (correto). O campo `token_perms` no token poderia ser removido para reduzir o tamanho do JWT (a fonte de verdade é o banco).

---

## ✅ 5. Pontos fortes verificados

- Autenticação consistente: token JWT validado, usuário relido do banco a cada request (mudança de permissão vale na hora).
- `JWT_SECRET` com verificação de tamanho mínimo no startup.
- Rate limiting por IP em endpoints sensíveis.
- Validação de imagem por **magic bytes** e limite de 5 MB.
- Bucket MinIO privado + presigned URLs (exceto pelo problema 1.2 de hostname).
- CORS restrito; headers de segurança e HSTS no nginx de produção.
- Backend roda como usuário não-root no Dockerfile.
- Migrações leves idempotentes no startup (`IF NOT EXISTS` + backfill de empresa).
- Frontend com guard de rotas por permissão e sincronização de permissões com o backend.
- Código comentado em português e bem organizado por responsabilidade.

---

## Plano de ação sugerido

1. **Corrigir bugs funcionais** (1.1, 1.2, 1.3) — impacto direto na experiência do usuário.
2. **Limpar código morto** (seção 3) — baixo risco, melhora manutenibilidade.
3. **Endurecer produção** (2.1–2.4): rotacionar chaves, parametrizar CSP, credenciais MinIO fortes, `real_ip` no nginx.
4. **Adicionar testes** básicos para os fluxos críticos (auth, permissões, aprovação, carga).
5. **Otimizar** N+1 de fotos e paginar listas quando o volume crescer.