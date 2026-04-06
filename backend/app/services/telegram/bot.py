"""Telegram bot for Nini AI — Davit's personal project manager."""

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message, TelegramObject

from app.config import settings
from app.services.ai.nini_brain import NiniBrain

logger = logging.getLogger(__name__)

router = Router()
brain = NiniBrain()


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
    await message.chat.do("typing")
    response = await brain.chat(
        message.chat.id,
        "Покажи мне топ-10 самых актуальных задач, отсортированных по приоритету и дедлайну.",
    )
    await message.answer(_truncate(response))


@router.message(Command("overdue"))
async def cmd_overdue(message: Message) -> None:
    await message.chat.do("typing")
    response = await brain.chat(
        message.chat.id,
        "Покажи все просроченные задачи.",
    )
    await message.answer(_truncate(response))


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    await message.chat.do("typing")
    response = await brain.chat(
        message.chat.id,
        "Покажи общую статистику по моим задачам.",
    )
    await message.answer(_truncate(response))


@router.message(Command("briefing"))
async def cmd_briefing(message: Message) -> None:
    await message.chat.do("typing")
    response = await brain.chat(
        message.chat.id,
        "Дай мне утренний брифинг на сегодня.",
    )
    await message.answer(_truncate(response))


@router.message(F.text)
async def handle_message(message: Message) -> None:
    """Forward free-text messages to Nini Brain."""
    if not message.text:
        return
    await message.chat.do("typing")
    try:
        response = await brain.chat(message.chat.id, message.text)
        await message.answer(_truncate(response))
    except Exception as e:
        logger.exception("Error processing message")
        await message.answer(f"Блин, что-то сломалось: <code>{e}</code>")


async def start_bot() -> None:
    """Start the Telegram bot with long polling."""
    if not settings.telegram_bot_token:
        logger.warning("TELEGRAM_BOT_TOKEN not set, skipping bot startup")
        return

    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(router)

    logger.info("Starting Nini Telegram bot (long polling)")
    try:
        await dp.start_polling(bot, close_bot_session=True)
    except Exception:
        logger.exception("Telegram bot crashed")
        raise
