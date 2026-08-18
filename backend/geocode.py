"""Geocoding direto — OpenCage (produção) com fallback Nominatim (dev).

OpenCage: 2.500 req/dia grátis — evita rate-limit do Nominatim em carga.
Se OPENCAGE_KEY não estiver definida, cai para Nominatim (ambiente dev local).
"""
import os
import httpx
import logging

logger = logging.getLogger(__name__)

OPENCAGE_ENDPOINT = "https://api.opencagedata.com/geocode/v1/json"
OPENCAGE_KEY = os.getenv("OPENCAGE_KEY", "").strip()

NOMINATIM_SEARCH = "https://nominatim.openstreetmap.org/search"

# Mapeia nome de estado (Nominatim) -> sigla UF, se precisar normalizar
UF_POR_NOME = {
    'Acre':'AC','Alagoas':'AL','Amapa':'AP','Amazonas':'AM','Bahia':'BA','Ceara':'CE',
    'Distrito Federal':'DF','Espirito Santo':'ES','Goias':'GO','Maranhao':'MA',
    'Mato Grosso':'MT','Mato Grosso do Sul':'MS','Minas Gerais':'MG','Para':'PA',
    'Paraiba':'PB','Parana':'PR','Pernambuco':'PE','Piaui':'PI','Rio de Janeiro':'RJ',
    'Rio Grande do Norte':'RN','Rio Grande do Sul':'RS','Rondonia':'RO','Roraima':'RR',
    'Santa Catarina':'SC','Sao Paulo':'SP','Sergipe':'SE','Tocantins':'TO',
}


def _s(v):
    """Normaliza valor para string nao vazia, ou None (aceita numeros/None)."""
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


def montar_endereco(rua=None, numero=None, bairro=None, cidade=None, estado=None, cep=None) -> str:
    """Monta string de endereco para query Nominatim.

    Nominatim e' sensivel a pontuacao — usamos espacos simples, sem hifens
    juntando cidade/estado (ex: 'Fortaleza CE' em vez de 'Fortaleza-CE').
    """
    rua = _s(rua)
    numero = _s(numero)
    bairro = _s(bairro)
    cidade = _s(cidade)
    estado = _s(estado)
    cep = _s(cep)
    partes = []
    if rua or numero:
        partes.append(", ".join(x for x in [rua, numero] if x))
    if bairro:
        partes.append(bairro)
    if cidade:
        partes.append(cidade)
    if estado:
        partes.append(estado)
    if cep:
        partes.append(cep)
    partes.append("Brasil")
    return ", ".join(partes)


async def _geocode_opencage(query: str) -> tuple[float, float] | None:
    """Forward geocoding via OpenCage: endereco textual -> (lat, lng)."""
    try:
        async with httpx.AsyncClient(timeout=10, headers={"Accept": "application/json"}) as client:
            resp = await client.get(
                OPENCAGE_ENDPOINT,
                params={
                    "q": query,
                    "key": OPENCAGE_KEY,
                    "language": "pt",
                    "countrycode": "br",
                    "limit": "1",
                    "no_annotations": "1",
                },
            )
            if resp.status_code != 200:
                logger.warning("[GEOCODE] OpenCage HTTP %s para %r", resp.status_code, query)
                return None
            data = resp.json()
            results = data.get("results") or []
            if not results:
                return None
            geom = results[0].get("geometry") or {}
            lat = geom.get("lat")
            lng = geom.get("lng")
            if lat is None or lng is None:
                return None
            return (float(lat), float(lng))
    except Exception as e:
        logger.warning("[GEOCODE] OpenCage erro %s", e)
        return None


async def geocode_endereco(rua=None, numero=None, bairro=None, cidade=None, estado=None, cep=None) -> tuple[float, float] | None:
    """Forward geocoding: endereco -> (lat, lng) ou None se nao achar.

    Prioriza OpenCage (se OPENCAGE_KEY definida). Fallback: Nominatim
    (gratuito, sem chave, mas respeitar <=1 req/s).

    OpenCage nao aceita query estruturada; montamos a query textual completa
    (montar_endereco) e fazemos uma unica chamada.
    """
    if not any([rua, cidade, cep, bairro]):
        return None

    query = montar_endereco(rua, numero, bairro, cidade, estado, cep)
    if query == "Brasil":
        return None

    if OPENCAGE_KEY:
        result = await _geocode_opencage(query)
        if result:
            return result
        logger.warning("[GEOCODE] OpenCage sem resultado para %r, tentando Nominatim", query)
        return None

    # ---------- Fallback: Nominatim ----------
    params_base = {"format": "json", "addressdetails": "1", "limit": "1", "country": "Brasil"}

    async with httpx.AsyncClient(timeout=10, headers={"Accept": "application/json", "User-Agent": "app-motorista/1.0"}) as client:
        # Estrategia 1: estruturada (melhor para ruas com acentos/siglas)
        params = dict(params_base)
        rua = _s(rua)
        numero = _s(numero)
        cidade = _s(cidade)
        estado = _s(estado)
        cep = _s(cep)
        if rua or numero:
            params["street"] = ", ".join(x for x in [rua, numero] if x)
        if cidade:
            params["city"] = cidade
        if estado:
            params["state"] = estado
        if cep:
            params["postalcode"] = cep

        try:
            resp = await client.get(NOMINATIM_SEARCH, params=params)
            if resp.status_code == 200:
                data = resp.json()
                if data:
                    hit = data[0]
                    return (float(hit["lat"]), float(hit["lon"]))
        except Exception as e:
            logger.warning("[GEOCODE] estruturada erro %s", e)

        # Estrategia 2: query textual (fallback mais permissivo)
        try:
            resp = await client.get(
                NOMINATIM_SEARCH,
                params={"format": "json", "addressdetails": "1", "limit": "1", "q": query}
            )
            if resp.status_code == 200:
                data = resp.json()
                if data:
                    hit = data[0]
                    return (float(hit["lat"]), float(hit["lon"]))
        except Exception as e:
            logger.warning("[GEOCODE] textual erro %s em %r", e, query)

    return None