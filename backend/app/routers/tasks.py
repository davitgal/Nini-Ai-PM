"""Task CRUD and query endpoints."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user_id, get_db
from app.models.task import UnifiedTask
from app.schemas.task import TaskListResponse, TaskResponse, TaskStatsResponse, TaskUpdate
from app.services.clickup.task_sync import OutboundSync

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    company: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    workspace_id: uuid.UUID | None = None,
    space_name: str | None = None,
    list_name: str | None = None,
    due_before: datetime | None = None,
    due_after: datetime | None = None,
    search: str | None = None,
    sort_by: str = "date_updated",
    sort_order: str = "desc",
    page: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """List tasks with filters and pagination."""
    query = select(UnifiedTask).where(
        UnifiedTask.user_id == user_id,
        UnifiedTask.archived.is_(False),
    )

    if company:
        query = query.where(UnifiedTask.company_tag == company)
    if status:
        query = query.where(UnifiedTask.status == status)
    if priority:
        query = query.where(UnifiedTask.nini_priority == priority)
    if workspace_id:
        query = query.where(UnifiedTask.workspace_id == workspace_id)
    if space_name:
        query = query.where(UnifiedTask.space_name == space_name)
    if list_name:
        query = query.where(UnifiedTask.list_name == list_name)
    if due_before:
        query = query.where(UnifiedTask.due_date <= due_before)
    if due_after:
        query = query.where(UnifiedTask.due_date >= due_after)
    if search:
        query = query.where(UnifiedTask.title.ilike(f"%{search}%"))

    # Count total before pagination
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Sorting
    sort_col = getattr(UnifiedTask, sort_by, UnifiedTask.date_updated)
    if sort_order == "asc":
        query = query.order_by(sort_col.asc().nullslast())
    else:
        query = query.order_by(sort_col.desc().nullsfirst())

    # Pagination
    query = query.offset(page * limit).limit(limit)

    result = await db.execute(query)
    tasks = result.scalars().all()

    return TaskListResponse(
        tasks=[TaskResponse.model_validate(t) for t in tasks],
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/stats", response_model=TaskStatsResponse)
async def task_stats(
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Get task statistics."""
    base = select(UnifiedTask).where(
        UnifiedTask.user_id == user_id,
        UnifiedTask.archived.is_(False),
    )

    # Total
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0

    # By status
    status_rows = await db.execute(
        select(UnifiedTask.status, func.count())
        .where(UnifiedTask.user_id == user_id, UnifiedTask.archived.is_(False))
        .group_by(UnifiedTask.status)
    )
    by_status = {row[0]: row[1] for row in status_rows}

    # By company
    company_rows = await db.execute(
        select(UnifiedTask.company_tag, func.count())
        .where(
            UnifiedTask.user_id == user_id,
            UnifiedTask.archived.is_(False),
            UnifiedTask.company_tag.isnot(None),
        )
        .group_by(UnifiedTask.company_tag)
    )
    by_company = {row[0]: row[1] for row in company_rows}

    # By nini priority
    priority_rows = await db.execute(
        select(UnifiedTask.nini_priority, func.count())
        .where(UnifiedTask.user_id == user_id, UnifiedTask.archived.is_(False))
        .group_by(UnifiedTask.nini_priority)
    )
    by_priority = {row[0]: row[1] for row in priority_rows}

    # Overdue
    overdue = (
        await db.execute(
            select(func.count())
            .where(
                UnifiedTask.user_id == user_id,
                UnifiedTask.archived.is_(False),
                UnifiedTask.due_date < func.now(),
                UnifiedTask.status_type.notin_(["done", "closed"]),
            )
        )
    ).scalar() or 0

    return TaskStatsResponse(
        total=total,
        by_status=by_status,
        by_company=by_company,
        by_priority=by_priority,
        overdue=overdue,
    )


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Get a single task."""
    result = await db.execute(
        select(UnifiedTask).where(
            UnifiedTask.id == task_id,
            UnifiedTask.user_id == user_id,
        )
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskResponse.model_validate(task)


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: uuid.UUID,
    updates: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Update a task locally."""
    result = await db.execute(
        select(UnifiedTask).where(
            UnifiedTask.id == task_id,
            UnifiedTask.user_id == user_id,
        )
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    update_data = updates.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(task, key, value)

    await db.commit()
    await db.refresh(task)
    return TaskResponse.model_validate(task)


@router.post("/{task_id}/sync-to-clickup")
async def sync_task_to_clickup(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Push local task changes to ClickUp."""
    sync = OutboundSync(db, user_id)
    result = await sync.push_task_to_clickup(task_id)
    return {"status": result}
