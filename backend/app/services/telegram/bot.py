"""Telegram bot for Nini AI — Davit's personal project manager."""

import asyncio
import logging
import random
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message, TelegramObject

from sqlalchemy import select

from app.config import settings
from app.database import async_session_factory
from app.dependencies import DAVIT_USER_ID
from app.models.workspace import Workspace
from app.services.ai.nini_brain import NiniBrain
from app.services.sync_engine import SyncEngine

# Only sync this list (Davit daily tasks)
SYNC_LIST_ID = "901410057231"

logger = logging.getLogger(__name__)

router = Router()
brain = NiniBrain()

# Global bot instance — set in start_bot(), used by proactive jobs
_bot: Bot | None = None


async def send_proactive_message(text: str) -> None:
    """Send a message to the owner without a user prompt (called by background jobs)."""
    if not _bot or not settings.telegram_owner_id:
        logger.warning("Cannot send proactive message: bot not ready or owner_id not set")
        return
    try:
        await _bot.send_message(
            chat_id=settings.telegram_owner_id,
            text=text,
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        logger.exception("Failed to send proactive Telegram message")


class OwnerOnlyMiddleware(BaseMiddleware):
    """Drop all messages from non-owner users."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, Message) and event.from_user:
            if settings.telegram_owner_id and event.from_user.id != settings.telegram_owner_id:
                logger.warning("Blocked message from user %s", event.from_user.id)
                return None
        return await handler(event, data)


router.message.middleware(OwnerOnlyMiddleware())

# Telegram has a 4096 character limit per message
TG_MAX_LENGTH = 4096


def _truncate(text: str, max_len: int = TG_MAX_LENGTH) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 20] + "\n\n... (обрезано)"


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await message.answer(
        "<b>Йо, я Нини</b> — твой проджект-менеджер.\n\n"
        "Знаю все твои задачи из ClickUp, так что не пытайся скрыть просрочки.\n\n"
        "<b>Команды:</b>\n"
        "/tasks — Топ-10 задач\n"
        "/overdue — Просроченные (надеюсь пусто)\n"
        "/stats — Статистика\n"
        "/briefing — Утренний брифинг\n"
        "/clear — Забыть наш разговор\n\n"
        "Или просто пиши — разберёмся."
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "<b>Что я умею:</b>\n\n"
        "📋 <b>Задачи</b>\n"
        "/tasks — Показать задачи (топ-10)\n"
        "/overdue — Просроченные задачи\n"
        "/stats — Статистика по компаниям и статусам\n"
        "/briefing — Утренний брифинг\n\n"
        "💬 <b>Свободный чат</b>\n"
        'Спроси что угодно: "что у меня горит?", "создай задачу для YM", '
        '"на чём сфокусироваться сегодня?"\n\n'
        "🔄 /clear — Сбросить контекст диалога"
    )


@router.message(Command("clear"))
async def cmd_clear(message: Message) -> None:
    brain.clear_history(message.chat.id)
    await message.answer("История диалога очищена. Начнём сначала!")


@router.message(Command("tasks"))
async def cmd_tasks(message: Message) -> None:
    asyncio.create_task(_track_user_activity("/tasks", "command"))
    await _auto_sync_if_needed(message)
    await message.chat.do("typing")
    response = await brain.chat(
        message.chat.id,
        "Покажи мне топ-10 самых актуальных задач, отсортированных по приоритету и дедлайну.",
    )
    await message.answer(_truncate(response))


@router.message(Command("overdue"))
async def cmd_overdue(message: Message) -> None:
    asyncio.create_task(_track_user_activity("/overdue", "command"))
    await _auto_sync_if_needed(message)
    await message.chat.do("typing")
    response = await brain.chat(
        message.chat.id,
        "Покажи все просроченные задачи.",
    )
    await message.answer(_truncate(response))


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    await _auto_sync_if_needed(message)
    await message.chat.do("typing")
    response = await brain.chat(
        message.chat.id,
        "Покажи общую статистику по моим задачам.",
    )
    await message.answer(_truncate(response))


@router.message(Command("briefing"))
async def cmd_briefing(message: Message) -> None:
    await _auto_sync_if_needed(message)
    await message.chat.do("typing")
    response = await brain.chat(
        message.chat.id,
        "Дай мне утренний брифинг на сегодня.",
    )
    await message.answer(_truncate(response))


_SYNC_CHECKING_MSGS = [
    "Сек, гляну что там...",
    "Подожди, обновляю данные 🔄",
    "Минуту, проверяю ClickUp...",
    "Давно не виделись — дай обновлюсь",
    "Сек, синкаюсь...",
]

_SYNC_NO_CHANGES_MSGS = [
    "Всё на месте, изменений нет.",
    "Без изменений с последнего раза.",
    "ClickUp тихий, всё актуально.",
    "Ничего нового — можем работать.",
    "Всё чисто, давай.",
]

_SYNC_CHANGED_MSGS = [
    "Обновил: {}.",
    "Есть изменения: {}.",
    "Поймал: {}.",
    "Свежак: {}.",
]


async def _auto_sync_if_needed(message: Message) -> bool:
    """Run incremental sync if 30+ min since last interaction. Returns True if sync ran.

    After a restart (in-memory state is empty), checks the DB workspace.last_full_sync
    instead of triggering a sync unconditionally — avoids sync storm on every deploy.
    """
    chat_id = message.chat.id

    # First message after process restart — check DB to see if recently synced
    if not brain.has_activity(chat_id):
        try:
            async with async_session_factory() as db:
                ws_result = await db.execute(
                    select(Workspace).where(
                        Workspace.user_id == DAVIT_USER_ID,
                        Workspace.sync_enabled.is_(True),
                    ).limit(1)
                )
                ws = ws_result.scalar_one_or_none()
                if ws and ws.last_full_sync:
                    last_sync = ws.last_full_sync
                    if last_sync.tzinfo is None:
                        from datetime import timezone as _tz
                        last_sync = last_sync.replace(tzinfo=_tz.utc)
                    elapsed = (datetime.now(timezone.utc) - last_sync).total_seconds()
                    if elapsed < SYNC_COOLDOWN_MINUTES * 60:
                        # Synced recently before restart — skip sync, seed in-memory timer
                        brain.touch_activity(chat_id)
                        return False
        except Exception:
            logger.debug("Could not check last_full_sync from DB", exc_info=True)

    if not brain.needs_sync(chat_id):
        brain.touch_activity(chat_id)
        return False

    brain.touch_activity(chat_id)
    await message.answer(random.choice(_SYNC_CHECKING_MSGS))
    await message.chat.do("typing")

    try:
        async with async_session_factory() as db:
            result = await db.execute(
                select(Workspace).where(
                    Workspace.user_id == DAVIT_USER_ID,
                    Workspace.sync_enabled.is_(True),
                )
            )
            workspaces = result.scalars().all()

            engine = SyncEngine(db, DAVIT_USER_ID)
            total_created, total_updated, total_archived = 0, 0, 0
            for ws in workspaces:
                try:
                    sr = await engine.sync_list_incremental(ws, SYNC_LIST_ID)
                    total_created += sr.created
                    total_updated += sr.updated
                    total_archived += sr.archived
                except Exception:
                    logger.exception("Auto-sync failed for %s", ws.name)

        parts = []
        if total_created:
            parts.append(f"+{total_created} новых")
        if total_updated:
            parts.append(f"{total_updated} обновлено")
        if total_archived:
            parts.append(f"{total_archived} в архив")
        if parts:
            await message.answer(random.choice(_SYNC_CHANGED_MSGS).format(", ".join(parts)))
        else:
            await message.answer(random.choice(_SYNC_NO_CHANGES_MSGS))
    except Exception:
        logger.exception("Auto-sync error")
        await message.answer("Синк не прошёл, но ладно — работаем с тем что есть. Что хотел?")

    return True


@router.message(F.text)
async def handle_message(message: Message) -> None:
    """Forward free-text messages to Nini Brain."""
    if not message.text:
        return

    # Track user activity for Supervisor's context-aware decisions
    asyncio.create_task(_track_user_activity(message.text, "free_text"))

    await _auto_sync_if_needed(message)
    await message.chat.do("typing")
    try:
        response = await brain.chat(message.chat.id, message.text)
        await message.answer(_truncate(response))
    except Exception as e:
        logger.exception("Error processing message")
        await message.answer(f"Блин, что-то сломалось: <code>{e}</code>")


async def _track_user_activity(text: str, category: str = "user_message") -> None:
    """Fire-and-forget: record user activity in DailyContext for the Supervisor."""
    try:
        from app.services.supervisor import record_user_activity
        await record_user_activity(text, category)
    except Exception:
        logger.debug("Activity tracking skipped", exc_info=True)


async def start_bot() -> None:
    """Start the Telegram bot with long polling."""
    global _bot

    if not settings.telegram_bot_token:
        logger.warning("TELEGRAM_BOT_TOKEN not set, skipping bot startup")
        return

    _bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(router)

    logger.info("Starting Nini Telegram bot (long polling)")
    try:
        await dp.start_polling(_bot, close_bot_session=True)
    except Exception:
        logger.exception("Telegram bot crashed")
        raise
    finally:
        _bot = None
