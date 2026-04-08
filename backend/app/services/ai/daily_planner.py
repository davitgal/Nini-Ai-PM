"""Daily planning service — generates morning plans, midday replans, and EOD reviews via Claude."""

import json
import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

USER_TZ = ZoneInfo("Asia/Yerevan")

import anthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import DAVIT_USER_ID
from app.models.daily_context import DailyContext
from app.models.daily_plan import DailyPlan
from app.models.task import UnifiedTask

logger = logging.getLogger(__name__)

PRIORITY_SCORE = {"critical": 4, "high": 3, "medium": 2, "low": 1, "none": 0}

NINI_VOICE_SYSTEM = """Ты — Нини, дерзкий AI проджект-менеджер Давита. 26 лет, говоришь прямо, без воды.
Отвечаешь только на русском. Форматируешь для Telegram (HTML теги: <b>, <i>, <code>).
Не используй markdown (**, ##). Будь конкретной — называй задачи по имени, не абстрактно."""


def _task_compact(t: UnifiedTask) -> dict:
    """Compact task dict for plan storage and Claude context."""
    return {
        "id": t.clickup_task_id or str(t.id),
        "title": t.title,
        "status": t.status,
        "priority": t.nini_priority,
        "company": t.company_tag,
        "due_date": t.due_date.date().isoformat() if t.due_date else None,
        "url": t.clickup_url,
    }


def _is_overdue(t: UnifiedTask, now: datetime) -> bool:
    return bool(t.due_date and t.due_date < now and t.status_type not in ("done", "closed"))


def _is_due_today(t: UnifiedTask, today: date) -> bool:
    return bool(t.due_date and t.due_date.date() == today)


async def _fetch_active_tasks(db: AsyncSession) -> list[UnifiedTask]:
    result = await db.execute(
        select(UnifiedTask).where(
            UnifiedTask.user_id == DAVIT_USER_ID,
            UnifiedTask.archived.is_(False),
            UnifiedTask.status_type.notin_(["done", "closed"]),
        )
    )
    return list(result.scalars().all())


def _extract_completion_signals(context: DailyContext | None) -> list[str]:
    """Extract user-reported completion signals from daily interactions."""
    if not context or not isinstance(context.interactions, list):
        return []

    done_markers = (
        "готово",
        "закончил",
        "сделал",
        "закрыл",
        "done",
        "finished",
        "completed",
    )
    signals: list[str] = []
    for item in context.interactions[-100:]:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "user_message":
            continue
        summary = str(item.get("summary", "")).strip()
        if not summary:
            continue
        low = summary.lower()
        if any(marker in low for marker in done_markers):
            signals.append(summary[:120])

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for s in signals:
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(s)
    return unique[:5]


async def _call_claude(system: str, user_message: str) -> str:
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key or None)
    response = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": user_message}],
    )
    await client.close()
    return response.content[0].text if response.content else ""


