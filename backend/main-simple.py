"""Main simplificado para troubleshooting - sem lifespan"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    title="App Motorista API - Simple",
    version="2.0.0",
    docs_url=None,
    redoc_url=None
)

allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in allowed_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
)

@app.get("/health")
async def health_check():
    """Endpoint de health check"""
    return {"status": "healthy", "message": "Backend rodando sem banco"}

@app.get("/")
async def root():
    return {"message": "App Motorista API - Modo simples"}

@app.get("/test-db")
async def test_db():
    """Testa conexão com o banco"""
    try:
        from database import engine
        from sqlalchemy import text
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            row = result.scalar()
        return {"status": "ok", "db_test": row}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/test-storage")
async def test_storage():
    """Testa conexão com o storage"""
    try:
        import storage
        storage.ensure_bucket()
        return {"status": "ok", "storage": "connected"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
