"""Nini issue backlog endpoints."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user_id, get_db
from app.models.nini_issue import NiniIssue
from app.schemas.nini_issue import (
    NiniIssueCreate,
    NiniIssueListResponse,
    NiniIssueResponse,
    NiniIssueUpdate,
)

router = APIRouter(prefix="/api/v1/nini-issues", tags=["nini-issues"])


def _to_response(issue: NiniIssue) -> NiniIssueResponse:
    """Map ORM model to API schema explicitly."""
    return NiniIssueResponse(
        id=issue.id,
        title=issue.title,
        description=issue.description,
        issue_type=issue.issue_type,
        severity=issue.severity,
        status=issue.status,
        source=issue.source,
        task_title=issue.task_title,
        conversation_snippet=issue.conversation_snippet,
        metadata=issue.metadata_ or {},
        resolved_at=issue.resolved_at,
        resolution_notes=issue.resolution_notes,
        created_at=issue.created_at,
        updated_at=issue.updated_at,
    )


@router.get("", response_model=NiniIssueListResponse)
async def list_nini_issues(
    status: str | None = None,
    severity: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    query = select(NiniIssue).where(NiniIssue.user_id == user_id)
    if status:
        query = query.where(NiniIssue.status == status)
    if severity:
        query = query.where(NiniIssue.severity == severity)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(NiniIssue.created_at.desc()).limit(limit)
    rows = (await db.execute(query)).scalars().all()
    return NiniIssueListResponse(
        items=[_to_response(i) for i in rows],
        total=total,
    )


@router.post("", response_model=NiniIssueResponse)
async def create_nini_issue(
    payload: NiniIssueCreate,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    issue = NiniIssue(
        user_id=user_id,
        title=payload.title.strip(),
        description=payload.description.strip(),
        issue_type=payload.issue_type.strip().lower(),
        severity=payload.severity.strip().lower(),
        status="open",
        source=payload.source.strip().lower(),
        task_title=payload.task_title.strip() if payload.task_title else None,
        conversation_snippet=payload.conversation_snippet.strip() if payload.conversation_snippet else None,
        metadata_=payload.metadata,
    )
    db.add(issue)
    await db.commit()
    await db.refresh(issue)
    return _to_response(issue)


@router.patch("/{issue_id}", response_model=NiniIssueResponse)
async def update_nini_issue(
    issue_id: uuid.UUID,
    payload: NiniIssueUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    issue = (
        await db.execute(
            select(NiniIssue).where(
                NiniIssue.id == issue_id,
                NiniIssue.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    updates = payload.model_dump(exclude_unset=True)
    if "severity" in updates and updates["severity"] is not None:
        issue.severity = updates["severity"].strip().lower()
    if "resolution_notes" in updates:
        issue.resolution_notes = updates["resolution_notes"]
    if "status" in updates and updates["status"] is not None:
        new_status = updates["status"].strip().lower()
        issue.status = new_status
        if new_status in {"fixed", "done", "resolved", "ignored"}:
            issue.resolved_at = datetime.now(timezone.utc)
        elif new_status in {"open", "in_progress"}:
            issue.resolved_at = None

    await db.commit()
    await db.refresh(issue)
    return _to_response(issue)
