"""Notificações: listagem, marcação de leitura e WebSocket em tempo real.

REST (prefixo /api):
  GET  /api/notificacoes             -> notificações do usuário logado
  POST /api/notificacoes/ler-todas   -> marca todas como lidas
  POST /api/notificacoes/{id}/ler    -> marca uma como lida

WebSocket:
  /ws/notificacoes?token=<JWT>       -> recebe push de novas notificações
"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

import jwt

from database import get_db, AsyncSessionLocal
from auth import require_user, _decode_local_token, _decode_azure_token
from models import User, Notificacao
from notify import manager, notificacao_para_dict

router = APIRouter(tags=["notificacoes"])

MAX_NOTIFICACOES = 60


async def _autenticar_ws(token: str, db: AsyncSession) -> User | None:
    """Valida o JWT (local ou Azure) e devolve o usuário ativo, ou None."""
    if not token:
        return None
    try:
        header = jwt.get_unverified_header(token)
        alg = header.get("alg", "")
    except Exception:
        return None

    if alg == "HS256":
        payload = _decode_local_token(token)
    else:
        payload = await _decode_azure_token(token)
    if not payload:
        return None

    email = (
        payload.get("email")
        or payload.get("preferred_username")
        or payload.get("upn")
    )
    if not email:
        return None

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        return None
    return user


def _notif_out(n: Notificacao) -> dict:
    return notificacao_para_dict(n)


@router.get("/api/notificacoes")
async def listar_notificacoes(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_user()),
):
    """Lista as notificações do usuário logado (mais recentes primeiro)."""
    result = await db.execute(
        select(Notificacao)
        .where(Notificacao.user_id == UUID(user["user_id"]))
        .order_by(Notificacao.created_at.desc())
        .limit(MAX_NOTIFICACOES)
    )
    notificacoes = result.scalars().all()

    nao_lidas = (
        await db.execute(
            select(func.count())
            .select_from(Notificacao)
            .where(
                Notificacao.user_id == UUID(user["user_id"]),
                Notificacao.lida.is_(False),
            )
        )
    ).scalar() or 0

    return {
        "nao_lidas": nao_lidas,
        "notificacoes": [_notif_out(n) for n in notificacoes],
    }


@router.post("/api/notificacoes/ler-todas")
async def marcar_todas_lidas(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_user()),
):
    await db.execute(
        update(Notificacao)
        .where(
            Notificacao.user_id == UUID(user["user_id"]),
            Notificacao.lida.is_(False),
        )
        .values(lida=True)
    )
    await db.commit()
    return {"ok": True}


@router.post("/api/notificacoes/{notificacao_id}/ler")
async def marcar_lida(
    notificacao_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_user()),
):
    n = await db.get(Notificacao, notificacao_id)
    if not n or str(n.user_id) != user["user_id"]:
        raise HTTPException(status_code=404, detail="Notificação não encontrada")
    n.lida = True
    await db.commit()
    return {"ok": True}


@router.websocket("/ws/notificacoes")
async def ws_notificacoes(websocket: WebSocket, token: str = Query(default="")):
    """Conexão WebSocket autenticada por token JWT (query ?token=...)."""
    async with AsyncSessionLocal() as db:
        user = await _autenticar_ws(token, db)
        if not user:
            await websocket.close(code=4401)
            return

        await websocket.accept()
        user_id = str(user.id)

        # Envia estado inicial (contagem de não lidas) ao conectar
        try:
            nao_lidas = (
                await db.execute(
                    select(func.count())
                    .select_from(Notificacao)
                    .where(
                        Notificacao.user_id == user.id,
                        Notificacao.lida.is_(False),
                    )
                )
            ).scalar() or 0
        except Exception:
            nao_lidas = 0

        await manager.connect(user_id, websocket)
        try:
            await websocket.send_json({"event": "init", "nao_lidas": nao_lidas})
            # Mantém a conexão viva; ignora mensagens do cliente (pings).
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        except Exception:
            pass
        finally:
            await manager.disconnect(user_id, websocket)