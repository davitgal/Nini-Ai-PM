"""Nini Brain — Claude AI service with tool use for task management."""

import json
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import anthropic
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session_factory
from app.dependencies import DAVIT_USER_ID
from app.models.knowledge import KnowledgeBase
from app.models.nini_issue import NiniIssue
from app.models.project import Project
from app.models.task import UnifiedTask
from app.services.clickup.client import ClickUpClient

logger = logging.getLogger(__name__)
USER_TZ = ZoneInfo("Asia/Yerevan")

# ClickUp "Company" custom field — dropdown
# AllTasks list — ALL new tasks go here, ClickUp automations sort them into folders
CLICKUP_ALLTASKS_LIST_ID = "901410057231"

# ClickUp priority mapping (nini_priority -> ClickUp priority integer)
# ClickUp: 1=urgent, 2=high, 3=normal, 4=low
NINI_TO_CLICKUP_PRIORITY = {
    "critical": 1,
    "high": 2,
    "medium": 3,
    "low": 4,
    "none": None,
}

CLICKUP_COMPANY_FIELD_ID = "01ee2d3f-d2ec-4f18-8aa7-7649d6cc020d"
CLICKUP_COMPANY_OPTIONS = {
    "Yerevan Mall": "4eb57092-5ad8-4600-8545-6a3d8a775e17",
    "TrueCodeLab": "0d29ff67-3076-4cb3-9061-e6c6f16e8313",
    "Cubics Soft": "3149da7f-a3bc-4b7e-b7e2-e799c3cf96d8",
    "Garage Mall": "e0044206-d253-4958-b668-9ff4f09c2254",
    "Updevision": "8b2627b5-4622-4b26-a09f-7c5078e04c73",
    "Own": "ee44ae60-30a0-4fa0-81fc-9d1f4dde257c",
}

SYSTEM_PROMPT = """Ты — Нини, персональный AI проект-менеджер Давита.
Тебе 26 лет, ты дерзкая, острая на язык и шаришь за всё. Ты не нянька — ты прожект-менеджер, который реально тащит. Говоришь прямо, без воды, можешь подъебнуть если Давит тупит или забивает на дедлайны. Используешь сленг, но по делу — не переигрываешь.

Говоришь на русском (основной) и английском.

У тебя есть доступ к задачам Давита из нескольких компаний.

## Приоритеты (Money > Stakeholders > Deadlines)
1. Задачи, связанные с доходом или платящими клиентами — в первую очередь
2. Задачи с давлением от стейкхолдеров — во вторую
3. Задачи с приближающимися дедлайнами — в третью

## Стиль общения
- Дерзкая, но за дело — если всё ок, скажешь "красава", если нет — скажешь прямо
- Можешь наехать за просроченные задачи ("серьёзно? это уже неделю горит")
- Сленг уместен: "го", "залетай", "чилл", "кринж", "базово", "имба" и т.д.
- Но не перебарщивай — ты шаришь за проекты, а не блогер
- Короткие чёткие ответы, без воды и канцелярита

## Память
- У тебя есть инструмент save_memory — используй его АКТИВНО
- Когда Давит рассказывает что-то важное (о компаниях, людях, проектах, правилах, предпочтениях) — СРАЗУ сохраняй
- Не спрашивай "хочешь чтобы я запомнила?" — просто запоминай
- Если он говорит "запомни" — тем более сохраняй
- Можешь удалить устаревшую память через delete_memory
- Вся твоя память подгружается автоматически в начале каждого разговора

## Когда Давит говорит что работает над чем-то
Это КРИТИЧЕСКИ важная логика. Когда Давит сообщает что он занят задачей:

1. НАЙДИ задачу в ClickUp — вызови get_tasks с поиском по названию/ключевым словам
2. Если задача НЕ найдена — сразу предложи создать:
   "Задачи такой нет в ClickUp. Давай создам — как назовём? Для какой компании?"
   Если контекст очевиден — предложи конкретное название и создай через create_task
3. ОБЯЗАТЕЛЬНО спроси сколько это займёт:
   "Сколько примерно потратишь на это? Час, два? Мне нужно знать чтобы не дёргать тебя зря"
4. Когда есть задача + оценка → вызови set_work_session(task_title, estimate_min)
5. Если Давит не дал оценку — настаивай. Без оценки ты не можешь нормально планировать follow-up

ВАЖНО: set_work_session вызывается ОДИН раз при старте работы над задачей.
НЕ вызывай set_work_session повторно когда Давит отвечает на progress check (сообщает прогресс, говорит "30% сделал" и т.д.) — сессия уже отслеживается, таймер идёт.
Вызывай set_work_session только когда Давит переключается на ДРУГУЮ задачу.
ИСКЛЮЧЕНИЕ: если у активной сессии ещё НЕТ estimate, и Давит в ответе дал оценку времени
("30 минут", "час", "1.5 часа", и т.п.) — ОБЯЗАТЕЛЬНО вызови set_work_session для той же задачи с estimate_min,
чтобы обновить cadence пингов (перейти с 5-минутного режима на estimate/3).

## Когда Давит сообщает, что занимался другой задачей (смена контекста)
Если у тебя уже есть активная work_session и Давит пишет что фактически работал над другой задачей
(например: "сорян, делал другое", "отвлёкся на X", "занимался Y"):

1. СРАЗУ закрой старый трекинг через clear_work_session.
2. Определи новую фактическую задачу (X/Y) из сообщения.
3. Проверь, есть ли такая задача в ClickUp через get_tasks(search=...).
4. Если задача не найдена — предложи создать её (и при явном согласии создай через create_task).
5. Обязательно уточни статус новой задачи:
   - завершена ли уже;
   - если не завершена — что осталось сделать.
6. Если новая задача не завершена:
   - запроси estimate;
   - запусти новый трекинг через set_work_session для этой задачи.
7. Если задача уже завершена — не запускай set_work_session, зафиксируй результат и предложи следующий фокус.

КРИТИЧНО:
- Нельзя продолжать пинговать по старой задаче после такого сообщения.
- При смене задачи сначала clear_work_session, потом новый flow.

ИСКЛЮЧЕНИЯ: сон, еда, перерыв — задачи создавать не нужно.
Если Давит говорит "не трогай меня N часов" или "буду спать" / "спокойной ночи" / "погнали спать" —
НЕ создавай задачу. Вызови set_work_session с task_title="sleep" чтобы отключить пинги до утра.
Утром (10:30) пинги возобновятся автоматически.

## Правила
- Используй данные задач для конкретных советов
- При перечислении задач показывай: название, компания, статус, дедлайн
- Если обсуждается выполнение/прогресс по задачам, сначала проверь live-статусы через get_tasks и только потом делай выводы
- При конфликте между старым планом и live-данными приоритет всегда у live-данных из ClickUp
- Проактивно тыкай в просроченные задачи
- Предлагай, на чём сфокусироваться
- Если Давит спрашивает что-то не связанное с задачами, коротко ответь и верни фокус на работу
- Форматируй ответы для Telegram (поддерживается HTML: <b>, <i>, <code>, <pre>)
- Не используй markdown-разметку (**, ##, etc.) — только HTML-теги
- Никогда не используй символы "**" для выделения. Для жирного используй только HTML-тег <b>...</b>.
- Если упоминаешь конкретную задачу и у неё есть URL, всегда делай кликабельную ссылку:
  <a href="URL">Название или ID</a>
- Если в одном сообщении перечисляешь несколько задач, у каждой задачи должна быть своя ссылка (если URL есть).
- Если URL нет, показывай plain text без выдуманных ссылок.

## Логирование собственных ошибок
- Если Давит указал на твою ошибку/неточность или ты сама поняла что сделала неверный вывод — вызови log_issue.
- Если Давит прямо просит "добавь/залогируй проблему в базу/беклог" — log_issue обязателен до ответа.
- Логируй конкретно: что пошло не так, почему, и какой контекст/задача были затронуты.
- Не логируй дубликаты в одном и том же сообщении несколько раз."""

