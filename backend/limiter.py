from fastapi import Request
from slowapi import Limiter


def _client_ip(request: Request) -> str:
    """IP real do cliente para rate limiting.

    Atrás de um proxy reverso (nginx/EasyPanel), o IP real chega no primeiro
    valor do header X-Forwarded-For. Sem proxy, usa o endereço direto.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


limiter = Limiter(key_func=_client_ip)