import logging
import os
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from database import get_db
from models import User
from auth import hash_password, verify_password, create_local_token, require_user
from limiter import limiter

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1)  # validação real é no banco


class SetupRequest(BaseModel):
    email: EmailStr
    name: str = Field(..., min_length=2)
    password: str = Field(..., min_length=8)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    name: str
    role: str
    empresa: str = "AC"
    permissions: list[str] = []


class MeResponse(BaseModel):
    email: str
    name: str
    role: str
    empresa: str = "AC"
    permissions: list[str] = []
    provider: str


@router.get("/me", response_model=MeResponse)
async def me(current: Any = Depends(require_user())):
    """Retorna dados do usuário autenticado — usado pelo frontend para obter o role real."""
    return MeResponse(
        email=current["email"],
        name=current["name"],
        role=current["role"],
        empresa=current.get("empresa") or "AC",
        permissions=current.get("permissions", []),
        provider=current["provider"]
    )


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(request: Request, body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if (
        not user
        or user.auth_provider != "local"
        or not user.password_hash
        or not verify_password(body.password, user.password_hash)
        or not user.is_active
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas"
        )

    token = create_local_token(str(user.id), user.email, user.name, user.role, user.permissions or [], user.empresa or "AC")
    return TokenResponse(access_token=token, name=user.name, role=user.role, empresa=user.empresa or "AC", permissions=user.permissions or [])


@router.post("/setup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def setup_first_admin(request: Request, body: SetupRequest, db: AsyncSession = Depends(get_db)):
    """Cria o primeiro admin. Desativado automaticamente após o primeiro uso.

    Só funciona com ALLOW_SETUP=1 no ambiente (default: desligado em produção).
    """
    if os.getenv("ALLOW_SETUP", "").strip() != "1":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Setup desativado. Defina ALLOW_SETUP=1 para habilitar."
        )

    count = await db.execute(select(func.count()).select_from(User))
    if count.scalar() > 0:
        logger.warning("[SETUP] Tentativa bloqueada de %s", request.client.host)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Setup já realizado"
        )

    admin = User(
        email=body.email,
        name=body.name,
        password_hash=hash_password(body.password),
        auth_provider="local",
        role="admin",
        empresa="AC",
        permissions=[],
        is_active=True
    )
    db.add(admin)
    await db.commit()
    await db.refresh(admin)

    token = create_local_token(str(admin.id), admin.email, admin.name, admin.role, empresa="AC")
    return TokenResponse(access_token=token, name=admin.name, role=admin.role, empresa="AC")
