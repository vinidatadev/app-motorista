"""Gerenciador de conexões WebSocket para notificações em tempo real.

Cada usuário autenticado mantém uma (ou mais) conexões abertas em
/ws/notificacoes. Quando algo relevante acontece (nova submissão para aprovar,
aprovação/recusa de uma alteração), o backend grava a Notificacao no banco e
faz push pela conexão — assim o sino do frontend atualiza sem refresh.
"""
import asyncio
from fastapi import WebSocket
from models import Notificacao


class ConnectionManager:
    """Mapa user_id -> conjunto de WebSockets conectados."""

    def __init__(self):
        self._connections: dict[str, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, user_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.setdefault(user_id, set()).add(websocket)

    async def disconnect(self, user_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            sockets = self._connections.get(user_id)
            if not sockets:
                return
            sockets.discard(websocket)
            if not sockets:
                self._connections.pop(user_id, None)

    async def send_to_user(self, user_id: str, data: dict) -> None:
        """Envia JSON para todas as conexões do usuário (ignora falhas)."""
        sockets = list(self._connections.get(user_id, set()))
        for ws in sockets:
            try:
                await ws.send_json(data)
            except Exception:
                await self.disconnect(user_id, ws)

    def usuarios_conectados(self) -> int:
        return len(self._connections)

    def conexoes_ativas(self) -> int:
        return sum(len(s) for s in self._connections.values())


manager = ConnectionManager()


def notificacao_para_dict(n: Notificacao) -> dict:
    """Serializa uma Notificacao para o payload do WebSocket / REST."""
    return {
        "id": str(n.id),
        "tipo": n.tipo,
        "titulo": n.titulo,
        "mensagem": n.mensagem,
        "link": n.link,
        "cliente_id": str(n.cliente_id) if n.cliente_id else None,
        "alteracao_id": str(n.alteracao_id) if n.alteracao_id else None,
        "lida": n.lida,
        "created_at": n.created_at.isoformat() if n.created_at else None,
    }


def criar_notificacao(
    db,
    user_id,
    *,
    tipo: str,
    titulo: str,
    mensagem: str | None = None,
    link: str | None = None,
    cliente_id=None,
    alteracao_id=None,
) -> Notificacao:
    """Cria a linha de Notificacao (nao faz commit — o chamador controla a transacao)."""
    n = Notificacao(
        user_id=user_id,
        tipo=tipo,
        titulo=titulo,
        mensagem=mensagem,
        link=link,
        cliente_id=cliente_id,
        alteracao_id=alteracao_id,
    )
    db.add(n)
    return n


async def enviar_notificacao(user_id, n: Notificacao) -> None:
    """Push da notificacao ja persistida para o usuario (se estiver online)."""
    payload = {"event": "nova_notificacao", "notificacao": notificacao_para_dict(n)}
    await manager.send_to_user(str(user_id), payload)