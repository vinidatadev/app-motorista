import os
import logging
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

ENDPOINT    = os.getenv("MINIO_ENDPOINT", "minio:9000")
ACCESS_KEY  = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
SECRET_KEY  = os.getenv("MINIO_SECRET_KEY", "minioadmin")
CLIENTES_BUCKET = os.getenv("MINIO_CLIENTES_BUCKET", "clientes")  # bucket/container de fotos
PUBLIC_URL  = os.getenv("MINIO_PUBLIC_URL", "http://localhost:9000")

# Se o endpoint aponta para o Azure Blob Storage, usa o SDK nativo
# (azure-storage-blob) em vez de boto3/S3. Isso evita depender do
# protocolo S3, que nem todas as regioes/contas do Azure habilitam.
IS_AZURE_BLOB = ".blob.core.windows.net" in ENDPOINT

if IS_AZURE_BLOB:
    from azure.storage.blob import (
        BlobServiceClient, generate_blob_sas, BlobSasPermissions,
    )
    from datetime import datetime, timedelta, timezone
else:
    # Quando não é Azure, define stub vazio pra evitar NameError nas type hints
    BlobServiceClient = None

# Buckets que devem ser criados automaticamente na inicializacao
_ALL_BUCKETS = [CLIENTES_BUCKET]


def _warn_default_creds():
    """Alerta caso esteja rodando com as credenciais padrão (nunca usar em produção)."""
    if not IS_AZURE_BLOB and ACCESS_KEY == "minioadmin" and SECRET_KEY == "minioadmin":
        logger.warning(
            "[STORAGE] MinIO usando credenciais PADRAO (minioadmin). "
            "Troque MINIO_ACCESS_KEY/MINIO_SECRET_KEY em producao."
        )


_warn_default_creds()

# ---------------------------------------------------------------------------
# Azure Blob (SDK nativo)
# ---------------------------------------------------------------------------

def _azure_service():
    """Cliente do Azure Blob usando a chave de acesso da conta."""
    if not IS_AZURE_BLOB:
        raise RuntimeError("Azure Blob não está configurado. Use MinIO localmente.")
    account_url = f"https://{ENDPOINT}"
    return BlobServiceClient(account_url=account_url, credential=SECRET_KEY)


def _azure_container(container: str):
    return _azure_service().get_container_client(container)


def _azure_ensure_one(container: str):
    """Garante que o container exista (privado)."""
    try:
        _azure_service().create_container(container)
    except Exception:
        pass  # ja existe (ou erro de permissao — deixado para o fluxo)


# ---------------------------------------------------------------------------
# S3-compatible (MinIO / Blob S3 / AWS)
# ---------------------------------------------------------------------------

def _endpoint_url() -> str:
    """Normaliza MINIO_ENDPOINT aceitando ou não o scheme.

    - "minio:9000"  -> http://minio:9000   (padrão Docker interno)
    - "https://acct.blob.core.windows.net" -> mantém (Azure Blob exige HTTPS)
    """
    return ENDPOINT if "://" in ENDPOINT else f"http://{ENDPOINT}"


def _client():
    return boto3.client(
        "s3",
        endpoint_url=_endpoint_url(),
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        region_name="us-east-1",
    )


def _public_client():
    """Cliente S3 apontando para a URL PÚBLICA do MinIO.

    As presigned URLs precisam ser assinadas com o mesmo host que o navegador
    vai acessar (MINIO_PUBLIC_URL), e não com o hostname interno do Docker
    (minio:9000) — senão a imagem não carrega nem passa no CSP.
    """
    scheme = "https" if PUBLIC_URL.startswith("https") else "http"
    host = PUBLIC_URL.replace("http://", "").replace("https://", "").rstrip("/")
    return boto3.client(
        "s3",
        endpoint_url=f"{scheme}://{host}",
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        region_name="us-east-1",
    )


