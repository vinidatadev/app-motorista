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
from routes.tasks import router as tasks_router
from routes.auth import router as auth_router
from routes.users import router as users_router
from routes.clientes import router as clientes_router
import storage
import seed as seed_module

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Migração leve para DBs existentes (create_all nao altera tabelas criadas)
        await conn.execute(
            text(
                "ALTER TABLE cliente_alteracoes "
                "ADD COLUMN IF NOT EXISTS revisado_por_user_id UUID, "
                "ADD COLUMN IF NOT EXISTS revisado_por_nome VARCHAR(200)"
            )
        )
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

app.include_router(tasks_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(users_router, prefix="/api")
app.include_router(clientes_router, prefix="/api")

@app.get("/health")
async def health():
    return {"status": "ok", "version": app.version}
