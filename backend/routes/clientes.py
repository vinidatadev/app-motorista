import io
from datetime import datetime, timezone
from uuid import UUID, uuid4
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, constr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, distinct
from database import get_db
from models import Cliente, ClienteFoto, ClienteAlteracao
from auth import require_permission
from geocode import geocode_endereco
import storage

router = APIRouter(tags=["clientes"])

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB

# --- Schemas ---

class FotoOut(BaseModel):
    id: UUID
    url: str
    created_at: str

    @classmethod
    def from_orm(cls, f: ClienteFoto):
        return cls(id=f.id, url=f.url, created_at=f.created_at.isoformat() if f.created_at else None)


class ClienteOut(BaseModel):
    id: UUID
    codigo: str | None
    nome_razao_social: str
    telefone: str | None
    pessoa_contato: str | None
    cep: str | None
    rua: str | None
    numero: str | None
    bairro: str | None
    cidade: str | None
    estado: str | None
    latitude: float | None
    longitude: float | None
    ponto_referencia: str | None
    observacao: str | None
    status_endereco: str = "aprovado"
    alterado_por_nome: str | None = None
    alterado_por_empresa: str | None = None
    alterado_em: str | None = None
    fotos: list[FotoOut] = []
    updated_at: str

    @classmethod
    def from_orm(cls, c: Cliente, fotos: list[ClienteFoto] | None = None):
        return cls(
            id=c.id,
            codigo=c.codigo,
            nome_razao_social=c.nome_razao_social,
            telefone=c.telefone,
            pessoa_contato=c.pessoa_contato,
            cep=c.cep,
            rua=c.rua,
            numero=c.numero,
            bairro=c.bairro,
            cidade=c.cidade,
            estado=c.estado,
            latitude=float(c.latitude) if c.latitude is not None else None,
            longitude=float(c.longitude) if c.longitude is not None else None,
            ponto_referencia=c.ponto_referencia,
            observacao=c.observacao,
            status_endereco=c.status_endereco or "aprovado",
            alterado_por_nome=c.alterado_por_nome,
            alterado_por_empresa=c.alterado_por_empresa,
            alterado_em=c.alterado_em.isoformat() if c.alterado_em else None,
            fotos=[FotoOut.from_orm(f) for f in (fotos or [])],
            updated_at=c.updated_at.isoformat() if c.updated_at else None,
        )


async def _carregar_fotos(db: AsyncSession, cliente_id: UUID) -> list[ClienteFoto]:
    """Carrega fotos ordenadas por data de criacao (mais recente primeiro)."""
    result = await db.execute(
        select(ClienteFoto)
        .where(ClienteFoto.cliente_id == cliente_id)
        .order_by(ClienteFoto.created_at.desc())
    )
    return result.scalars().all()


async def _cliente_out(db: AsyncSession, c: Cliente) -> ClienteOut:
    """Monta ClienteOut com fotos anexas."""
    fotos = await _carregar_fotos(db, c.id)
    return ClienteOut.from_orm(c, fotos=fotos)


class ClienteCreate(BaseModel):
    codigo: constr(strip_whitespace=True, max_length=50) | None = None
    nome_razao_social: str = Field(..., min_length=1, max_length=150)
    telefone: constr(strip_whitespace=True, max_length=20) | None = None
    pessoa_contato: constr(strip_whitespace=True, max_length=100) | None = None
    cep: constr(strip_whitespace=True, max_length=10) | None = None
    rua: constr(strip_whitespace=True, max_length=150) | None = None
    numero: constr(strip_whitespace=True, max_length=20) | None = None
    bairro: constr(strip_whitespace=True, max_length=100) | None = None
    cidade: constr(strip_whitespace=True, max_length=100) | None = None
    estado: constr(strip_whitespace=True, min_length=2, max_length=2) | None = None
    latitude: float | None = None
    longitude: float | None = None
    ponto_referencia: constr(strip_whitespace=True, max_length=200) | None = None
    observacao: constr(strip_whitespace=True, max_length=2000) | None = None