class DailyPlanner:
    """Generates daily plans and reports for proactive AI scheduling."""

    async def generate_morning_plan(self, db: AsyncSession) -> DailyPlan:
        """Build and save the morning plan for today."""
        now = datetime.now(timezone.utc)
        today = datetime.now(USER_TZ).date()

        tasks = await _fetch_active_tasks(db)

        must_do: list[dict] = []
        should_do: list[dict] = []
        can_wait: list[dict] = []
        blocked: list[dict] = []

        for t in tasks:
            td = _task_compact(t)
            status_lower = (t.status or "").lower()

            if "block" in status_lower:
                blocked.append(td)
                continue

            if _is_overdue(t, now) or _is_due_today(t, today) or t.nini_priority == "critical":
                must_do.append(td)
            elif t.nini_priority == "high":
                should_do.append(td)
            else:
                can_wait.append(td)

        # Sort must_do: overdue first, then by priority score desc
        must_do.sort(
            key=lambda x: (
                x["due_date"] is not None and x["due_date"] < today.isoformat(),
                PRIORITY_SCORE.get(x["priority"] or "none", 0),
            ),
            reverse=True,
        )
        must_do = must_do[:7]

        risks = [t for t in must_do if t["due_date"] and t["due_date"] < today.isoformat()]

        summary = await _generate_morning_summary(must_do, should_do, blocked, risks, today)

        plan = DailyPlan(
            id=uuid.uuid4(),
            user_id=DAVIT_USER_ID,
            plan_date=today,
            plan_type="morning",
            must_do=must_do,
            should_do=should_do,
            can_wait=can_wait,
            blocked=blocked,
            risks=risks,
            summary=summary,
            job_started_at=now,
            job_finished_at=datetime.now(timezone.utc),
            job_status="success",
            affected_tasks_count=len(tasks),
        )
        db.add(plan)
        await db.commit()
        await db.refresh(plan)
        logger.info("Morning plan saved: %d must_do, %d should_do, %d blocked", len(must_do), len(should_do), len(blocked))
        return plan

    async def generate_midday_replan(self, db: AsyncSession) -> DailyPlan:
        """Refresh the morning plan based on current task states."""
        now = datetime.now(timezone.utc)
        today = datetime.now(USER_TZ).date()

        # Load today's morning plan
        morning = await _load_plan(db, today, "morning")

        tasks = await _fetch_active_tasks(db)
        tasks_by_id: dict[str, UnifiedTask] = {
            (t.clickup_task_id or str(t.id)): t for t in tasks
        }

        must_do_ids = {t["id"] for t in (morning.must_do if morning else [])}

        # What's still active from morning must_do?
        remaining_must = [t for t in (morning.must_do if morning else []) if t["id"] in tasks_by_id]
        completed = [t for t in (morning.must_do if morning else []) if t["id"] not in tasks_by_id]

        # New urgent tasks that weren't in morning plan
        new_urgent: list[dict] = []
        for t in tasks:
            tid = t.clickup_task_id or str(t.id)
            if tid not in must_do_ids:
                if _is_overdue(t, now) or _is_due_today(t, today) or t.nini_priority == "critical":
                    new_urgent.append(_task_compact(t))

        # Rebuild must_do: remaining + new urgent, max 5
        updated_must = (remaining_must + new_urgent)[:5]

        deferred = remaining_must[5:] if len(remaining_must) > 5 else []

        summary = await _generate_midday_summary(updated_must, completed, new_urgent, deferred)

        plan = DailyPlan(
            id=uuid.uuid4(),
            user_id=DAVIT_USER_ID,
            plan_date=today,
            plan_type="midday",
            must_do=updated_must,
            deferred=deferred,
            completed=completed,
            summary=summary,
            job_started_at=now,
            job_finished_at=datetime.now(timezone.utc),
            job_status="success",
            affected_tasks_count=len(tasks),
        )
        db.add(plan)
        await db.commit()
        await db.refresh(plan)
        logger.info("Midday replan saved: %d must, %d completed, %d new_urgent", len(updated_must), len(completed), len(new_urgent))
        return plan

    async def generate_eod_review(self, db: AsyncSession) -> DailyPlan:
        """Generate end-of-day review comparing plan vs reality."""
        now = datetime.now(timezone.utc)
        today = datetime.now(USER_TZ).date()
        tomorrow = today + timedelta(days=1)

        morning = await _load_plan(db, today, "morning")
        context = await _load_context(db, today)
        planned_ids = {t["id"] for t in (morning.must_do if morning else [])}

        tasks = await _fetch_active_tasks(db)
        tasks_by_id: dict[str, UnifiedTask] = {
            (t.clickup_task_id or str(t.id)): t for t in tasks
        }

        # Completed = were in morning plan but now gone (done/closed/archived)
        completed = [t for t in (morning.must_do if morning else []) if t["id"] not in tasks_by_id]

        # Not completed = still in morning plan and still active
        not_completed = [t for t in (morning.must_do if morning else []) if t["id"] in tasks_by_id]

        # Carry-over risks: active tasks with due_date tomorrow or already overdue
        risks: list[dict] = []
        for t in tasks:
            due = t.due_date
            if due and (due.date() <= tomorrow):
                risks.append(_task_compact(t))

        total_planned = len(morning.must_do) if morning else 0
        productivity_pct = int(len(completed) / total_planned * 100) if total_planned > 0 else 0
        completion_signals = _extract_completion_signals(context)

        summary = await _generate_eod_summary(
            completed, not_completed, risks, productivity_pct, completion_signals
        )

        plan = DailyPlan(
            id=uuid.uuid4(),
            user_id=DAVIT_USER_ID,
            plan_date=today,
            plan_type="eod",
            must_do=[],
            completed=completed,
            deferred=not_completed,
            risks=risks,
            summary=summary,
            job_started_at=now,
            job_finished_at=datetime.now(timezone.utc),
            job_status="success",
            affected_tasks_count=len(tasks),
        )
        db.add(plan)
        await db.commit()
        await db.refresh(plan)
        logger.info("EOD review saved: %d completed, %d not_done, %d risks", len(completed), len(not_completed), len(risks))
        return plan


async def _load_plan(db: AsyncSession, plan_date: date, plan_type: str) -> DailyPlan | None:
    result = await db.execute(
        select(DailyPlan).where(
            DailyPlan.user_id == DAVIT_USER_ID,
            DailyPlan.plan_date == plan_date,
            DailyPlan.plan_type == plan_type,
        )
    )
    return result.scalar_one_or_none()


async def _load_context(db: AsyncSession, context_date: date) -> DailyContext | None:
    result = await db.execute(
        select(DailyContext).where(
            DailyContext.user_id == DAVIT_USER_ID,
            DailyContext.context_date == context_date,
        )
    )
    return result.scalar_one_or_none()


