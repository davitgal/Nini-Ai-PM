"""ClickUp webhook receiver endpoint."""

import logging
import uuid

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import WebhookVerificationError
from app.core.security import verify_clickup_signature
from app.dependencies import get_current_user_id, get_db
from app.schemas.clickup import WebhookPayload
from app.services.clickup.webhook_handler import WebhookHandler

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


@router.post("/clickup")
async def receive_clickup_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Receive and process ClickUp webhook events."""
    body = await request.body()

    # Verify signature if secret is configured
    signature = request.headers.get("X-Signature", "")
    if settings.clickup_webhook_secret:
        if not verify_clickup_signature(body, signature, settings.clickup_webhook_secret):
            raise WebhookVerificationError()

    payload = WebhookPayload.model_validate_json(body)

    handler = WebhookHandler(db, user_id)
    await handler.handle(payload)

    return Response(status_code=200)