class ClienteUpdate(BaseModel):
    codigo: constr(strip_whitespace=True, max_length=50) | None = None
    nome_razao_social: str | None = Field(default=None, min_length=1, max_length=150)
    telefone: constr(strip_whitespace=True, max_length=20) | None = None
    pessoa_contato: constr(strip_whitespace=True, max_length=100) | None = None
    cep: constr(strip_whitespace=True, max_length=10) | None = None
    rua: constr(strip_whitespace=True, max_length=150) | None = None
    numero: constr(strip_whitespace=True, max_length=20) | None = None
    bairro: constr(strip_whitespace=True, max_length=100) | None = None
    cidade: constr(strip_whitespace=True, max_length=100) | None = None
    estado: constr(strip_whitespace=True, min_length=2, max_length=2) | None = None
    latitude: float | None = None
    longitude: float | None = None
    ponto_referencia: constr(strip_whitespace=True, max_length=200) | None = None
    observacao: constr(strip_whitespace=True, max_length=2000) | None = None


# --- Locais (estados / cidades) ---

@router.get("/locais/estados", response_model=list[str])
async def listar_estados(
    db: AsyncSession = Depends(get_db),
    _: Any = Depends(require_permission("visualizar")),
):
    result = await db.execute(
        select(distinct(Cliente.estado))
        .where(Cliente.estado.is_not(None))
        .order_by(Cliente.estado)
    )
    return [r[0] for r in result.all()]


@router.get("/locais/cidades", response_model=list[str])
async def listar_cidades(
    estado: str = Query(..., min_length=2, max_length=2, description="Sigla da UF"),
    db: AsyncSession = Depends(get_db),
    _: Any = Depends(require_permission("visualizar")),
):
    result = await db.execute(
        select(distinct(Cliente.cidade))
        .where(Cliente.estado == estado.upper(), Cliente.cidade.is_not(None))
        .order_by(Cliente.cidade)
    )
    return [r[0] for r in result.all()]


# --- Clientes ---

@router.get("/clientes", response_model=list[ClienteOut])
async def listar_clientes(
    estado: str | None = Query(default=None, max_length=2),
    cidade: str | None = Query(default=None, max_length=100),
    db: AsyncSession = Depends(get_db),
    _: Any = Depends(require_permission("visualizar")),
):
    stmt = select(Cliente).order_by(Cliente.estado, Cliente.cidade, Cliente.nome_razao_social)
    if estado:
        stmt = stmt.where(Cliente.estado == estado.upper())
    if cidade:
        stmt = stmt.where(Cliente.cidade.ilike(cidade))
    result = await db.execute(stmt)
    clientes = result.scalars().all()
    # Carrega fotos em paralelo (1 query por cliente; em lista grande, otimizar depois)
    return [await _cliente_out(db, c) for c in clientes]


# --- Exportar Excel ---

@router.get("/clientes/export")
async def exportar_clientes(
    estado: str | None = Query(default=None, max_length=2),
    cidade: str | None = Query(default=None, max_length=100),
    db: AsyncSession = Depends(get_db),
    _: Any = Depends(require_permission("exportar")),
):
    import openpyxl

    stmt = select(Cliente).order_by(Cliente.estado, Cliente.cidade, Cliente.nome_razao_social)
    if estado:
        stmt = stmt.where(Cliente.estado == estado.upper())
    if cidade:
        stmt = stmt.where(Cliente.cidade.ilike(cidade))
    result = await db.execute(stmt)
    clientes = result.scalars().all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Clientes"
    colunas = ["codigo", "nome_razao_social", "telefone", "pessoa_contato", "cep", "rua",
               "numero", "bairro", "cidade", "estado", "latitude", "longitude",
               "ponto_referencia", "observacao"]
    ws.append(colunas)
    for c in clientes:
        ws.append([
            c.codigo, c.nome_razao_social, c.telefone, c.pessoa_contato, c.cep, c.rua,
            c.numero, c.bairro, c.cidade, c.estado,
            float(c.latitude) if c.latitude is not None else None,
            float(c.longitude) if c.longitude is not None else None,
            c.ponto_referencia, c.observacao,
        ])
    # Largura auto
    for i, col in enumerate(colunas, 1):
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = max(len(col) + 4, 16)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=clientes.xlsx"}
    )


