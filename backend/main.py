import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from limiter import limiter
from dotenv import load_dotenv
from database import engine, Base, AsyncSessionLocal
from routes.auth import router as auth_router
from routes.users import router as users_router
from routes.clientes import router as clientes_router
from routes.notificacoes import router as notificacoes_router
from routes.solicitacoes import router as solicitacoes_router
import storage
import seed as seed_module

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Segurança: exige JWT_SECRET forte (evita tokens forjados com segredo fraco)
    jwt_secret = os.getenv("JWT_SECRET") or ""
    if len(jwt_secret) < 32:
        raise RuntimeError(
            "JWT_SECRET ausente ou muito curto (mínimo 32 caracteres). "
            "Defina um segredo forte no ambiente antes de subir o backend."
        )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Migração leve para DBs existentes (create_all nao altera tabelas criadas).
        # asyncpg nao aceita varios comandos num prepared statement — roda um por vez.
        for ddl in [
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS empresa VARCHAR(10) NOT NULL DEFAULT 'AC'",
            "ALTER TABLE clientes ADD COLUMN IF NOT EXISTS alterado_por_empresa VARCHAR(10)",
            "ALTER TABLE cliente_alteracoes ADD COLUMN IF NOT EXISTS motorista_empresa VARCHAR(10) NOT NULL DEFAULT 'AC'",
            "ALTER TABLE cliente_alteracoes ADD COLUMN IF NOT EXISTS revisado_por_empresa VARCHAR(10)",
            "ALTER TABLE cliente_alteracoes ADD COLUMN IF NOT EXISTS revisado_por_user_id UUID",
            "ALTER TABLE cliente_alteracoes ADD COLUMN IF NOT EXISTS revisado_por_nome VARCHAR(200)",
            # Backfill: preenche empresa de registros antigos a partir dos users (idempotente)
            "UPDATE cliente_alteracoes ca SET motorista_empresa = u.empresa FROM users u "
            "WHERE ca.motorista_user_id = u.id AND ca.motorista_empresa IS NULL",
            "UPDATE cliente_alteracoes ca SET revisado_por_empresa = u.empresa FROM users u "
            "WHERE ca.revisado_por_user_id = u.id AND ca.revisado_por_empresa IS NULL",
            "UPDATE clientes c SET alterado_por_empresa = u.empresa FROM users u "
            "WHERE c.alterado_por_user_id = u.id AND c.alterado_por_empresa IS NULL",
            # Novo perfil 'solicitacoes': quem já cadastra (perm 'criar') vira o time de solicitações
            "UPDATE users SET permissions = array_append(permissions, 'solicitacoes') "
            "WHERE 'criar' = ANY(permissions) AND NOT 'solicitacoes' = ANY(permissions)",
            # Novo modelo de enderecos/contatos: migra o endereco flat existente
            # para a tabela cliente_enderecos (so quando ainda estiver vazia).
            "INSERT INTO cliente_enderecos "
            "(id, cliente_id, nome, ordem, cep, rua, numero, bairro, cidade, estado, "
            "latitude, longitude, ponto_referencia, observacao, created_at, updated_at) "
            "SELECT gen_random_uuid(), id, 'Endereço principal', 0, cep, rua, numero, bairro, "
            "cidade, estado, latitude, longitude, ponto_referencia, observacao, updated_at, updated_at "
            "FROM clientes WHERE NOT EXISTS (SELECT 1 FROM cliente_enderecos) "
            "AND (rua IS NOT NULL OR cep IS NOT NULL OR cidade IS NOT NULL "
            "OR bairro IS NOT NULL OR ponto_referencia IS NOT NULL)",
            # Migra telefone/pessoa de contato do cliente para contatos do endereco principal
            "INSERT INTO cliente_contatos (id, endereco_id, nome, telefone, created_at) "
            "SELECT gen_random_uuid(), e.id, c.pessoa_contato, c.telefone, e.created_at "
            "FROM clientes c JOIN cliente_enderecos e ON e.cliente_id = c.id AND e.ordem = 0 "
            "WHERE NOT EXISTS (SELECT 1 FROM cliente_contatos) "
            "AND (c.pessoa_contato IS NOT NULL OR c.telefone IS NOT NULL)",
        ]:
            await conn.execute(text(ddl))
    storage.ensure_bucket()
    # Carga inicial de dados fictícios (idempotente — só popula tabelas vazias)
    async with AsyncSessionLocal() as session:
        await seed_module.semear_banco(session)
    yield

app = FastAPI(
    title="App Motorista API",
    version="2.0.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in allowed_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth_router, prefix="/api")
app.include_router(users_router, prefix="/api")
app.include_router(clientes_router, prefix="/api")
# Sem prefixo: as rotas de notificação já trazem /api/... e o WebSocket é /ws/...
app.include_router(notificacoes_router)
app.include_router(solicitacoes_router)

@app.get("/health")
async def health():
    return {"status": "ok", "version": app.version}
