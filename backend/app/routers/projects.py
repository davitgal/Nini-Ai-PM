"""Project/folder endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user_id, get_db
from app.models.project import Project
from app.models.task import UnifiedTask

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


@router.get("")
async def list_projects(
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """List all projects with task counts."""
    result = await db.execute(
        select(Project).where(Project.user_id == user_id, Project.is_active.is_(True))
    )
    projects = result.scalars().all()

    response = []
    for proj in projects:
        task_count = (
            await db.execute(
                select(func.count(UnifiedTask.id)).where(
                    UnifiedTask.project_id == proj.id,
                    UnifiedTask.archived.is_(False),
                )
            )
        ).scalar() or 0

        response.append(
            {
                "id": proj.id,
                "clickup_id": proj.clickup_id,
                "clickup_type": proj.clickup_type,
                "name": proj.name,
                "company_tag": proj.company_tag,
                "priority_tier": proj.priority_tier,
                "parent_id": proj.parent_id,
                "task_count": task_count,
            }
        )

    return response


@router.get("/{project_id}")
async def get_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Get a project with its task counts by status."""
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    status_counts = await db.execute(
        select(UnifiedTask.status, func.count())
        .where(UnifiedTask.project_id == project_id, UnifiedTask.archived.is_(False))
        .group_by(UnifiedTask.status)
    )

    return {
        "id": project.id,
        "clickup_id": project.clickup_id,
        "clickup_type": project.clickup_type,
        "name": project.name,
        "company_tag": project.company_tag,
        "priority_tier": project.priority_tier,
        "tasks_by_status": {row[0]: row[1] for row in status_counts},
    }


@router.patch("/{project_id}")
async def update_project(
    project_id: uuid.UUID,
    priority_tier: int | None = None,
    company_tag: str | None = None,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Update project metadata (priority tier, company tag)."""
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if priority_tier is not None:
        project.priority_tier = priority_tier
    if company_tag is not None:
        project.company_tag = company_tag

    await db.commit()
    return {"status": "updated"}