# --- Carga em massa via Excel (preview upsert) ---

COLUNAS_XLSX = ["codigo", "nome_razao_social", "telefone", "pessoa_contato", "cep", "rua",
                "numero", "bairro", "cidade", "estado", "latitude", "longitude",
                "ponto_referencia", "observacao"]


def _parse_valor(v):
    """Normaliza valor da celula: None/vazio -> None, numero -> str, floats de lat/lng ficam float."""
    if v is None:
        return None
    if isinstance(v, str):
        s = v.strip()
        return s if s else None
    return v


@router.post("/clientes/carga/preview")
async def preview_carga(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _: Any = Depends(require_permission("carga")),
):
    """Faz upload do xlsx e retorna preview do que sera inserido (novos) e alterado (updates)."""
    import openpyxl

    data = await file.read()
    wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True)
    ws = wb.active

    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        raise HTTPException(status_code=422, detail="Planilha vazia")
    header = [str(c).strip().lower() if c is not None else "" for c in rows[0]]

    # Mapeia colunas por nome (primeira linha)
    idx = {}
    for i, h in enumerate(header):
        if h in COLUNAS_XLSX:
            idx[h] = i

    # Verifica colunas obrigatorias
    if "nome_razao_social" not in idx:
        raise HTTPException(status_code=422, detail="Coluna 'nome_razao_social' nao encontrada")
    if "codigo" not in idx:
        raise HTTPException(status_code=422, detail="Coluna 'codigo' nao encontrada")

    dados_linhas = []
    for row in rows[1:]:
        # Pula linhas totalmente vazias
        if all(v is None or (isinstance(v, str) and not v.strip()) for v in row):
            continue
        registro = {}
        for col, i in idx.items():
            registro[col] = _parse_valor(row[i] if i < len(row) else None)
        dados_linhas.append(registro)

    # Separa por codigo: existentes (update) vs novos (insert)
    codigos = [d["codigo"] for d in dados_linhas if d.get("codigo")]
    codigos_set = set(codigos)

    existing_map = {}
    if codigos_set:
        result = await db.execute(select(Cliente).where(Cliente.codigo.in_(codigos_set)))
        for c in result.scalars().all():
            existing_map[c.codigo] = c

    novos = []
    alterados = []
    for d in dados_linhas:
        cod = d.get("codigo")
        if cod and cod in existing_map:
            c = existing_map[cod]
            atual = ClienteOut.from_orm(c).model_dump()
            # Compara apenas campos que estao no registro
            mudancas = {}
            for k, v in d.items():
                atual_val = atual.get(k)
                # Normaliza ambos para comparacao string
                if str(v) != str(atual_val):
                    mudancas[k] = {"de": atual_val, "para": v}
            alterados.append({
                "codigo": cod,
                "nome_razao_social": d.get("nome_razao_social"),
                "mudancas": mudancas,
                "id": str(c.id),
            })
        else:
            novos.append(d)

    return {
        "total_linhas": len(dados_linhas),
        "novos": novos,
        "alterados": alterados,
        "quantidade_novos": len(novos),
        "quantidade_alterados": len(alterados),
    }


