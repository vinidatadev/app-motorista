from uuid import UUID
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models import Task
from auth import require_user
import storage

router = APIRouter(prefix="/tasks", tags=["tasks"])

any_user = require_user()

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_SIZE = 5 * 1024 * 1024  # 5 MB

# --- Schemas ---

class TaskOut(BaseModel):
    id: UUID
    user_id: str
    title: str
    is_completed: bool
    image_url: str | None
    created_at: str

    @classmethod
    def from_orm(cls, task: Task):
        return cls(
            id=task.id,
            user_id=task.user_id,
            title=task.title,
            is_completed=task.is_completed,
            image_url=task.image_url,
            created_at=task.created_at.isoformat()
        )

class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)

class TaskUpdate(BaseModel):
    is_completed: bool

# --- Rotas ---

@router.get("/", response_model=list[TaskOut])
async def list_tasks(
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(any_user)
):
    result = await db.execute(
        select(Task)
        .where(Task.user_id == current_user["user_id"])
        .order_by(Task.created_at.desc())
    )
    return [TaskOut.from_orm(t) for t in result.scalars().all()]


@router.post("/", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
async def create_task(
    body: TaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(any_user)
):
    task = Task(title=body.title, user_id=current_user["user_id"])
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return TaskOut.from_orm(task)


@router.patch("/{task_id}", response_model=TaskOut)
async def update_task(
    task_id: UUID,
    body: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(any_user)
):
    task = await _get_own_task(db, task_id, current_user["user_id"])
    task.is_completed = body.is_completed
    await db.commit()
    await db.refresh(task)
    return TaskOut.from_orm(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(any_user)
):
    task = await _get_own_task(db, task_id, current_user["user_id"])
    await db.delete(task)
    await db.commit()


async def _get_own_task(db: AsyncSession, task_id: UUID, user_id: str) -> Task:
    """Busca tarefa e garante que pertence ao usuário logado."""
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.user_id == user_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tarefa não encontrada")
    return task


@router.post("/{task_id}/image", response_model=TaskOut)
async def upload_task_image(
    task_id: UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(any_user)
):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=422, detail="Tipo de arquivo não permitido. Use JPEG, PNG, WEBP ou GIF.")

    data = await file.read()
    if len(data) > MAX_SIZE:
        raise HTTPException(status_code=422, detail="Arquivo muito grande. Máximo 5 MB.")

    task = await _get_own_task(db, task_id, current_user["user_id"])

    ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "jpg"
    key = f"{current_user['user_id']}/{task_id}.{ext}"
    url = storage.upload_file(key, data, file.content_type)

    task.image_url = url
    await db.commit()
    await db.refresh(task)
    return TaskOut.from_orm(task)


@router.delete("/{task_id}/image", response_model=TaskOut)
async def delete_task_image(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(any_user)
):
    task = await _get_own_task(db, task_id, current_user["user_id"])
    if task.image_url:
        # Extrai a key do path após o bucket
        key = "/".join(task.image_url.split("/")[4:])
        storage.delete_file(key)
        task.image_url = None
        await db.commit()
        await db.refresh(task)
    return TaskOut.from_orm(task)
