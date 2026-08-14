import os
import httpx
import jwt
import bcrypt
import time
import logging
from datetime import datetime, timedelta, timezone
from cryptography.x509 import load_der_x509_certificate
from cryptography.hazmat.backends import default_backend
from base64 import b64decode
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

TENANT_ID    = os.getenv("AZURE_TENANT_ID")
CLIENT_ID    = os.getenv("AZURE_CLIENT_ID")
JWT_SECRET   = os.getenv("JWT_SECRET")          # segredo para tokens locais
JWT_EXPIRE_H = int(os.getenv("JWT_EXPIRE_H", "8"))

JWKS_URL = f"https://login.microsoftonline.com/{TENANT_ID}/discovery/v2.0/keys"

bearer_scheme = HTTPBearer()

# ---------- helpers de senha ----------

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())

# ---------- JWT local ----------

def create_local_token(user_id: str, email: str, name: str, role: str, permissions: list[str] | None = None, empresa: str = "AC") -> str:
    payload = {
        "sub": str(user_id),   # UUID real do usuário
        "email": email,
        "name": name,
        "role": role,
        "empresa": empresa,
        "permissions": permissions or [],
        "provider": "local",
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_H)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def _decode_local_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except Exception:
        return None

# ---------- Azure JWKS — cache com TTL de 1 hora ----------

_JWKS_TTL = 3600  # segundos
_jwks_cache: dict[str, tuple[object, float]] = {}

async def _get_azure_public_key(kid: str):
    entry = _jwks_cache.get(kid)
    if entry and time.time() - entry[1] < _JWKS_TTL:
        return entry[0]

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(JWKS_URL)
        resp.raise_for_status()
    for key in resp.json().get("keys", []):
        if key.get("kid") == kid:
            x5c = key.get("x5c", [])
            if x5c:
                cert = load_der_x509_certificate(b64decode(x5c[0]), default_backend())
                pub = cert.public_key()
                _jwks_cache[kid] = (pub, time.time())
                return pub
    return None

async def _decode_azure_token(token: str) -> dict | None:
    try:
        header = jwt.get_unverified_header(token)
        pub = await _get_azure_public_key(header["kid"])
        if not pub:
            return None
        return jwt.decode(
            token, pub, algorithms=["RS256"],
            audience=CLIENT_ID,
            issuer=f"https://login.microsoftonline.com/{TENANT_ID}/v2.0"
        )
    except Exception:
        return None

# ---------- Dependência principal ----------

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = None   # injetado via wrapper abaixo
) -> dict:
    raise NotImplementedError  # nunca chamado diretamente


def require_user(required_role: str | None = None):
    """
    Retorna uma dependência FastAPI que:
    1. Aceita token Azure (idToken) ou token local (JWT HS256)
    2. Verifica se o usuário existe e está ativo na tabela users
    3. Opcionalmente exige um role mínimo
    """
    from database import get_db  # import local evita circular

    async def _dependency(
        credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
        db: AsyncSession = Depends(get_db)
    ):
        from models import User  # import local evita circular

        token = credentials.credentials
        credentials_exc = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )

        # Tenta decodificar como token local primeiro (header "alg": "HS256")
        try:
            header = jwt.get_unverified_header(token)
            alg = header.get("alg", "")
        except Exception:
            raise credentials_exc

        if alg == "HS256":
            payload = _decode_local_token(token)
            if not payload:
                raise credentials_exc
            email    = payload.get("email")
            name     = payload.get("name", "")
            provider = "local"
        else:
            # Token Azure (RS256)
            payload = await _decode_azure_token(token)
            if not payload:
                raise credentials_exc
            email = (
                payload.get("preferred_username")
                or payload.get("email")
                or payload.get("upn")
            )
            name     = payload.get("name", "")
            provider = "microsoft"

        if not email:
            raise credentials_exc

        # Verifica usuário na tabela própria
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso não autorizado"
            )

        if required_role == "admin" and user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permissão insuficiente"
            )

        return {
            "user_id": str(user.id),   # UUID real
            "email": str(user.email),
            "name": user.name,
            "role": user.role,
            "empresa": user.empresa or "AC",
            "permissions": user.permissions or [],
            "provider": provider
        }

    return _dependency


def require_permission(*permissions: str):
    """
    Factory que retorna uma dependência FastAPI exigindo permissões granulares.
    Admin sempre passa. Users precisam ter TODAS as permissões listadas.

    Permissões válidas: 'visualizar', 'editar', 'criar', 'deletar', 'carga', 'exportar'
    """
    from database import get_db

    async def _dependency(
        credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
        db: AsyncSession = Depends(get_db)
    ):
        # Reaproveita a logica de require_user para autenticar
        from models import User
        token = credentials.credentials
        credentials_exc = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido ou expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
        try:
            header = jwt.get_unverified_header(token)
            alg = header.get("alg", "")
        except Exception:
            raise credentials_exc

        if alg == "HS256":
            payload = _decode_local_token(token)
            if not payload:
                raise credentials_exc
            email = payload.get("email")
            name = payload.get("name", "")
            provider = "local"
            token_perms = payload.get("permissions", [])
        else:
            payload = await _decode_azure_token(token)
            if not payload:
                raise credentials_exc
            email = payload.get("preferred_username") or payload.get("email") or payload.get("upn")
            name = payload.get("name", "")
            provider = "microsoft"
            token_perms = []

        if not email:
            raise credentials_exc

        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso nao autorizado")

        user_info = {
            "user_id": str(user.id),
            "email": str(user.email),
            "name": user.name,
            "role": user.role,
            "empresa": user.empresa or "AC",
            "permissions": user.permissions or [],
            "provider": provider
        }

        # Admin ignora permissoes granulares
        if user_info["role"] == "admin":
            return user_info

        user_perms = set(user_info.get("permissions", []))
        required = set(permissions)
        if not required.issubset(user_perms):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permissão insuficiente. Requer: {', '.join(permissions)}"
            )
        return user_info
    return _dependency

    return _dependency