@router.post("/clientes/carga/aplicar")
async def aplicar_carga(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _: Any = Depends(require_permission("carga")),
):
    """Aplica a carga do xlsx (upsert por codigo)."""
    import openpyxl

    data = await file.read()
    wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        raise HTTPException(status_code=422, detail="Planilha vazia")
    header = [str(c).strip().lower() if c is not None else "" for c in rows[0]]
    idx = {}
    for i, h in enumerate(header):
        if h in COLUNAS_XLSX:
            idx[h] = i
    if "nome_razao_social" not in idx:
        raise HTTPException(status_code=422, detail="Coluna 'nome_razao_social' nao encontrada")
    if "codigo" not in idx:
        raise HTTPException(status_code=422, detail="Coluna 'codigo' nao encontrada")

    dados_linhas = []
    for row in rows[1:]:
        if all(v is None or (isinstance(v, str) and not v.strip()) for v in row):
            continue
        registro = {}
        for col, i in idx.items():
            registro[col] = _parse_valor(row[i] if i < len(row) else None)
        dados_linhas.append(registro)

    codigos = set(d["codigo"] for d in dados_linhas if d.get("codigo"))
    existing_map = {}
    if codigos:
        result = await db.execute(select(Cliente).where(Cliente.codigo.in_(codigos)))
        for c in result.scalars().all():
            existing_map[c.codigo] = c

    import asyncio
    inseridos = 0
    atualizados = 0
    geocoded = 0
    for d in dados_linhas:
        cod = d.get("codigo")
        # Forward geocoding automatico quando lat/lng vazios mas endereco existe.
        # Importante: Nominatim tem rate limit de 1 req/s — damos um pequeno sleep
        # entre chamadas para respeitar a politica de uso gratuito.
        precisa_geo = (not d.get("latitude") and not d.get("longitude")) and (
            d.get("rua") or d.get("cidade") or d.get("cep")
        )
        if precisa_geo:
            coords = await geocode_endereco(
                rua=d.get("rua"), numero=d.get("numero"), bairro=d.get("bairro"),
                cidade=d.get("cidade"), estado=d.get("estado"), cep=d.get("cep")
            )
            if coords:
                d["latitude"] = coords[0]
                d["longitude"] = coords[1]
                geocoded += 1
            # Respeita o rate limit do Nominatim (~1 req/s)
            await asyncio.sleep(1)

        if cod and cod in existing_map:
            c = existing_map[cod]
            for k, v in d.items():
                setattr(c, k, v)
            atualizados += 1
        else:
            db.add(Cliente(**d))
            inseridos += 1

    await db.commit()
    return {
        "inseridos": inseridos,
        "atualizados": atualizados,
        "geocoded": geocoded,
        "total": inseridos + atualizados
    }


# --- CRUD por ID (depois das rotas estaticas para nao conflitar) ---

@router.post("/clientes", response_model=ClienteOut, status_code=status.HTTP_201_CREATED)
async def criar_cliente(
    body: ClienteCreate,
    db: AsyncSession = Depends(get_db),
    _: Any = Depends(require_permission("criar")),
):
    if body.codigo:
        existing = await db.execute(select(Cliente).where(Cliente.codigo == body.codigo))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail=f"Cliente com codigo '{body.codigo}' ja existe")

    dados = body.model_dump()
    # Forward geocoding automatico quando lat/lng nao informados mas endereco existe
    if (dados.get("latitude") is None and dados.get("longitude") is None) and (
        dados.get("rua") or dados.get("cidade") or dados.get("cep")
    ):
        coords = await geocode_endereco(
            rua=dados.get("rua"), numero=dados.get("numero"), bairro=dados.get("bairro"),
            cidade=dados.get("cidade"), estado=dados.get("estado"), cep=dados.get("cep")
        )
        if coords:
            dados["latitude"] = coords[0]
            dados["longitude"] = coords[1]

    c = Cliente(**dados)
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return await _cliente_out(db, c)


@router.get("/clientes/{cliente_id}", response_model=ClienteOut)
async def obter_cliente(
    cliente_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: Any = Depends(require_permission("visualizar")),
):
    c = await db.get(Cliente, cliente_id)
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente nao encontrado")
    return await _cliente_out(db, c)