async def _generate_morning_summary(
    must_do: list[dict],
    should_do: list[dict],
    blocked: list[dict],
    risks: list[dict],
    today: date,
) -> str:
    if not settings.anthropic_api_key:
        return _fallback_morning(must_do, risks, today)

    tasks_text = json.dumps(must_do[:5], ensure_ascii=False, indent=2)
    risks_text = json.dumps(risks[:2], ensure_ascii=False, indent=2) if risks else "нет"
    blocked_text = f"{len(blocked)} задач заблокировано" if blocked else "блокировок нет"

    prompt = (
        f"Сегодня {today.strftime('%d.%m.%Y')}. Утренний план Давита готов.\n\n"
        f"MUST DO ({len(must_do)} задач, показываю топ-5):\n{tasks_text}\n\n"
        f"Риски: {risks_text}\n"
        f"Прочее: {blocked_text}\n\n"
        "Напиши короткий утренний брифинг (до 5 пунктов). "
        "Выдели 3–5 ключевых задач, 1–2 риска, 1 рекомендацию на день. "
        "Используй HTML теги для форматирования. Будь краткой и дерзкой."
    )
    return await _call_claude(NINI_VOICE_SYSTEM, prompt)


async def _generate_midday_summary(
    must_do: list[dict],
    completed: list[dict],
    new_urgent: list[dict],
    deferred: list[dict],
) -> str:
    if not settings.anthropic_api_key:
        return _fallback_midday(must_do, completed, new_urgent)

    prompt = (
        "Перепланирование в середине дня.\n\n"
        f"Выполнено из утреннего плана: {len(completed)} задач\n"
        f"Новые срочные задачи: {json.dumps(new_urgent[:3], ensure_ascii=False)}\n"
        f"Текущий приоритет: {json.dumps(must_do[:5], ensure_ascii=False)}\n"
        f"Перенесено: {len(deferred)} задач\n\n"
        "Напиши короткое обновление для Давита: что изменилось, что теперь приоритет, что можно перенести. "
        "Используй HTML теги. Максимум 200 слов."
    )
    return await _call_claude(NINI_VOICE_SYSTEM, prompt)


async def _generate_eod_summary(
    completed: list[dict],
    not_completed: list[dict],
    risks: list[dict],
    productivity_pct: int,
    completion_signals: list[str],
) -> str:
    if not settings.anthropic_api_key:
        return _fallback_eod(completed, not_completed, productivity_pct, completion_signals)

    prompt = (
        "Конец рабочего дня. Подводим итоги.\n\n"
        f"Выполнено: {len(completed)} задач\n"
        f"Не выполнено: {len(not_completed)} задач\n"
        f"Продуктивность: {productivity_pct}%\n"
        f"Риски на завтра: {json.dumps(risks[:3], ensure_ascii=False)}\n\n"
        f"Сигналы из диалога о завершении задач (могут опережать sync): {json.dumps(completion_signals, ensure_ascii=False)}\n\n"
        "Напиши короткий итог дня: ключевые достижения, проблемные зоны, 1 рекомендацию на завтра. "
        "Используй HTML теги. Максимум 200 слов. "
        "Если есть сигналы из диалога о завершении — НЕ пиши 'достижений нет'. "
        "В таком случае отметь, что часть закрытий подтверждена пользователем и может ждать финального sync."
    )
    return await _call_claude(NINI_VOICE_SYSTEM, prompt)


# --- Fallback summaries (when no Anthropic key) ---

def _fallback_morning(must_do: list[dict], risks: list[dict], today: date) -> str:
    lines = [f"<b>☀️ План на {today.strftime('%d.%m')}</b>\n"]
    for i, t in enumerate(must_do[:5], 1):
        due = f" | до {t['due_date']}" if t.get("due_date") else ""
        lines.append(f"{i}. <b>{t['title']}</b> [{t.get('company', '—')}]{due}")
    if risks:
        lines.append(f"\n⚠️ <b>Риски:</b> {len(risks)} просроченных задач")
    return "\n".join(lines)


def _fallback_midday(must_do: list[dict], completed: list[dict], new_urgent: list[dict]) -> str:
    lines = [f"<b>🔄 Перепланирование</b>\n"]
    lines.append(f"✅ Выполнено: {len(completed)}")
    if new_urgent:
        lines.append(f"🔥 Новых срочных: {len(new_urgent)}")
    lines.append(f"\n<b>Сейчас в приоритете:</b>")
    for t in must_do[:3]:
        lines.append(f"• {t['title']}")
    return "\n".join(lines)


def _fallback_eod(
    completed: list[dict],
    not_completed: list[dict],
    productivity_pct: int,
    completion_signals: list[str],
) -> str:
    lines = [f"<b>🌙 Итог дня</b>\n"]
    lines.append(f"✅ Выполнено: {len(completed)}")
    lines.append(f"⏳ Не выполнено: {len(not_completed)}")
    lines.append(f"📊 Продуктивность: {productivity_pct}%")
    if completion_signals:
        lines.append("🗣️ Есть подтвержденные пользователем закрытия задач (ожидают sync).")
    return "\n".join(lines)
