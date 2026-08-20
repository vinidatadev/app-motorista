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

    # Cria tabelas se não existirem (rápido, não altera tabelas existentes)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Garante que o bucket existe
    storage.ensure_bucket()
    
    # Seed apenas se SEED_DEMO=1 (opcional, não roda em produção)
    if os.getenv("SEED_DEMO") == "1":
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
app.include_router(solicitacoes_router, prefix="/api")

# Health check endpoint para Container Apps
@app.get("/health")
async def health_check():
    """Endpoint de health check para o Azure Container Apps"""
    return {"status": "healthy"}
app.include_router(solicitacoes_router)

@app.get("/health")
async def health():
    return {"status": "ok", "version": app.version}