@router.put("/clientes/{cliente_id}", response_model=ClienteOut)
async def atualizar_cliente(
    cliente_id: UUID,
    body: ClienteUpdate,
    db: AsyncSession = Depends(get_db),
    user: Any = Depends(require_permission("editar")),
):
    """Atualiza o cliente OU cria submissao pendente (se motorista sem 'aprovar').
    Quem tem 'aprovar' edita direto. Quem so' tem 'editar' gera alteracao pendente."""
    c = await db.get(Cliente, cliente_id)
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente nao encontrado")

    # Bloqueia edicao enquanto houver alteracao pendente de aprovacao.
    # Depois que o aprovador aprovar/recusar, o status volta para 'aprovado' e a edicao libera.
    if c.status_endereco == "atualizando":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cliente com alteração pendente de aprovação. A edição só será liberada após a aprovação."
        )

    dados = body.model_dump(exclude_unset=True)

    permission_aprovar = (user["role"] == "admin") or ("aprovar" in (user.get("permissions") or []))

    if permission_aprovar:
        # Aprovador/admin: edita direto no cliente
        for campo, valor in dados.items():
            setattr(c, campo, valor)

        # Forward geocoding automatico
        if ("latitude" not in dados and "longitude" not in dados and
                c.latitude is None and c.longitude is None and
                (c.rua or c.cidade or c.cep)):
            coords = await geocode_endereco(
                rua=c.rua, numero=c.numero, bairro=c.bairro,
                cidade=c.cidade, estado=c.estado, cep=c.cep
            )
            if coords:
                c.latitude = coords[0]
                c.longitude = coords[1]

        # Marca como aprovado (foi alterado direto) e registra quem alterou
        c.status_endereco = "aprovado"
        c.alterado_por_user_id = UUID(user["user_id"])
        c.alterado_por_nome = user["name"]
        c.alterado_por_empresa = user.get("empresa") or "AC"
        c.alterado_em = datetime.now(timezone.utc)
    else:
        # Motorista: grava snapshot dos campos propostos e marca pendencia
        # Snapshot com TODOS os campos editaveis no estado proposto (mesclando com os atuais)
        campos_editaveis = [
            "codigo", "nome_razao_social", "telefone", "pessoa_contato", "cep", "rua",
            "numero", "bairro", "cidade", "estado", "latitude", "longitude",
            "ponto_referencia", "observacao"
        ]
        snapshot = {}
        for campo in campos_editaveis:
            if campo in dados:
                snapshot[campo] = dados[campo]
            else:
                # Manter valor atual
                v = getattr(c, campo)
                if campo in ("latitude", "longitude") and v is not None:
                    snapshot[campo] = float(v)
                else:
                    snapshot[campo] = v

        # IMPORTANTE: NAO altera os dados do cliente (snapshot fica guardado para revisao)

        # Atualiza o controle de quem submeteu
        c.status_endereco = "atualizando"
        c.alterado_por_user_id = UUID(user["user_id"])
        c.alterado_por_nome = user["name"]
        c.alterado_por_empresa = user.get("empresa") or "AC"
        c.alterado_em = datetime.now(timezone.utc)

        # Remove submissoes pendentes anteriores deste cliente (mantem apenas a mais nova)
        anteriores = await db.execute(
            select(ClienteAlteracao).where(
                ClienteAlteracao.cliente_id == cliente_id,
                ClienteAlteracao.status == "pendente"
            )
        )
        for a in anteriores.scalars().all():
            await db.delete(a)

        # Cria nova submissao pendente
        alt = ClienteAlteracao(
            cliente_id=cliente_id,
            snapshot=snapshot,
            motorista_user_id=UUID(user["user_id"]),
            motorista_nome=user["name"],
            motorista_empresa=user.get("empresa") or "AC",
            status="pendente",
        )
        db.add(alt)

    await db.commit()
    await db.refresh(c)
    return await _cliente_out(db, c)


@router.delete("/clientes/{cliente_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deletar_cliente(
    cliente_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: Any = Depends(require_permission("deletar")),
):
    c = await db.get(Cliente, cliente_id)
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente nao encontrado")
    # Remove fotos do MinIO antes de apagar o cliente
    fotos = await _carregar_fotos(db, cliente_id)
    for f in fotos:
        info = storage.extract_key_from_url(f.url)
        if info:
            storage.delete_file(info[1], bucket=info[0])
    # Remove registros de foto do banco
    for f in fotos:
        await db.delete(f)
    await db.delete(c)
    await db.commit()


# --- Fotos do cliente ---