def _ensure_one(s3, name: str):
    """Cria um bucket (privado). Acesso só via presigned URLs geradas pela API."""
    try:
        s3.head_bucket(Bucket=name)
    except ClientError:
        s3.create_bucket(Bucket=name)


# ---------------------------------------------------------------------------
# Interface comum
# ---------------------------------------------------------------------------

def ensure_bucket():
    """Garante todos os buckets/containers do app (clientes)."""
    if IS_AZURE_BLOB:
        for b in _ALL_BUCKETS:
            _azure_ensure_one(b)
        return
    s3 = _client()
    for b in _ALL_BUCKETS:
        _ensure_one(s3, b)


def upload_file(key: str, data: bytes, content_type: str, bucket: str | None = None) -> str:
    """Faz upload e retorna a URL publica (Usa o bucket de clientes se nao for informado)."""
    b = bucket or CLIENTES_BUCKET
    if IS_AZURE_BLOB:
        from azure.storage.blob import ContentSettings
        cc = _azure_container(b)
        cc.upload_blob(
            name=key, 
            data=data, 
            overwrite=True, 
            content_settings=ContentSettings(content_type=content_type)
        )
        return f"{PUBLIC_URL}/{b}/{key}"
    s3 = _client()
    s3.put_object(Bucket=b, Key=key, Body=data, ContentType=content_type)
    return f"{PUBLIC_URL}/{b}/{key}"


def delete_file(key: str, bucket: str | None = None):
    b = bucket or CLIENTES_BUCKET
    if IS_AZURE_BLOB:
        try:
            _azure_container(b).delete_blob(key)
        except Exception:
            pass
        return
    s3 = _client()
    try:
        s3.delete_object(Bucket=b, Key=key)
    except ClientError:
        pass


def presign_url(key: str, bucket: str | None = None, expires: int = 3600) -> str:
    """Gera URL temporária e autenticada para leitura de um objeto do container/bucket.

    O container é privado; apenas quem recebe esta URL (expira após `expires` s)
    consegue baixar o arquivo. Não exige rede — a assinatura é calculada localmente.
    """
    b = bucket or CLIENTES_BUCKET
    if IS_AZURE_BLOB:
        sas = generate_blob_sas(
            account_name=ENDPOINT.split(".")[0],
            account_key=SECRET_KEY,
            container_name=b,
            blob_name=key,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.now(timezone.utc) + timedelta(seconds=expires),
        )
        return f"{PUBLIC_URL}/{b}/{key}?{sas}"
    s3 = _public_client()
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": b, "Key": key},
        ExpiresIn=expires,
    )


def extract_key_from_url(url: str) -> tuple[str, str] | None:
    """Extrai (bucket, key) de uma URL publica gerada por upload_file.

    URL tem o formato: {PUBLIC_URL}/{bucket}/{key}
    Retorna None se a URL nao for reconhecida.
    """
    if not url:
        return None
    # Ex.: http://localhost:9000/clientes/{cliente_id}/{foto_id}.jpg
    #      https://acct.blob.core.windows.net/clientes/{cliente_id}/{foto_id}.jpg?<sas>
    # split: ['http:', '', 'host', 'bucket', 'resto...']
    url = url.split("?")[0]  # remove query string (SAS)
    parts = url.split("/")
    if len(parts) < 5:
        return None
    bucket = parts[3]
    key = "/".join(parts[4:])
    return (bucket, key)


EXT_POR_TIPO = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/gif": "gif",
    "image/webp": "webp",
}


def validar_imagem(data: bytes) -> bool:
    """Valida a assinatura (magic bytes) de JPEG/PNG/GIF/WEBP.

    Evita subir conteudo arbitrario disfarçado de imagem (ex.: HTML/JS hosteado
    no bucket publico).
    """
    if len(data) < 12:
        return False
    if data[:3] == b"\xff\xd8\xff":
        return True   # JPEG
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return True   # PNG
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return True   # GIF
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return True   # WEBP
    return False