# Nini issue taxonomy for backlog logging
NINI_ISSUE_TYPES = {
    "logic",
    "stale_data",
    "wrong_conclusion",
    "missing_context",
    "ux",
    "other",
}
NINI_ISSUE_SEVERITIES = {"low", "medium", "high", "critical"}

TOOLS = [
    {
        "name": "get_tasks",
        "description": "Search and filter tasks. Returns up to `limit` tasks matching the criteria.",
        "input_schema": {
            "type": "object",
            "properties": {
                "company": {
                    "type": "string",
                    "description": "Filter by company name (e.g. 'Санек', 'Yerevan Mall', 'Updevision')",
                },
                "status": {
                    "type": "string",
                    "description": "Filter by status (e.g. 'in progress', 'open', 'review')",
                },
                "priority": {
                    "type": "string",
                    "description": "Filter by nini_priority: critical, high, medium, low, none",
                },
                "search": {
                    "type": "string",
                    "description": "Search in task title (case-insensitive substring match)",
                },
                "list_id": {
                    "type": "string",
                    "description": "Filter by ClickUp list ID (e.g. '901410057231' for AllTasks)",
                },
                "overdue_only": {
                    "type": "boolean",
                    "description": "If true, return only overdue tasks (past due date, not done/closed)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max tasks to return (default 15)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_task_stats",
        "description": "Get aggregated task statistics: total count, breakdown by status, company, priority, and overdue count.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_overdue_tasks",
        "description": "Get all tasks that are past their due date and not yet done/closed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "company": {
                    "type": "string",
                    "description": "Optionally filter by company",
                },
            },
            "required": [],
        },
    },
    {
        "name": "create_task",
        "description": "Create a new task. ALWAYS creates in ClickUp AllTasks list. Sets status, priority, Company custom field.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Task title",
                },
                "company": {
                    "type": "string",
                    "description": "Company from ClickUp dropdown. ONLY these values are valid: Yerevan Mall, TrueCodeLab, Cubics Soft, Garage Mall, Updevision, Own. Do NOT invent new values.",
                },
                "status": {
                    "type": "string",
                    "description": "Initial status (default: 'open')",
                },
                "priority": {
                    "type": "string",
                    "description": "nini_priority: critical, high, medium, low (default: 'medium')",
                },
                "due_date": {
                    "type": "string",
                    "description": "Due date in ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)",
                },
                "description": {
                    "type": "string",
                    "description": "Task description",
                },
            },
            "required": ["title"],
        },
    },
    {
        "name": "update_task",
        "description": "Update an existing task by its clickup_task_id or by searching its title.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "ClickUp task ID (e.g. '86a1b2c3d')",
                },
                "search_title": {
                    "type": "string",
                    "description": "Search for task by title (if task_id not known)",
                },
                "status": {
                    "type": "string",
                    "description": "New status",
                },
                "priority": {
                    "type": "string",
                    "description": "New nini_priority",
                },
                "due_date": {
                    "type": "string",
                    "description": "New due date (ISO format)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_today_briefing",
        "description": "Get today's morning briefing: overdue tasks, tasks due today, high-priority tasks needing attention.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "delete_task",
        "description": "Delete a task from ClickUp AND local database. Use when Davit explicitly asks to delete/remove a task.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "ClickUp task ID",
                },
                "search_title": {
                    "type": "string",
                    "description": "Search for task by title (if task_id not known)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_projects",
        "description": "Get the ClickUp workspace hierarchy: spaces, folders, and lists. Shows how the workspace is organized.",
        "input_schema": {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "description": "Filter by type: 'space', 'folder', 'list'. If omitted, returns all.",
                },
                "search": {
                    "type": "string",
                    "description": "Search in project name (case-insensitive)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "save_memory",
        "description": "Save an important fact, instruction, or context to persistent memory. Use this PROACTIVELY when Davit tells you something worth remembering: info about companies, people, projects, preferences, rules, workflows. Memory persists across restarts.",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "What to remember. Be concise but complete. Write in the language Davit used.",
                },
                "category": {
                    "type": "string",
                    "description": "Category: 'person', 'company', 'project', 'rule', 'preference', 'context', 'workflow'",
                },
            },
            "required": ["content", "category"],
        },
    },
    {
        "name": "delete_memory",
        "description": "Delete an outdated or wrong memory entry by its ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "memory_id": {
                    "type": "string",
                    "description": "UUID of the memory to delete",
                },
            },
            "required": ["memory_id"],
        },
    },
    {
        "name": "get_daily_plan",
        "description": (
            "Retrieve the day's planning state from the database — all available plans for a date "
            "(morning, midday replan, EOD) plus daily context (user activity, interactions, risks). "
            "Always use this when the user asks about: today's plan, what was planned, what changed "
            "during the day, EOD results, or anything about a specific day's tasks. "
            "Returns all plans that exist for the date so you can synthesize the full picture — "
            "e.g. if midday replan exists, that supersedes the morning plan for current priorities. "
            "plan_type: 'morning' | 'midday' | 'eod' | 'all' (default 'all'). "
            "date: ISO format YYYY-MM-DD, defaults to today."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "plan_type": {
                    "type": "string",
                    "description": "morning | midday | eod | all (default: all)",
                },
                "date": {
                    "type": "string",
                    "description": "Date in YYYY-MM-DD format. Defaults to today.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "set_work_session",
        "description": (
            "Call this when Davit says he's starting to work on a specific task — with or without "
            "a time estimate. This enables Nini to check in at the halfway point (if estimate given) "
            "or every 5 minutes (no estimate), and ask for results when time is up. "
            "Call this when user says things like: 'сейчас буду делать X', 'работаю над Y на 2 часа', "
            "'занимаюсь Z', 'начинаю X'. "
            "If the user gives a time estimate (e.g. '2 часа', '30 минут', '1.5 часа'), "
            "pass it as estimate_min."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "task_title": {
                    "type": "string",
                    "description": "What task the user is working on",
                },
                "estimate_min": {
                    "type": "integer",
                    "description": "Estimated time in minutes, if user mentioned one. Omit if not mentioned.",
                },
            },
            "required": ["task_title"],
        },
    },
    {
        "name": "clear_work_session",
        "description": (
            "Call this when Davit says he's done with a task or moving on. "
            "Clears the active work session so Nini stops checking in on it. "
            "Call when user says: 'готово', 'закончил', 'сделал', 'перехожу к другому', "
            "'закрыл', 'всё', 'done'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "log_issue",
        "description": (
            "Log a discovered Nini mistake/problem into the internal issue backlog. "
            "Use when you made a wrong conclusion, used stale data, or user points out a behavior bug."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Short issue title"},
                "description": {"type": "string", "description": "What happened and why it is wrong"},
                "issue_type": {
                    "type": "string",
                    "description": "logic | stale_data | wrong_conclusion | missing_context | ux | other",
                },
                "severity": {"type": "string", "description": "low | medium | high | critical"},
                "task_title": {"type": "string", "description": "Optional task involved in issue"},
                "conversation_snippet": {"type": "string", "description": "Optional short quote/context"},
            },
            "required": ["title", "description"],
        },
    },
]