@router.post("/clientes/{cliente_id}/fotos", response_model=FotoOut, status_code=status.HTTP_201_CREATED)
async def upload_foto(
    cliente_id: UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _: Any = Depends(require_permission("editar")),
):
    """Anexa uma foto ao cliente (jpeg/png/webp/gif, max 5MB)."""
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=422, detail="Tipo de arquivo nao permitido. Use JPEG, PNG, WEBP ou GIF.")

    c = await db.get(Cliente, cliente_id)
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente nao encontrado")

    data = await file.read()
    if len(data) > MAX_IMAGE_SIZE:
        raise HTTPException(status_code=422, detail="Arquivo muito grande. Maximo 5 MB.")

    foto_id = uuid4()
    ext = (file.filename.rsplit(".", 1)[-1] if file.filename and "." in file.filename else "jpg").lower()
    key = f"{cliente_id}/{foto_id}.{ext}"
    url = storage.upload_file(key, data, file.content_type, bucket=storage.CLIENTES_BUCKET)

    foto = ClienteFoto(id=foto_id, cliente_id=cliente_id, url=url)
    db.add(foto)
    await db.commit()
    await db.refresh(foto)
    return FotoOut.from_orm(foto)


@router.delete("/clientes/{cliente_id}/fotos/{foto_id}", response_model=ClienteOut)
async def deletar_foto(
    cliente_id: UUID,
    foto_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: Any = Depends(require_permission("editar")),
):
    """Remove uma foto especifica do cliente (apaga do MinIO e do banco)."""
    c = await db.get(Cliente, cliente_id)
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente nao encontrado")

    foto = await db.get(ClienteFoto, foto_id)
    if not foto or foto.cliente_id != cliente_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Foto nao encontrada")

    # Remove do MinIO
    info = storage.extract_key_from_url(foto.url)
    if info:
        storage.delete_file(info[1], bucket=info[0])

    await db.delete(foto)
    await db.commit()
    await db.refresh(c)
    return await _cliente_out(db, c)


# --- Submissoes pendentes (aprovador) ---

CAMPOS_EDITAVEIS = [
    "codigo", "nome_razao_social", "telefone", "pessoa_contato", "cep", "rua",
    "numero", "bairro", "cidade", "estado", "latitude", "longitude",
    "ponto_referencia", "observacao"
]


class AlteracaoOut(BaseModel):
    id: UUID
    cliente_id: UUID
    cliente_codigo: str | None = None
    cliente_nome: str = ""
    snapshot: dict
    # Endereco/dados atuais do cliente no momento da submissao (para comparar no diff)
    cliente_atual: dict = {}
    motorista_nome: str
    motorista_empresa: str = "AC"
    status: str
    observacao_revisao: str | None = None
    created_at: str
    revisado_at: str | None = None
    revisado_por_nome: str | None = None
    revisado_por_empresa: str | None = None

    @classmethod
    def from_orm(cls, a: ClienteAlteracao, cliente: Cliente | None = None):
        return cls(
            id=a.id,
            cliente_id=a.cliente_id,
            cliente_codigo=cliente.codigo if cliente else None,
            cliente_nome=cliente.nome_razao_social if cliente else "",
            snapshot=a.snapshot or {},
            cliente_atual=_cliente_atual_dict(cliente),
            motorista_nome=a.motorista_nome,
            motorista_empresa=a.motorista_empresa or "AC",
            status=a.status,
            observacao_revisao=a.observacao_revisao,
            created_at=a.created_at.isoformat() if a.created_at else None,
            revisado_at=a.revisado_at.isoformat() if a.revisado_at else None,
            revisado_por_nome=a.revisado_por_nome,
            revisado_por_empresa=a.revisado_por_empresa,
        )


def _cliente_atual_dict(c: Cliente | None) -> dict:
    """Extrai os campos de endereco atuais do cliente para o diff."""
    if c is None:
        return {}
    def _f(v):
        if v is None:
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return v
    return {
        "rua": c.rua,
        "numero": c.numero,
        "bairro": c.bairro,
        "cep": c.cep,
        "cidade": c.cidade,
        "estado": c.estado,
        "latitude": _f(c.latitude),
        "longitude": _f(c.longitude),
        "ponto_referencia": c.ponto_referencia,
        "observacao": c.observacao,
    }


