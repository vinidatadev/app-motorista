"""Solicitações abertas pelos usuários (cadastrar cliente novo / atualizar contato).

REST (prefixo /api):
  POST /api/solicitacoes            -> abre uma solicitação (qualquer usuário logado)
  GET  /api/solicitacoes            -> lista (time vê todas; demais veem só as suas)
  POST /api/solicitacoes/{id}/status -> time muda o status (concluir/recusar)

Fluxo de notificação:
  - ao abrir -> notifica o time (permissão 'solicitacoes' + admin)
  - ao concluir/recusar -> notifica o solicitante
"""
from uuid import UUID
from datetime import datetime, timezone
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, constr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Solicitacao, User, Cliente
from auth import require_user, require_permission
from limiter import limiter
from notify import criar_notificacao, enviar_notificacao

router = APIRouter(tags=["solicitacoes"])

TIPOS_VALIDOS = {"novo_cliente", "atualizar_contato"}
STATUS_VALIDOS = {"aberta", "em_andamento", "concluida", "recusada"}

LABEL_TIPO = {
    "novo_cliente": "Cadastrar cliente novo",
    "atualizar_contato": "Atualizar contato",
}


class SolicitacaoCreate(BaseModel):
    tipo: str
    cliente_codigo: constr(strip_whitespace=True, max_length=50) | None = None
    cliente_id: UUID | None = None
    cliente_nome: constr(strip_whitespace=True, max_length=150) = Field(..., min_length=1)
    descricao: constr(strip_whitespace=True, max_length=5000) | None = None


class StatusBody(BaseModel):
    status: str
    observacao_resolucao: constr(strip_whitespace=True, max_length=2000) | None = None
    # Código do cliente cadastrado (usado ao concluir uma solicitação de novo_cliente)
    cliente_codigo: constr(strip_whitespace=True, max_length=50) | None = None


def _eh_equipe(user: dict) -> bool:
    return user["role"] == "admin" or "solicitacoes" in (user.get("permissions") or [])


def _solicitacao_out(s: Solicitacao) -> dict:
    return {
        "id": str(s.id),
        "tipo": s.tipo,
        "tipo_label": LABEL_TIPO.get(s.tipo, s.tipo),
        "status": s.status,
        "solicitante_user_id": str(s.solicitante_user_id),
        "solicitante_nome": s.solicitante_nome,
        "solicitante_empresa": s.solicitante_empresa or "AC",
        "cliente_id": str(s.cliente_id) if s.cliente_id else None,
        "cliente_codigo": s.cliente_codigo,
        "cliente_nome": s.cliente_nome,
        "descricao": s.descricao,
        "resolvido_por_user_id": str(s.resolvido_por_user_id) if s.resolvido_por_user_id else None,
        "resolvido_por_nome": s.resolvido_por_nome,
        "resolvido_por_empresa": s.resolvido_por_empresa,
        "observacao_resolucao": s.observacao_resolucao,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "resolvido_at": s.resolvido_at.isoformat() if s.resolvido_at else None,
    }


@router.post("/api/solicitacoes", status_code=201)
@limiter.limit("20/minute")
async def criar_solicitacao(
    request: Request,
    body: SolicitacaoCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_user()),
):
    if body.tipo not in TIPOS_VALIDOS:
        raise HTTPException(status_code=422, detail="Tipo de solicitação inválido")
    if body.tipo == "atualizar_contato" and not body.cliente_id:
        raise HTTPException(
            status_code=422,
            detail="Para solicitar contato atualizado, informe o cliente",
        )

    s = Solicitacao(
        tipo=body.tipo,
        status="aberta",
        solicitante_user_id=UUID(user["user_id"]),
        solicitante_nome=user["name"],
        solicitante_empresa=user.get("empresa") or "AC",
        cliente_id=body.cliente_id,
        cliente_codigo=body.cliente_codigo,
        cliente_nome=body.cliente_nome,
        descricao=body.descricao,
    )
    db.add(s)
    await db.flush()

    # Notifica o time de solicitações (permissão 'solicitacoes' + admins)
    result = await db.execute(select(User).where(User.is_active == True))
    alvos: list[tuple[User, Any]] = []
    for u in result.scalars().all():
        if u.role == "admin" or "solicitacoes" in (u.permissions or []):
            n = criar_notificacao(
                db,
                u.id,
                tipo="nova_solicitacao",
                titulo="Nova solicitação",
                mensagem=(
                    f"{user['name']} ({user.get('empresa') or 'AC'}) pediu: "
                    f"{LABEL_TIPO.get(body.tipo, body.tipo)} — {body.cliente_nome}."
                ),
                link="/solicitacoes",
                cliente_id=body.cliente_id,
            )
            alvos.append((u, n))

    await db.commit()
    for u, n in alvos:
        await enviar_notificacao(u.id, n)

    return _solicitacao_out(s)