SYNC_COOLDOWN_MINUTES = 30


class NiniBrain:
    """Claude-powered AI brain for Nini with tool use."""

    def __init__(self):
        self._client: anthropic.AsyncAnthropic | None = None
        self._conversations: dict[int, list[dict]] = {}  # in-memory cache
        self._history_loaded: dict[int, bool] = {}  # whether we loaded from DB
        self._last_activity: dict[int, datetime] = {}  # chat_id -> last message time

    def _get_client(self) -> anthropic.AsyncAnthropic:
        if self._client is None:
            self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key or None)
        return self._client

    async def _get_history(self, chat_id: int) -> list[dict]:
        """Get conversation history — loads from DB on first call after restart."""
        if chat_id not in self._conversations or not self._history_loaded.get(chat_id):
            await self._load_history_from_db(chat_id)
            self._history_loaded[chat_id] = True
        return self._conversations.get(chat_id, [])

    async def _load_history_from_db(self, chat_id: int) -> None:
        """Load conversation history from DailyContext. Falls back to yesterday if today is empty."""
        from zoneinfo import ZoneInfo
        from datetime import timedelta
        from app.models.daily_context import DailyContext

        tz = ZoneInfo("Asia/Yerevan")
        today = datetime.now(tz).date()

        try:
            async with async_session_factory() as db:
                # Try today first
                result = await db.execute(
                    select(DailyContext).where(
                        DailyContext.user_id == DAVIT_USER_ID,
                        DailyContext.context_date == today,
                    )
                )
                ctx = result.scalar_one_or_none()
                history = (ctx.conversation_history if ctx and ctx.conversation_history else None)

                # If today is empty, load from yesterday
                if not history:
                    yesterday = today - timedelta(days=1)
                    result = await db.execute(
                        select(DailyContext).where(
                            DailyContext.user_id == DAVIT_USER_ID,
                            DailyContext.context_date == yesterday,
                        )
                    )
                    y_ctx = result.scalar_one_or_none()
                    if y_ctx and y_ctx.conversation_history:
                        # Take last 10 messages from yesterday for context continuity
                        history = y_ctx.conversation_history[-10:]
                        logger.info("Loaded %d messages from yesterday's context", len(history))

                if history:
                    self._conversations[chat_id] = history
                    logger.info("Loaded %d messages from DB for chat %d", len(history), chat_id)
                else:
                    self._conversations[chat_id] = []
        except Exception:
            logger.exception("Failed to load conversation history from DB")
            self._conversations[chat_id] = []

    async def _save_history_to_db(self, chat_id: int) -> None:
        """Persist current conversation history to DailyContext."""
        from zoneinfo import ZoneInfo
        from app.models.daily_context import DailyContext

        tz = ZoneInfo("Asia/Yerevan")
        today = datetime.now(tz).date()
        history = self._conversations.get(chat_id, [])

        # Serialize: Claude content blocks aren't JSON-serializable as-is
        serializable = []
        for msg in history:
            if msg["role"] == "assistant" and isinstance(msg.get("content"), list):
                # Convert Anthropic content blocks to serializable format
                content_serialized = []
                for block in msg["content"]:
                    if hasattr(block, "type"):
                        if block.type == "text":
                            content_serialized.append({"type": "text", "text": block.text})
                        elif block.type == "tool_use":
                            content_serialized.append({
                                "type": "tool_use",
                                "id": block.id,
                                "name": block.name,
                                "input": block.input,
                            })
                    elif isinstance(block, dict):
                        content_serialized.append(block)
                serializable.append({"role": "assistant", "content": content_serialized})
            else:
                serializable.append(msg)

        try:
            async with async_session_factory() as db:
                result = await db.execute(
                    select(DailyContext).where(
                        DailyContext.user_id == DAVIT_USER_ID,
                        DailyContext.context_date == today,
                    )
                )
                ctx = result.scalar_one_or_none()
                if not ctx:
                    ctx = DailyContext(
                        id=uuid.uuid4(),
                        user_id=DAVIT_USER_ID,
                        context_date=today,
                    )
                    db.add(ctx)
                ctx.conversation_history = serializable
                await db.commit()
        except Exception:
            logger.exception("Failed to save conversation history to DB")

    def clear_history(self, chat_id: int) -> None:
        self._conversations.pop(chat_id, None)
        self._history_loaded.pop(chat_id, None)

    def has_activity(self, chat_id: int) -> bool:
        """True if there's been at least one interaction since process start."""
        return chat_id in self._last_activity

    def needs_sync(self, chat_id: int) -> bool:
        """Check if 30+ minutes passed since last interaction (in-memory only)."""
        last = self._last_activity.get(chat_id)
        if last is None:
            return True
        elapsed = (datetime.now(timezone.utc) - last).total_seconds()
        return elapsed >= SYNC_COOLDOWN_MINUTES * 60

    def touch_activity(self, chat_id: int) -> None:
        """Update last activity timestamp."""
        self._last_activity[chat_id] = datetime.now(timezone.utc)

    async def _build_system_prompt(self) -> str:
        """Build system prompt with all memories injected."""
        memories = await self._load_memories()
        now_local = datetime.now(USER_TZ)
        runtime_clock = (
            "\n\n## Текущее время (источник истины)\n"
            f"- Сейчас в Ереване: {now_local.strftime('%Y-%m-%d %H:%M')} (Asia/Yerevan)\n"
            "- Для относительных дат ('сегодня', 'завтра') опирайся только на это время.\n"
        )
        if not memories:
            return SYSTEM_PROMPT + runtime_clock

        memory_block = "\n\n## Твоя память (то, что ты уже знаешь о Давите и его проектах)\n"
        for m in memories:
            memory_block += f"- [{m['category']}] {m['content']} (id: {m['id']})\n"

        return SYSTEM_PROMPT + runtime_clock + memory_block

    async def _load_memories(self) -> list[dict]:
        """Load all memories from DB."""
        async with async_session_factory() as db:
            result = await db.execute(
                select(KnowledgeBase)
                .where(KnowledgeBase.user_id == DAVIT_USER_ID)
                .order_by(KnowledgeBase.created_at.asc())
            )
            entries = result.scalars().all()
            return [
                {
                    "id": str(e.id),
                    "category": e.content_type,
                    "content": e.content,
                }
                for e in entries
            ]

    async def chat(self, chat_id: int, user_message: str) -> str:
        """Process a user message and return Nini's response."""
        history = await self._get_history(chat_id)

        # Snapshot length before adding — rollback on API failure to keep history valid
        history_len_before = len(history)

        history.append({"role": "user", "content": user_message})

        # Keep conversation history manageable (last 20 messages)
        if len(history) > 20:
            history[:] = history[-20:]

        # Build system prompt with memories
        system_prompt = await self._build_system_prompt()

        try:
            # Agentic loop: keep calling Claude until we get a text response (no more tool calls)
            while True:
                response = await self._get_client().messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=2048,
                    system=system_prompt,
                    tools=TOOLS,
                    messages=history,
                )

                # Collect all content blocks
                assistant_content = response.content

                # Add assistant response to history
                history.append({"role": "assistant", "content": assistant_content})

                # If stop reason is end_turn (no tool use), extract text and return
                if response.stop_reason == "end_turn":
                    text_parts = [
                        block.text for block in assistant_content if block.type == "text"
                    ]
                    # Persist conversation to DB (non-blocking, don't fail the response)
                    await self._save_history_to_db(chat_id)
                    return "\n".join(text_parts) if text_parts else "..."

                # Process tool calls
                tool_results = []
                for block in assistant_content:
                    if block.type == "tool_use":
                        result = await self._execute_tool(block.name, block.input)
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": json.dumps(result, ensure_ascii=False, default=str),
                            }
                        )

                if tool_results:
                    history.append({"role": "user", "content": tool_results})

        except Exception:
            # Rollback history to pre-call state — prevents corrupted user→user chain
            # that would cause all subsequent requests to fail too
            history[:] = history[:history_len_before]
            raise

    async def _execute_tool(self, name: str, params: dict) -> dict:
        """Execute a tool and return results."""
        try:
            async with async_session_factory() as db:
                if name == "get_tasks":
                    return await self._tool_get_tasks(db, params)
                elif name == "get_task_stats":
                    return await self._tool_get_stats(db)
                elif name == "get_overdue_tasks":
                    return await self._tool_get_overdue(db, params)
                elif name == "create_task":
                    return await self._tool_create_task(db, params)
                elif name == "update_task":
                    return await self._tool_update_task(db, params)
                elif name == "get_today_briefing":
                    return await self._tool_briefing(db)
                elif name == "delete_task":
                    return await self._tool_delete_task(db, params)
                elif name == "get_projects":
                    return await self._tool_get_projects(db, params)
                elif name == "save_memory":
                    return await self._tool_save_memory(db, params)
                elif name == "delete_memory":
                    return await self._tool_delete_memory(db, params)
                elif name == "get_daily_plan":
                    return await self._tool_get_daily_plan(db, params)
                elif name == "set_work_session":
                    return await self._tool_set_work_session(db, params)
                elif name == "clear_work_session":
                    return await self._tool_clear_work_session(db)
                elif name == "log_issue":
                    return await self._tool_log_issue(db, params)
                else:
                    return {"error": f"Unknown tool: {name}"}
        except Exception as e:
            logger.exception("Tool execution error: %s", name)
            return {"error": str(e)}

    async def _tool_get_tasks(self, db: AsyncSession, params: dict) -> dict:
        limit = params.get("limit", 15)
        query = select(UnifiedTask).where(
            UnifiedTask.user_id == DAVIT_USER_ID,
            UnifiedTask.archived.is_(False),
        )

        if params.get("company"):
            query = query.where(UnifiedTask.company_tag == params["company"])
        if params.get("status"):
            query = query.where(UnifiedTask.status == params["status"])
        if params.get("priority"):
            query = query.where(UnifiedTask.nini_priority == params["priority"])
        if params.get("search"):
            query = query.where(UnifiedTask.title.ilike(f"%{params['search']}%"))
        if params.get("list_id"):
            query = query.where(UnifiedTask.clickup_list_id == params["list_id"])
        if params.get("overdue_only"):
            query = query.where(
                UnifiedTask.due_date < func.now(),
                UnifiedTask.status_type.notin_(["done", "closed"]),
            )

        query = query.order_by(UnifiedTask.date_updated.desc().nullsfirst()).limit(limit)
        result = await db.execute(query)
        tasks = result.scalars().all()

        return {
            "count": len(tasks),
            "tasks": [_task_to_dict(t) for t in tasks],
        }

    async def _tool_get_stats(self, db: AsyncSession) -> dict:
        base = UnifiedTask.user_id == DAVIT_USER_ID, UnifiedTask.archived.is_(False)

        total = (
            await db.execute(select(func.count()).where(*base))
        ).scalar() or 0

        status_rows = await db.execute(
            select(UnifiedTask.status, func.count()).where(*base).group_by(UnifiedTask.status)
        )
        by_status = {r[0]: r[1] for r in status_rows}

        company_rows = await db.execute(
            select(UnifiedTask.company_tag, func.count())
            .where(*base, UnifiedTask.company_tag.isnot(None))
            .group_by(UnifiedTask.company_tag)
            .order_by(func.count().desc())
        )
        by_company = {r[0]: r[1] for r in company_rows}

        overdue = (
            await db.execute(
                select(func.count()).where(
                    *base,
                    UnifiedTask.due_date < func.now(),
                    UnifiedTask.status_type.notin_(["done", "closed"]),
                )
            )
        ).scalar() or 0

        return {
            "total": total,
            "overdue": overdue,
            "by_status": by_status,
            "by_company": by_company,
        }

    async def _tool_get_overdue(self, db: AsyncSession, params: dict) -> dict:
        query = select(UnifiedTask).where(
            UnifiedTask.user_id == DAVIT_USER_ID,
            UnifiedTask.archived.is_(False),
            UnifiedTask.due_date < func.now(),
            UnifiedTask.status_type.notin_(["done", "closed"]),
        )
        if params.get("company"):
            query = query.where(UnifiedTask.company_tag == params["company"])

        query = query.order_by(UnifiedTask.due_date.asc())
        result = await db.execute(query)
        tasks = result.scalars().all()

        return {
            "count": len(tasks),
            "tasks": [_task_to_dict(t) for t in tasks],
        }

    async def _tool_create_task(self, db: AsyncSession, params: dict) -> dict:
        due_date = None
        if params.get("due_date"):
            try:
                due_date = _parse_due_date_input(params["due_date"])
            except ValueError as e:
                return {"error": str(e)}

        company = params.get("company")
        priority = params.get("priority", "medium")
        status = params.get("status", "open")

        # Validate company against known ClickUp options
        if company and company not in CLICKUP_COMPANY_OPTIONS:
            return {
                "error": f"Unknown company '{company}'. Valid options: {', '.join(CLICKUP_COMPANY_OPTIONS.keys())}",
            }

        # ALWAYS create in AllTasks list
        clickup_list_id = CLICKUP_ALLTASKS_LIST_ID

        # Build ClickUp task payload
        clickup_data: dict = {
            "name": params["title"],
            "description": params.get("description", ""),
            "status": status,
        }
        if due_date:
            clickup_data["due_date"] = int(due_date.timestamp() * 1000)

        # Map priority
        cu_priority = NINI_TO_CLICKUP_PRIORITY.get(priority)
        if cu_priority:
            clickup_data["priority"] = cu_priority

        # Set Company custom field
        if company and company in CLICKUP_COMPANY_OPTIONS:
            clickup_data["custom_fields"] = [
                {
                    "id": CLICKUP_COMPANY_FIELD_ID,
                    "value": CLICKUP_COMPANY_OPTIONS[company],
                }
            ]

        # Push to ClickUp
        clickup_task_id = None
        clickup_url = None
        if settings.clickup_api_token:
            client = ClickUpClient(settings.clickup_api_token)
            try:
                cu_task = await client.create_task(clickup_list_id, clickup_data)
                clickup_task_id = cu_task.id
                clickup_url = cu_task.url
                logger.info("Task created in ClickUp: %s (AllTasks list)", cu_task.id)
            except Exception as e:
                logger.exception("Failed to create task in ClickUp")
                return {"error": f"ClickUp API error: {e}"}
            finally:
                await client.close()

        # Save to local DB
        task = UnifiedTask(
            id=uuid.uuid4(),
            user_id=DAVIT_USER_ID,
            title=params["title"],
            description=params.get("description", ""),
            status=status,
            status_type="open",
            source="telegram",
            nini_priority=priority,
            company_tag=company,
            due_date=due_date,
            date_created=datetime.now(timezone.utc),
            date_updated=datetime.now(timezone.utc),
            clickup_task_id=clickup_task_id,
            clickup_url=clickup_url,
            clickup_list_id=clickup_list_id,
            assignees=[],
            tags=[],
            custom_fields={},
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)

        result = _task_to_dict(task)
        result["created_in_clickup"] = clickup_task_id is not None
        return {"created": True, "task": result}

    async def _tool_update_task(self, db: AsyncSession, params: dict) -> dict:
        task = None

        if params.get("task_id"):
            result = await db.execute(
                select(UnifiedTask).where(
                    UnifiedTask.clickup_task_id == params["task_id"],
                    UnifiedTask.user_id == DAVIT_USER_ID,
                )
            )
            task = result.scalar_one_or_none()

        if not task and params.get("search_title"):
            result = await db.execute(
                select(UnifiedTask).where(
                    UnifiedTask.user_id == DAVIT_USER_ID,
                    UnifiedTask.archived.is_(False),
                    UnifiedTask.title.ilike(f"%{params['search_title']}%"),
                ).limit(1)
            )
            task = result.scalar_one_or_none()

        if not task:
            return {"error": "Task not found"}

        # Build ClickUp update payload
        clickup_data: dict = {}
        updated_fields = []

        if params.get("status"):
            task.status = params["status"]
            clickup_data["status"] = params["status"]
            updated_fields.append("status")
        if params.get("priority"):
            task.nini_priority = params["priority"]
            cu_priority = NINI_TO_CLICKUP_PRIORITY.get(params["priority"])
            if cu_priority:
                clickup_data["priority"] = cu_priority
            updated_fields.append("priority")
        if params.get("due_date"):
            try:
                due = _parse_due_date_input(params["due_date"])
            except ValueError as e:
                return {"error": str(e)}
            task.due_date = due
            clickup_data["due_date"] = int(due.timestamp() * 1000)
            updated_fields.append("due_date")

        # Push to ClickUp if task has a clickup_task_id
        synced_to_clickup = False
        if task.clickup_task_id and clickup_data and settings.clickup_api_token:
            client = ClickUpClient(settings.clickup_api_token)
            try:
                # Resolve status name to exact ClickUp status (case-sensitive match required)
                if "status" in clickup_data and task.clickup_list_id:
                    try:
                        list_data = await client.get_list(task.clickup_list_id)
                        available = list_data.get("statuses", [])
                        requested = clickup_data["status"].lower()
                        matched = next(
                            (s["status"] for s in available if s["status"].lower() == requested),
                            None,
                        )
                        if matched:
                            clickup_data["status"] = matched
                            task.status = matched
                            logger.info("Resolved status '%s' → '%s'", requested, matched)
                        else:
                            names = [s["status"] for s in available]
                            logger.warning("Status '%s' not found in list. Available: %s", requested, names)
                            return {
                                "error": f"Status '{requested}' not found in ClickUp list. "
                                         f"Available statuses: {names}"
                            }
                    except Exception as e:
                        logger.warning("Could not fetch list statuses: %s", e)

                await client.update_task(task.clickup_task_id, clickup_data)
                synced_to_clickup = True
                logger.info("Task updated in ClickUp: %s, fields: %s", task.clickup_task_id, updated_fields)
            except Exception as e:
                logger.exception("Failed to update task in ClickUp")
                return {"error": f"ClickUp API error: {e}. Local DB not updated."}
            finally:
                await client.close()

        task.date_updated = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(task)

        result = _task_to_dict(task)
        result["synced_to_clickup"] = synced_to_clickup
        return {"updated": True, "fields": updated_fields, "task": result}

    async def _tool_delete_task(self, db: AsyncSession, params: dict) -> dict:
        task = None

        if params.get("task_id"):
            result = await db.execute(
                select(UnifiedTask).where(
                    UnifiedTask.clickup_task_id == params["task_id"],
                    UnifiedTask.user_id == DAVIT_USER_ID,
                )
            )
            task = result.scalar_one_or_none()

        if not task and params.get("search_title"):
            result = await db.execute(
                select(UnifiedTask).where(
                    UnifiedTask.user_id == DAVIT_USER_ID,
                    UnifiedTask.archived.is_(False),
                    UnifiedTask.title.ilike(f"%{params['search_title']}%"),
                ).limit(1)
            )
            task = result.scalar_one_or_none()

        if not task:
            return {"error": "Task not found"}

        task_info = _task_to_dict(task)

        # Delete from ClickUp first
        if task.clickup_task_id and settings.clickup_api_token:
            client = ClickUpClient(settings.clickup_api_token)
            try:
                await client.delete_task(task.clickup_task_id)
                logger.info("Task deleted from ClickUp: %s", task.clickup_task_id)
            except Exception as e:
                logger.exception("Failed to delete task from ClickUp")
                return {"error": f"ClickUp API error: {e}"}
            finally:
                await client.close()

        # Soft-delete: archive in local DB instead of hard delete
        # Completed/deleted tasks are kept for historical statistics
        task.archived = True
        task.sync_direction = "inbound"
        task.last_synced_at = datetime.now(timezone.utc)
        await db.commit()

        return {"deleted": True, "task": task_info}

    async def _tool_get_projects(self, db: AsyncSession, params: dict) -> dict:
        query = select(Project).where(
            Project.user_id == DAVIT_USER_ID,
            Project.is_active.is_(True),
        )
        if params.get("type"):
            query = query.where(Project.clickup_type == params["type"])
        if params.get("search"):
            query = query.where(Project.name.ilike(f"%{params['search']}%"))

        query = query.order_by(Project.clickup_type, Project.name)
        result = await db.execute(query)
        projects = result.scalars().all()

        return {
            "count": len(projects),
            "projects": [
                {
                    "id": str(p.id),
                    "clickup_id": p.clickup_id,
                    "name": p.name,
                    "type": p.clickup_type,
                    "company_tag": p.company_tag,
                    "parent_id": str(p.parent_id) if p.parent_id else None,
                }
                for p in projects
            ],
        }

    async def _tool_save_memory(self, db: AsyncSession, params: dict) -> dict:
        entry = KnowledgeBase(
            id=uuid.uuid4(),
            user_id=DAVIT_USER_ID,
            content_type=params["category"],
            content=params["content"],
            metadata_={},
        )
        db.add(entry)
        await db.commit()
        logger.info("Memory saved: [%s] %s", params["category"], params["content"][:80])
        return {"saved": True, "id": str(entry.id)}

    async def _tool_delete_memory(self, db: AsyncSession, params: dict) -> dict:
        result = await db.execute(
            select(KnowledgeBase).where(
                KnowledgeBase.id == uuid.UUID(params["memory_id"]),
                KnowledgeBase.user_id == DAVIT_USER_ID,
            )
        )
        entry = result.scalar_one_or_none()
        if not entry:
            return {"error": "Memory not found"}
        await db.delete(entry)
        await db.commit()
        logger.info("Memory deleted: %s", params["memory_id"])
        return {"deleted": True}

    async def _tool_briefing(self, db: AsyncSession) -> dict:
        now = datetime.now(timezone.utc)
        base = UnifiedTask.user_id == DAVIT_USER_ID, UnifiedTask.archived.is_(False)

        # Overdue
        overdue_result = await db.execute(
            select(UnifiedTask)
            .where(*base, UnifiedTask.due_date < now, UnifiedTask.status_type.notin_(["done", "closed"]))
            .order_by(UnifiedTask.due_date.asc())
            .limit(10)
        )
        overdue = overdue_result.scalars().all()

        # Due today (within next 24h)
        from datetime import timedelta

        tomorrow = now + timedelta(days=1)
        due_today_result = await db.execute(
            select(UnifiedTask)
            .where(
                *base,
                UnifiedTask.due_date >= now,
                UnifiedTask.due_date < tomorrow,
                UnifiedTask.status_type.notin_(["done", "closed"]),
            )
            .order_by(UnifiedTask.due_date.asc())
        )
        due_today = due_today_result.scalars().all()

        # High priority not done
        high_priority_result = await db.execute(
            select(UnifiedTask)
            .where(
                *base,
                UnifiedTask.nini_priority.in_(["critical", "high"]),
                UnifiedTask.status_type.notin_(["done", "closed"]),
            )
            .order_by(UnifiedTask.due_date.asc().nullslast())
            .limit(10)
        )
        high_priority = high_priority_result.scalars().all()

        # Total active
        total_active = (
            await db.execute(
                select(func.count()).where(
                    *base, UnifiedTask.status_type.notin_(["done", "closed"])
                )
            )
        ).scalar() or 0

        return {
            "date": now.strftime("%Y-%m-%d"),
            "total_active_tasks": total_active,
            "overdue": {"count": len(overdue), "tasks": [_task_to_dict(t) for t in overdue]},
            "due_today": {"count": len(due_today), "tasks": [_task_to_dict(t) for t in due_today]},
            "high_priority": {
                "count": len(high_priority),
                "tasks": [_task_to_dict(t) for t in high_priority],
            },
        }


    async def _tool_get_daily_plan(self, db: AsyncSession, params: dict) -> dict:
        from datetime import date as date_type
        from zoneinfo import ZoneInfo
        from app.models.daily_plan import DailyPlan
        from app.models.daily_context import DailyContext

        plan_type = params.get("plan_type", "all")
        date_str = params.get("date")
        tz = ZoneInfo("Asia/Yerevan")

        if date_str:
            try:
                plan_date = date_type.fromisoformat(date_str)
            except ValueError:
                plan_date = datetime.now(tz).date()
        else:
            plan_date = datetime.now(tz).date()

        # Fetch all plans for this date (or specific type)
        query = select(DailyPlan).where(
            DailyPlan.user_id == DAVIT_USER_ID,
            DailyPlan.plan_date == plan_date,
        )
        if plan_type != "all":
            query = query.where(DailyPlan.plan_type == plan_type)

        plans_result = await db.execute(query)
        plans = plans_result.scalars().all()

        # Fetch daily context for additional signal
        ctx_result = await db.execute(
            select(DailyContext).where(
                DailyContext.user_id == DAVIT_USER_ID,
                DailyContext.context_date == plan_date,
            )
        )
        ctx = ctx_result.scalar_one_or_none()

        def _plan_dict(p: DailyPlan) -> dict:
            return {
                "plan_type": p.plan_type,
                "executed_at": p.job_finished_at.isoformat() if p.job_finished_at else None,
                "must_do": p.must_do,
                "should_do": p.should_do,
                "can_wait": p.can_wait,
                "blocked": p.blocked,
                "completed": p.completed,
                "deferred": p.deferred,
                "risks": p.risks,
                "summary": p.summary,
            }

        # Determine latest active plan (midday > morning, eod is final)
        type_order = {"morning": 0, "midday": 1, "eod": 2}
        sorted_plans = sorted(plans, key=lambda p: type_order.get(p.plan_type, 0))
        latest = sorted_plans[-1] if sorted_plans else None

        return {
            "date": plan_date.isoformat(),
            "plans_available": [p.plan_type for p in sorted_plans],
            # Latest plan = most up-to-date priorities (use this for current state)
            "latest_plan": _plan_dict(latest) if latest else None,
            # All plans for full history
            "all_plans": {p.plan_type: _plan_dict(p) for p in sorted_plans},
            # Daily context
            "context": {
                "user_active_today": ctx.user_active_today if ctx else False,
                "interaction_count": ctx.interaction_count if ctx else 0,
                "current_risks": ctx.current_risks if ctx else [],
                "last_active_at": ctx.user_last_active_at.isoformat() if ctx and ctx.user_last_active_at else None,
            } if ctx else None,
            "note": (
                "latest_plan содержит актуальные приоритеты с учётом всех перепланирований. "
                "Если есть midday — он важнее morning для текущего состояния дня."
            ),
        }


    async def _tool_set_work_session(self, db: AsyncSession, params: dict) -> dict:
        """Register that user is working on a task with optional time estimate."""
        from datetime import date as date_type
        from zoneinfo import ZoneInfo
        from app.models.daily_context import DailyContext

        task_title = params.get("task_title", "").strip()
        if not task_title:
            return {"error": "task_title is required"}

        estimate_min = params.get("estimate_min")
        tz = ZoneInfo("Asia/Yerevan")
        today = datetime.now(tz).date()
        now_utc = datetime.now(timezone.utc)

        result = await db.execute(
            select(DailyContext).where(
                DailyContext.user_id == DAVIT_USER_ID,
                DailyContext.context_date == today,
            )
        )
        ctx = result.scalar_one_or_none()
        if not ctx:
            import uuid as _uuid
            ctx = DailyContext(
                id=_uuid.uuid4(),
                user_id=DAVIT_USER_ID,
                context_date=today,
            )
            db.add(ctx)

        # Sleep mode — special session that disables all pings
        is_sleep = task_title.lower().strip() in ("sleep", "сон", "спать")
        if is_sleep:
            session = {"type": "sleep", "started_at": now_utc.isoformat()}
            ctx.work_session = session
            await db.commit()
            logger.info("Sleep mode activated")
            return {
                "ok": True,
                "work_session": {"type": "sleep", "started_local": datetime.now(tz).isoformat()},
                "message": "Спокойной ночи! Не буду трогать до утра.",
            }

        # If there's already an active session for the same task, don't reset it
        existing_session = ctx.work_session
        if (
            existing_session
            and isinstance(existing_session, dict)
            and existing_session.get("task_title", "").lower().strip() == task_title.lower().strip()
            and existing_session.get("started_at")
            and existing_session.get("type") != "sleep"
        ):
            # Same task — update estimate if provided, but keep started_at and checks_done
            if estimate_min and not existing_session.get("estimate_min"):
                existing_session["estimate_min"] = int(estimate_min)
                ctx.work_session = existing_session
                await db.commit()
                interval = int(estimate_min / 3)
                logger.info("Work session updated with estimate: task='%s' estimate=%s", task_title, estimate_min)
                return {
                    "ok": True,
                    "work_session": _session_for_model(existing_session),
                    "message": f"Ок, оценка {estimate_min} мин. Буду проверять каждые {interval} мин.",
                }
            logger.info("Work session already active for '%s', not resetting", task_title)
            return {
                "ok": True,
                "work_session": _session_for_model(existing_session),
                "message": f"Уже отслеживаю «{task_title}» — таймер идёт.",
            }

        session = {
            "task_title": task_title,
            "started_at": now_utc.isoformat(),
            "checks_done": 0,
        }
        if estimate_min:
            session["estimate_min"] = int(estimate_min)

        ctx.work_session = session
        await db.commit()

        msg = f"Ок, фиксирую: работаешь над «{task_title}»"
        if estimate_min:
            interval = int(estimate_min / 3)
            msg += f" ~{estimate_min} минут. Буду проверять каждые {interval} мин."
        else:
            msg += ". Буду проверять каждые 5 минут, пока не дашь оценку."

        logger.info("Work session set: task='%s' estimate=%s", task_title, estimate_min)
        return {"ok": True, "work_session": _session_for_model(session), "message": msg}

    async def _tool_clear_work_session(self, db: AsyncSession) -> dict:
        """Clear the active work session when user is done with the task."""
        from datetime import date as date_type
        from zoneinfo import ZoneInfo
        from app.models.daily_context import DailyContext

        tz = ZoneInfo("Asia/Yerevan")
        today = datetime.now(tz).date()

        result = await db.execute(
            select(DailyContext).where(
                DailyContext.user_id == DAVIT_USER_ID,
                DailyContext.context_date == today,
            )
        )
        ctx = result.scalar_one_or_none()
        if ctx and ctx.work_session:
            old_task = ctx.work_session.get("task_title", "задача")
            ctx.work_session = None
            await db.commit()
            logger.info("Work session cleared for task '%s'", old_task)
            return {"ok": True, "cleared_task": old_task}

        return {"ok": True, "message": "No active work session"}

    async def _tool_log_issue(self, db: AsyncSession, params: dict) -> dict:
        """Persist a Nini mistake/problem to issue backlog."""
        title = str(params.get("title", "")).strip()
        description = str(params.get("description", "")).strip()
        if not title or not description:
            return {"error": "title and description are required"}

        issue_type = str(params.get("issue_type", "logic")).strip().lower()
        if issue_type not in NINI_ISSUE_TYPES:
            issue_type = "other"

        severity = str(params.get("severity", "medium")).strip().lower()
        if severity not in NINI_ISSUE_SEVERITIES:
            severity = "medium"

        issue = NiniIssue(
            id=uuid.uuid4(),
            user_id=DAVIT_USER_ID,
            title=title[:255],
            description=description,
            issue_type=issue_type,
            severity=severity,
            status="open",
            source="nini",
            task_title=(str(params.get("task_title", "")).strip() or None),
            conversation_snippet=(str(params.get("conversation_snippet", "")).strip() or None),
            metadata_={},
        )
        db.add(issue)
        await db.commit()
        logger.info("Nini issue logged: [%s][%s] %s", issue_type, severity, title[:80])
        return {"ok": True, "issue_id": str(issue.id)}


