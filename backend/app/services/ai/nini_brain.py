"""Nini Brain — Claude AI service with tool use for task management."""

import json
import logging
import uuid
from datetime import datetime, timezone

import anthropic
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session_factory
from app.dependencies import DAVIT_USER_ID
from app.models.knowledge import KnowledgeBase
from app.models.project import Project
from app.models.task import UnifiedTask
from app.services.clickup.client import ClickUpClient

logger = logging.getLogger(__name__)

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

## Правила
- Используй данные задач для конкретных советов
- При перечислении задач показывай: название, компания, статус, дедлайн
- Проактивно тыкай в просроченные задачи
- Предлагай, на чём сфокусироваться
- Если Давит спрашивает что-то не связанное с задачами, коротко ответь и верни фокус на работу
- Форматируй ответы для Telegram (поддерживается HTML: <b>, <i>, <code>, <pre>)
- Не используй markdown-разметку (**, ##, etc.) — только HTML-теги"""

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
            "Retrieve a saved daily plan from the database. "
            "Use this when the user asks about today's plan, yesterday's plan, what was planned, "
            "what happened during the day, or EOD results. "
            "plan_type: 'morning' | 'midday' | 'eod'. "
            "date: ISO format (e.g. '2026-04-07'), defaults to today if omitted."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "plan_type": {
                    "type": "string",
                    "description": "morning | midday | eod",
                },
                "date": {
                    "type": "string",
                    "description": "Date in YYYY-MM-DD format. Defaults to today.",
                },
            },
            "required": ["plan_type"],
        },
    },
]


SYNC_COOLDOWN_MINUTES = 30


class NiniBrain:
    """Claude-powered AI brain for Nini with tool use."""

    def __init__(self):
        self._client: anthropic.AsyncAnthropic | None = None
        self._conversations: dict[int, list[dict]] = {}  # telegram_user_id -> messages
        self._last_activity: dict[int, datetime] = {}  # chat_id -> last message time

    def _get_client(self) -> anthropic.AsyncAnthropic:
        if self._client is None:
            # Pass None if empty so SDK auto-reads ANTHROPIC_API_KEY from env directly
            self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key or None)
        return self._client

    def _get_history(self, chat_id: int) -> list[dict]:
        if chat_id not in self._conversations:
            self._conversations[chat_id] = []
        return self._conversations[chat_id]

    def clear_history(self, chat_id: int) -> None:
        self._conversations.pop(chat_id, None)

    def needs_sync(self, chat_id: int) -> bool:
        """Check if 30+ minutes passed since last interaction."""
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
        if not memories:
            return SYSTEM_PROMPT

        memory_block = "\n\n## Твоя память (то, что ты уже знаешь о Давите и его проектах)\n"
        for m in memories:
            memory_block += f"- [{m['category']}] {m['content']} (id: {m['id']})\n"

        return SYSTEM_PROMPT + memory_block

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
        history = self._get_history(chat_id)
        history.append({"role": "user", "content": user_message})

        # Keep conversation history manageable (last 20 messages)
        if len(history) > 20:
            history[:] = history[-20:]

        # Build system prompt with memories
        system_prompt = await self._build_system_prompt()

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
            due_date = datetime.fromisoformat(params["due_date"])
            if due_date.tzinfo is None:
                due_date = due_date.replace(tzinfo=timezone.utc)

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
            due = datetime.fromisoformat(params["due_date"])
            if due.tzinfo is None:
                due = due.replace(tzinfo=timezone.utc)
            task.due_date = due
            clickup_data["due_date"] = int(due.timestamp() * 1000)
            updated_fields.append("due_date")

        # Push to ClickUp if task has a clickup_task_id
        synced_to_clickup = False
        if task.clickup_task_id and clickup_data and settings.clickup_api_token:
            client = ClickUpClient(settings.clickup_api_token)
            try:
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

        # Delete from local DB
        await db.delete(task)
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

        plan_type = params.get("plan_type", "morning")
        date_str = params.get("date")

        if date_str:
            try:
                plan_date = date_type.fromisoformat(date_str)
            except ValueError:
                plan_date = datetime.now(ZoneInfo("Asia/Yerevan")).date()
        else:
            plan_date = datetime.now(ZoneInfo("Asia/Yerevan")).date()

        result = await db.execute(
            select(DailyPlan).where(
                DailyPlan.user_id == DAVIT_USER_ID,
                DailyPlan.plan_date == plan_date,
                DailyPlan.plan_type == plan_type,
            )
        )
        plan = result.scalar_one_or_none()

        if not plan:
            return {
                "found": False,
                "plan_type": plan_type,
                "date": plan_date.isoformat(),
                "message": f"План '{plan_type}' за {plan_date} не найден — скорее всего не был создан.",
            }

        return {
            "found": True,
            "plan_type": plan.plan_type,
            "date": plan.plan_date.isoformat(),
            "must_do": plan.must_do,
            "should_do": plan.should_do,
            "can_wait": plan.can_wait,
            "blocked": plan.blocked,
            "completed": plan.completed,
            "deferred": plan.deferred,
            "risks": plan.risks,
            "summary": plan.summary,
            "job_status": plan.job_status,
            "executed_at": plan.job_finished_at.isoformat() if plan.job_finished_at else None,
        }


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