@router.get("/api/solicitacoes")
async def listar_solicitacoes(
    status_filter: str | None = Query(default=None, alias="status"),
    tipo: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_user()),
):
    """Lista solicitações. O time (perm 'solicitacoes' ou admin) vê todas;
    os demais usuários veem apenas as que eles mesmos abriram."""
    eh_equipe = _eh_equipe(user)
    stmt = select(Solicitacao).order_by(Solicitacao.created_at.desc())
    if not eh_equipe:
        stmt = stmt.where(Solicitacao.solicitante_user_id == UUID(user["user_id"]))
    if status_filter:
        stmt = stmt.where(Solicitacao.status == status_filter)
    if tipo:
        stmt = stmt.where(Solicitacao.tipo == tipo)

    result = await db.execute(stmt)
    return {
        "eh_equipe": eh_equipe,
        "solicitacoes": [_solicitacao_out(s) for s in result.scalars().all()],
    }


@router.post("/api/solicitacoes/{solicitacao_id}/status")
async def atualizar_status_solicitacao(
    solicitacao_id: UUID,
    body: StatusBody,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_permission("solicitacoes")),
):
    """Time altera o status da solicitação (em_andamento/concluida/recusada).

    Ao concluir ou recusar, o solicitante recebe notificação de volta."""
    if body.status not in STATUS_VALIDOS:
        raise HTTPException(status_code=422, detail="Status inválido")

    s = await db.get(Solicitacao, solicitacao_id)
    if not s:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada")
    if s.status in ("concluida", "recusada"):
        raise HTTPException(status_code=400, detail=f"Solicitação já {s.status}")

    s.status = body.status
    s.observacao_resolucao = body.observacao_resolucao

    # Ao concluir um pedido de cadastro, tenta vincular o cliente pelo código
    # informado pelo time (assim a notificação ao motorista abre o cliente).
    if body.status == "concluida" and body.cliente_codigo:
        cod = body.cliente_codigo.strip()
        if cod:
            cli = (await db.execute(select(Cliente).where(Cliente.codigo == cod))).scalar_one_or_none()
            if cli:
                s.cliente_id = cli.id
                s.cliente_codigo = cli.codigo

    notif = None
    if body.status in ("concluida", "recusada"):
        s.resolvido_por_user_id = UUID(user["user_id"])
        s.resolvido_por_nome = user["name"]
        s.resolvido_por_empresa = user.get("empresa") or "AC"
        s.resolvido_at = datetime.now(timezone.utc)

        concluida = body.status == "concluida"
        # Notificação do solicitante abre o cliente na Pesquisa (e não a tela
        # de Solicitações, que é da equipe).
        if s.cliente_id:
            link = f"/clientes/pesquisa?cliente={s.cliente_id}"
        elif s.cliente_codigo:
            link = f"/clientes/pesquisa?codigo={s.cliente_codigo}"
        else:
            link = "/clientes/pesquisa"

        detalhe = f" ({s.cliente_codigo})" if s.cliente_codigo else ""
        notif = criar_notificacao(
            db,
            s.solicitante_user_id,
            tipo="solicitacao_concluida" if concluida else "solicitacao_recusada",
            titulo="Sua solicitação foi concluída" if concluida else "Sua solicitação foi recusada",
            mensagem=(
                f"A solicitação de {LABEL_TIPO.get(s.tipo, s.tipo)} de '{s.cliente_nome}' "
                f"foi {('concluída' if concluida else 'recusada')} por {user['name']}{detalhe}."
            ),
            link=link,
            cliente_id=s.cliente_id,
        )

    await db.commit()
    if notif is not None:
        await enviar_notificacao(s.solicitante_user_id, notif)

    return _solicitacao_out(s)