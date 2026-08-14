import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, Numeric, ARRAY, JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # Só preenchido para auth_provider='local'; None para login Microsoft
    password_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    auth_provider: Mapped[str] = mapped_column(String(20), nullable=False)  # 'microsoft' | 'local'
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="user")  # 'admin' | 'user'
    # Permissoes granulares para role='user'. Admin ignora (sempre pode tudo).
    # Valores possiveis: 'visualizar', 'editar', 'criar', 'deletar', 'carga', 'exportar'
    permissions: Mapped[list[str] | None] = mapped_column(
        ARRAY(String), nullable=True, default=list
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    image_url: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class Cliente(Base):
    __tablename__ = "clientes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Codigo unico do cliente — chave para carga em massa (upsert)
    codigo: Mapped[str | None] = mapped_column(String(50), nullable=True, unique=True, index=True)
    nome_razao_social: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    telefone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    pessoa_contato: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cep: Mapped[str | None] = mapped_column(String(10), nullable=True)
    rua: Mapped[str | None] = mapped_column(String(150), nullable=True)
    numero: Mapped[str | None] = mapped_column(String(20), nullable=True)
    bairro: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cidade: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    estado: Mapped[str | None] = mapped_column(String(2), nullable=True, index=True)
    latitude: Mapped[float | None] = mapped_column(Numeric(10, 8), nullable=True)
    longitude: Mapped[float | None] = mapped_column(Numeric(11, 8), nullable=True)
    # Campos livres para o motorista
    ponto_referencia: Mapped[str | None] = mapped_column(String(200), nullable=True)
    observacao: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    # Status do endereco para o fluxo de aprovacao
    # 'aprovado' (endereco confiado pelo aprovador), 'atualizando' (motorista submeteu - aguardando revisao)
    status_endereco: Mapped[str] = mapped_column(String(20), nullable=False, default="aprovado", index=True)
    alterado_por_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    alterado_por_nome: Mapped[str | None] = mapped_column(String(200), nullable=True)
    alterado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class ClienteAlteracao(Base):
    """Submissao pendente de alteracao de endereco por motorista.
    O aprovador revisa: aprovar (aplica snapshot ao cliente), editar (modifica antes
    de aplicar), ou recusar (descarta com motivo)."""
    __tablename__ = "cliente_alteracoes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    cliente_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    # Snapshot dos campos propostos (dict com os campos editaveis)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    motorista_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    motorista_nome: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pendente", index=True)
    # 'pendente', 'aprovado', 'recusado', 'editado'
    observacao_revisao: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    revisado_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Quem revisou/aprovou/recusou a submissao
    revisado_por_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    revisado_por_nome: Mapped[str | None] = mapped_column(String(200), nullable=True)


class ClienteFoto(Base):
    __tablename__ = "cliente_fotos"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    cliente_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False, index=True
    )
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
