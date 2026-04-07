"""Async ClickUp REST API client with rate limiting."""

import asyncio
import logging
import time

import httpx

from app.services.clickup.models import (
    ClickUpFolder,
    ClickUpList,
    ClickUpSpace,
    ClickUpTask,
    ClickUpWebhook,
)

logger = logging.getLogger(__name__)

CLICKUP_API_BASE = "https://api.clickup.com/api/v2"

# ClickUp rate limit: 100 requests per minute per token
RATE_LIMIT_REQUESTS = 100
RATE_LIMIT_WINDOW = 60  # seconds


class RateLimiter:
    """Token bucket rate limiter for ClickUp API."""

    def __init__(self, max_requests: int = RATE_LIMIT_REQUESTS, window: float = RATE_LIMIT_WINDOW):
        self._max = max_requests
        self._window = window
        self._timestamps: list[float] = []
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            # Remove timestamps outside the window
            self._timestamps = [t for t in self._timestamps if now - t < self._window]
            if len(self._timestamps) >= self._max:
                sleep_time = self._window - (now - self._timestamps[0])
                logger.warning("ClickUp rate limit reached, sleeping %.1fs", sleep_time)
                await asyncio.sleep(sleep_time)
            self._timestamps.append(time.monotonic())


class ClickUpClient:
    """Async client for ClickUp REST API v2."""

    def __init__(self, api_token: str):
        self._token = api_token
        self._rate_limiter = RateLimiter()
        self._client = httpx.AsyncClient(
            base_url=CLICKUP_API_BASE,
            headers={"Authorization": api_token},
            timeout=30.0,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def _request(
        self, method: str, path: str, retries: int = 3, **kwargs
    ) -> dict | list:
        await self._rate_limiter.acquire()
        for attempt in range(retries):
            try:
                response = await self._client.request(method, path, **kwargs)
                if response.status_code == 429:
                    retry_after = float(response.headers.get("Retry-After", "5"))
                    logger.warning("ClickUp 429, retry after %.1fs", retry_after)
                    await asyncio.sleep(retry_after)
                    continue
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError:
                if attempt < retries - 1 and response.status_code >= 500:
                    await asyncio.sleep(2**attempt)
                    continue
                # Re-raise with ClickUp response body so callers can see the actual error
                try:
                    body = response.json()
                    msg = body.get("err") or body.get("error") or str(body)
                except Exception:
                    msg = response.text
                raise httpx.HTTPStatusError(
                    f"HTTP {response.status_code}: {msg}",
                    request=response.request,
                    response=response,
                ) from None
            except httpx.RequestError:
                if attempt < retries - 1:
                    await asyncio.sleep(2**attempt)
                    continue
                raise
        return {}  # unreachable, but satisfies type checker

    # === Workspace hierarchy ===

    async def get_spaces(self, team_id: str) -> list[ClickUpSpace]:
        data = await self._request("GET", f"/team/{team_id}/space", params={"archived": "false"})
        return [ClickUpSpace.model_validate(s) for s in data.get("spaces", [])]

    async def get_folders(self, space_id: str) -> list[ClickUpFolder]:
        data = await self._request(
            "GET", f"/space/{space_id}/folder", params={"archived": "false"}
        )
        return [ClickUpFolder.model_validate(f) for f in data.get("folders", [])]

    async def get_folderless_lists(self, space_id: str) -> list[ClickUpList]:
        data = await self._request(
            "GET", f"/space/{space_id}/list", params={"archived": "false"}
        )
        return [ClickUpList.model_validate(item) for item in data.get("lists", [])]

    async def get_lists(self, folder_id: str) -> list[ClickUpList]:
        data = await self._request(
            "GET", f"/folder/{folder_id}/list", params={"archived": "false"}
        )
        return [ClickUpList.model_validate(item) for item in data.get("lists", [])]

    async def get_list(self, list_id: str) -> dict:
        """Get a single list by ID (returns raw dict for flexible metadata access)."""
        data = await self._request("GET", f"/list/{list_id}")
        return data if isinstance(data, dict) else {}

    # === Tasks ===

    async def get_tasks(
        self,
        list_id: str,
        page: int = 0,
        include_closed: bool = False,
        subtasks: bool = True,
        date_updated_gt: int | None = None,
    ) -> list[ClickUpTask]:
        params: dict = {
            "page": str(page),
            "subtasks": str(subtasks).lower(),
            "include_closed": str(include_closed).lower(),
        }
        if date_updated_gt is not None:
            params["date_updated_gt"] = str(date_updated_gt)
        data = await self._request("GET", f"/list/{list_id}/task", params=params)
        return [ClickUpTask.model_validate(t) for t in data.get("tasks", [])]

    async def get_all_tasks(
        self,
        list_id: str,
        include_closed: bool = False,
        date_updated_gt: int | None = None,
    ) -> list[ClickUpTask]:
        """Paginate through all tasks in a list, optionally filtered by update time."""
        all_tasks: list[ClickUpTask] = []
        page = 0
        while True:
            tasks = await self.get_tasks(
                list_id,
                page=page,
                include_closed=include_closed,
                date_updated_gt=date_updated_gt,
            )
            if not tasks:
                break
            all_tasks.extend(tasks)
            if len(tasks) < 100:  # ClickUp returns max 100 per page
                break
            page += 1
        return all_tasks

    async def get_task(self, task_id: str) -> ClickUpTask:
        data = await self._request(
            "GET", f"/task/{task_id}", params={"include_subtasks": "true"}
        )
        return ClickUpTask.model_validate(data)

    async def update_task(self, task_id: str, data: dict) -> ClickUpTask:
        result = await self._request("PUT", f"/task/{task_id}", json=data)
        return ClickUpTask.model_validate(result)

    async def create_task(self, list_id: str, data: dict) -> ClickUpTask:
        result = await self._request("POST", f"/list/{list_id}/task", json=data)
        return ClickUpTask.model_validate(result)

    async def delete_task(self, task_id: str) -> None:
        await self._request("DELETE", f"/task/{task_id}")

    async def get_custom_fields(self, list_id: str) -> list[dict]:
        data = await self._request("GET", f"/list/{list_id}/field")
        return data.get("fields", [])

    # === Webhooks ===

    async def create_webhook(
        self, team_id: str, endpoint: str, events: list[str]
    ) -> ClickUpWebhook:
        data = await self._request(
            "POST",
            f"/team/{team_id}/webhook",
            json={"endpoint": endpoint, "events": events},
        )
        return ClickUpWebhook.model_validate(data.get("webhook", data))

    async def get_webhooks(self, team_id: str) -> list[ClickUpWebhook]:
        data = await self._request("GET", f"/team/{team_id}/webhook")
        return [ClickUpWebhook.model_validate(w) for w in data.get("webhooks", [])]

    async def delete_webhook(self, webhook_id: str) -> None:
        await self._request("DELETE", f"/webhook/{webhook_id}")