class RecusarBody(BaseModel):
    observacao: str | None = Field(default=None, max_length=500)


class EditarAlteracaoBody(BaseModel):
    """Edita o snapshot antes de aprovar. Campos opcionais."""
    nome_razao_social: constr(strip_whitespace=True, max_length=150) | None = None
    telefone: constr(strip_whitespace=True, max_length=20) | None = None
    pessoa_contato: constr(strip_whitespace=True, max_length=100) | None = None
    cep: constr(strip_whitespace=True, max_length=10) | None = None
    rua: constr(strip_whitespace=True, max_length=150) | None = None
    numero: constr(strip_whitespace=True, max_length=20) | None = None
    bairro: constr(strip_whitespace=True, max_length=100) | None = None
    cidade: constr(strip_whitespace=True, max_length=100) | None = None
    estado: constr(strip_whitespace=True, min_length=2, max_length=2) | None = None
    latitude: float | None = None
    longitude: float | None = None
    ponto_referencia: constr(strip_whitespace=True, max_length=200) | None = None
    observacao: constr(strip_whitespace=True, max_length=2000) | None = None


@router.get("/alteracoes", response_model=list[AlteracaoOut])
async def listar_alteracoes(
    status_filter: str | None = Query(default=None, alias="status"),
    empresa: str | None = Query(default=None, alias="empresa"),
    db: AsyncSession = Depends(get_db),
    _: Any = Depends(require_permission("aprovar")),
):
    """Lista submissoes (default: todas; passe ?status=pendente para pendentes).
    ?empresa=AC|SIN filtra pelo MOTORISTA que solicitou a alteracao."""
    stmt = select(ClienteAlteracao, Cliente).join(
        Cliente, ClienteAlteracao.cliente_id == Cliente.id, isouter=True
    ).order_by(ClienteAlteracao.created_at.desc())
    if status_filter:
        stmt = stmt.where(ClienteAlteracao.status == status_filter)
    if empresa:
        stmt = stmt.where(ClienteAlteracao.motorista_empresa == empresa)
    result = await db.execute(stmt)
    rows = result.all()
    return [AlteracaoOut.from_orm(a, c) for (a, c) in rows]


async def _get_alteracao(db: AsyncSession, alt_id: UUID) -> ClienteAlteracao:
    a = await db.get(ClienteAlteracao, alt_id)
    if not a:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submissao nao encontrada")
    return a


async def _aplica_snapshot(c: Cliente, snapshot: dict, db: AsyncSession):
    """Aplica o snapshot aos campos editaveis do cliente e regeocoda se precisar."""
    for campo in CAMPOS_EDITAVEIS:
        if campo in snapshot:
            setattr(c, campo, snapshot[campo])

    # Se ficou sem coords (e endereco existe) tenta geocoding
    if (c.latitude is None and c.longitude is None) and (c.rua or c.cidade or c.cep):
        coords = await geocode_endereco(
            rua=c.rua, numero=c.numero, bairro=c.bairro,
            cidade=c.cidade, estado=c.estado, cep=c.cep
        )
        if coords:
            c.latitude = coords[0]
            c.longitude = coords[1]


@router.post("/alteracoes/{alt_id}/aprovar", response_model=AlteracaoOut)
async def aprovar_alteracao(
    alt_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: Any = Depends(require_permission("aprovar")),
):
    """Aprova a submissao: aplica o snapshot no cliente e fecha como 'aprovado'."""
    a = await _get_alteracao(db, alt_id)
    if a.status != "pendente":
        raise HTTPException(status_code=400, detail=f"Submissao ja {a.status}")

    c = await db.get(Cliente, a.cliente_id)
    if not c:
        raise HTTPException(status_code=404, detail="Cliente nao existe mais")

    await _aplica_snapshot(c, a.snapshot or {}, db)

    # Status volta a aprovado, mas alterado_por_* continua sendo quem PEDIU (o motorista),
    # para a pesquisa/histórico mostrar quem solicitou a mudanca.
    c.status_endereco = "aprovado"

    a.status = "aprovado"
    a.revisado_at = datetime.now(timezone.utc)
    a.revisado_por_user_id = UUID(user["user_id"])
    a.revisado_por_nome = user["name"]
    a.revisado_por_empresa = user.get("empresa") or "AC"

    await db.commit()
    await db.refresh(a)
    return AlteracaoOut.from_orm(a, c)


