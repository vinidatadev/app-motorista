import os
import logging
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

ENDPOINT    = os.getenv("MINIO_ENDPOINT", "minio:9000")
ACCESS_KEY  = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
SECRET_KEY  = os.getenv("MINIO_SECRET_KEY", "minioadmin")
BUCKET      = os.getenv("MINIO_BUCKET", "tasks")          # bucket padrao (tarefas)
CLIENTES_BUCKET = os.getenv("MINIO_CLIENTES_BUCKET", "clientes")  # bucket de fotos de clientes
PUBLIC_URL  = os.getenv("MINIO_PUBLIC_URL", "http://localhost:9000")

# Buckets que devem ser criados automaticamente na inicializacao
_ALL_BUCKETS = [BUCKET, CLIENTES_BUCKET]


def _warn_default_creds():
    """Alerta caso esteja rodando com as credenciais MinIO padrão (nunca usar em produção)."""
    if ACCESS_KEY == "minioadmin" and SECRET_KEY == "minioadmin":
        logger.warning(
            "[STORAGE] MinIO usando credenciais PADRAO (minioadmin). "
            "Troque MINIO_ACCESS_KEY/MINIO_SECRET_KEY em producao."
        )


_warn_default_creds()

def _client():
    return boto3.client(
        "s3",
        endpoint_url=f"http://{ENDPOINT}",
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        region_name="us-east-1",
    )

def _ensure_one(s3, name: str):
    """Cria um bucket e libera leitura publica (GetObject p/ *)."""
    try:
        s3.head_bucket(Bucket=name)
    except ClientError:
        s3.create_bucket(Bucket=name)
        # Torna o bucket publico para leitura
        s3.put_bucket_policy(Bucket=name, Policy=f'''{{
            "Version":"2012-10-17",
            "Statement":[{{
                "Effect":"Allow",
                "Principal":"*",
                "Action":"s3:GetObject",
                "Resource":"arn:aws:s3:::{name}/*"
            }}]
        }}''')

def ensure_bucket():
    """Garante todos os buckets do app (tasks + clientes)."""
    s3 = _client()
    for b in _ALL_BUCKETS:
        _ensure_one(s3, b)

def upload_file(key: str, data: bytes, content_type: str, bucket: str | None = None) -> str:
    """Faz upload e retorna a URL publica ( Usa bucket padrao se nao for informado)."""
    b = bucket or BUCKET
    s3 = _client()
    s3.put_object(Bucket=b, Key=key, Body=data, ContentType=content_type)
    return f"{PUBLIC_URL}/{b}/{key}"

def delete_file(key: str, bucket: str | None = None):
    b = bucket or BUCKET
    s3 = _client()
    try:
        s3.delete_object(Bucket=b, Key=key)
    except ClientError:
        pass

def extract_key_from_url(url: str) -> tuple[str, str] | None:
    """Extrai (bucket, key) de uma URL publica gerada por upload_file.

    URL tem o formato: {PUBLIC_URL}/{bucket}/{key}
    Retorna None se a URL nao for reconhecida.
    """
    if not url:
        return None
    # Ex.: http://localhost:9000/clientes/{cliente_id}/{foto_id}.jpg
    # split: ['http:', '', 'host', 'bucket', 'resto...']
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