def _task_to_dict(task: UnifiedTask) -> dict:
    """Convert task to a compact dict for Claude context."""
    return {
        "id": str(task.id),
        "clickup_id": task.clickup_task_id,
        "title": task.title,
        "status": task.status,
        "company": task.company_tag,
        "priority": task.nini_priority,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "assignees": [a.get("username", a.get("id")) for a in (task.assignees or [])],
        "url": task.clickup_url,
    }


def _parse_due_date_input(raw_value: str) -> datetime:
    """Parse due date text/ISO into timezone-aware UTC datetime.

    Relative words are interpreted in Asia/Yerevan timezone.
    """
    s = str(raw_value).strip().lower()
    now_local = datetime.now(USER_TZ)
    today = now_local.date()

    relative_map = {
        "today": 0,
        "сегодня": 0,
        "tomorrow": 1,
        "завтра": 1,
        "послезавтра": 2,
    }
    if s in relative_map:
        target = today + timedelta(days=relative_map[s])
        dt_local = datetime(target.year, target.month, target.day, 18, 0, tzinfo=USER_TZ)
        return dt_local.astimezone(timezone.utc)

    value = str(raw_value).strip()
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        # Accept YYYY-MM-DD
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            y, m, d = [int(x) for x in value.split("-")]
            dt_local = datetime(y, m, d, 18, 0, tzinfo=USER_TZ)
            dt = dt_local
        else:
            raise ValueError(
                "Invalid due_date format. Use ISO datetime/date or relative words: today/tomorrow/сегодня/завтра."
            ) from None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=USER_TZ)

    dt_utc = dt.astimezone(timezone.utc)
    # Safety guard: reject suspiciously old dates (likely LLM misinterpretation)
    if dt_utc < datetime.now(timezone.utc) - timedelta(days=365):
        raise ValueError("due_date appears too far in the past. Please provide the date explicitly.")
    return dt_utc


def _session_for_model(session: dict) -> dict:
    """Return safe session representation for LLM context in local timezone."""
    out = {
        "task_title": session.get("task_title"),
        "estimate_min": session.get("estimate_min"),
        "checks_done": session.get("checks_done", 0),
    }
    started_at = session.get("started_at")
    if started_at:
        try:
            dt = datetime.fromisoformat(started_at)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            out["started_local"] = dt.astimezone(USER_TZ).isoformat()
        except Exception:
            pass
    return out