@router.post("/alteracoes/{alt_id}/recusar", response_model=AlteracaoOut)
async def recusar_alteracao(
    alt_id: UUID,
    body: RecusarBody,
    db: AsyncSession = Depends(get_db),
    user: Any = Depends(require_permission("aprovar")),
):
    """Recusa a submissao: mantem o endereco atual do cliente."""
    a = await _get_alteracao(db, alt_id)
    if a.status != "pendente":
        raise HTTPException(status_code=400, detail=f"Submissao ja {a.status}")

    c = await db.get(Cliente, a.cliente_id)
    # Se cliente existe, volta o status dele para 'aprovado' (sem alterar endereco)
    if c:
        c.status_endereco = "aprovado"
        c.alterado_por_user_id = None
        c.alterado_por_nome = None
        c.alterado_por_empresa = None
        c.alterado_em = None

    a.status = "recusado"
    a.observacao_revisao = body.observacao
    a.revisado_at = datetime.now(timezone.utc)
    a.revisado_por_user_id = UUID(user["user_id"])
    a.revisado_por_nome = user["name"]
    a.revisado_por_empresa = user.get("empresa") or "AC"

    await db.commit()
    await db.refresh(a)
    return AlteracaoOut.from_orm(a, c)


@router.put("/alteracoes/{alt_id}/editar", response_model=AlteracaoOut)
async def editar_e_aprovar_alteracao(
    alt_id: UUID,
    body: EditarAlteracaoBody,
    db: AsyncSession = Depends(get_db),
    user: Any = Depends(require_permission("aprovar")),
):
    """Aprovador ajusta o snapshot antes de aplicar, e ja aprova."""
    a = await _get_alteracao(db, alt_id)
    if a.status != "pendente":
        raise HTTPException(status_code=400, detail=f"Submissao ja {a.status}")

    c = await db.get(Cliente, a.cliente_id)
    if not c:
        raise HTTPException(status_code=404, detail="Cliente nao existe mais")

    # Aplica os overrides do aprovador por cima do snapshot
    snapshot = dict(a.snapshot or {})
    updates = body.model_dump(exclude_unset=True)
    for k, v in updates.items():
        snapshot[k] = v

    await _aplica_snapshot(c, snapshot, db)
    c.status_endereco = "aprovado"
    # alterado_por_* mantém quem PEDIU (o motorista) — o revisor fica em revisado_por_*

    # Atualiza o snapshot da submissao com os ajustes e marca como 'editado'/aprovado
    a.snapshot = snapshot
    a.status = "editado"
    a.observacao_revisao = "Editado e aprovado pelo revisor"
    a.revisado_at = datetime.now(timezone.utc)
    a.revisado_por_user_id = UUID(user["user_id"])
    a.revisado_por_nome = user["name"]
    a.revisado_por_empresa = user.get("empresa") or "AC"

    await db.commit()
    await db.refresh(a)
    return AlteracaoOut.from_orm(a, c)


@router.get("/clientes/{cliente_id}/alteracoes", response_model=list[AlteracaoOut])
async def historico_alteracoes_cliente(
    cliente_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: Any = Depends(require_permission("visualizar")),
):
    """Historico de submissoes de alteracao de um cliente especifico."""
    c = await db.get(Cliente, cliente_id)
    if not c:
        raise HTTPException(status_code=404, detail="Cliente nao encontrado")
    result = await db.execute(
        select(ClienteAlteracao)
        .where(ClienteAlteracao.cliente_id == cliente_id)
        .order_by(ClienteAlteracao.created_at.desc())
    )
    return [AlteracaoOut.from_orm(a, c) for a in result.scalars().all()]