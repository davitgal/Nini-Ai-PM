"""Supervisor — background decision layer for proactive AI behavior.

Runs every 5 minutes and decides:
1. Whether a ritual (morning/midday/eod) should run
2. Whether it's a late/recovery execution
3. Whether to proactively ping the user if they're idle
4. Whether to check in on an active work session at mid-point / end

Ping logic:
- If user is idle (no response for 15+ min) → ping every 15 min, escalating tone
- If user set a work session with estimate → check at halfway, then at end
- If work session without estimate → check every 30 min
"""

import logging
import random
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import direct_session_factory
from app.dependencies import DAVIT_USER_ID
from app.models.daily_context import DailyContext
from app.models.daily_plan import DailyPlan
from app.models.daily_state import DailyState
from app.services.ai.adaptive_messenger import build_message
from app.services.ai.daily_planner import DailyPlanner

logger = logging.getLogger(__name__)

USER_TZ = ZoneInfo("Asia/Yerevan")

# Time when this process started — used to avoid pinging immediately after a deploy
_PROCESS_START_UTC = datetime.now(timezone.utc)
# Grace period after startup: don't fire proactive pings during this window
_STARTUP_GRACE_SECONDS = 10 * 60  # 10 minutes

# Ritual schedule: trigger time + recovery_until_hour (after which we give up)
RITUAL_SCHEDULE = [
    {"type": "morning", "hour": 10, "minute": 30, "recovery_until_hour": 14},
    {"type": "midday",  "hour": 14, "minute":  0, "recovery_until_hour": 18},
    {"type": "eod",     "hour": 21, "minute":  0, "recovery_until_hour": 23},
]

# A ritual run within this window of the trigger time is considered "on-time"
ON_TIME_WINDOW_MINUTES = 30

# Proactive ping settings
PING_INTERVAL_MINUTES = 15
WORK_CHECK_NO_ESTIMATE_MINUTES = 30
WORKING_HOURS_START = 10  # 10:00
WORKING_HOURS_END = 22    # 22:00

# -----------------------------------------------------------------------
# Ping message pools — varied by escalation level, never template-feeling
# -----------------------------------------------------------------------

_PING_L1 = [  # First ping — casual nudge
    "Эй, {time} уже — ты там? Пора работать",
    "Давит, алло. {time} на часах. Что делаешь?",
    "Молчишь с {last_active}. Начинаем или нет?",
    "{time} — по плану должна быть работа. Ты живой?",
]
_PING_L2 = [  # 2nd–3rd ping — настойчивее
    "Уже {minutes} минут без ответа. Серьёзно, что происходит?",
    "Пишу второй раз. Объясняй где ты и что делаешь",
    "Молчишь {minutes} минут. Буду писать каждые 15 пока не ответишь",
    "{minutes} минут тишины. Это норма?",
]
_PING_L3 = [  # 4th–5th ping — жёстко
    "Третий раз пишу. Каждые 15 минут — это не шутка",
    "{minutes} минут игнора. Следующий пинг через 15 минут",
    "Продолжаем. Каждые. 15. Минут. Пока не ответишь.",
    "Хорошо, значит договорились — пингую каждые 15 минут весь день",
]
_PING_L4 = [  # 6th+ ping — максимальное давление
    "Пинг #{count}. Продолжаю.",
    "#{count} сообщение без ответа. Мне не сложно.",
    "Я не устану. #{count}. Следующий через 15 минут.",
    "Ок. #{count}. Можем делать это весь день.",
]

_MID_CHECK = [
    "Половина времени на «{task}» прошла. Успеваешь?",
    "«{task}» — {elapsed} мин из {estimate}. Всё ок?",
    "Дедлайн по «{task}» через {remaining} мин. Укладываешься?",
    "{elapsed} минут прошло на «{task}». На полпути — как там?",
]

_RESULT_CHECK = [
    "Время на «{task}» вышло — закрыл?",
    "«{task}» — {estimate} минут прошло. Что по итогу?",
    "Ну что, «{task}» готово или нет?",
    "Дедлайн по «{task}» истёк. Результат?",
]

_NO_ESTIMATE_CHECK = [
    "Как там «{task}»? Прогресс есть?",
    "{elapsed} минут прошло — «{task}» двигается?",
    "«{task}» — что сделал за {elapsed} минут?",
    "Напомни: «{task}» — ты ещё на нём или закончил?",
]


def _build_ping_message(count: int, time_str: str, inactive_min: int, last_active_str: str) -> str:
    if count <= 1:
        pool = _PING_L1
    elif count <= 3:
        pool = _PING_L2
    elif count <= 5:
        pool = _PING_L3
    else:
        pool = _PING_L4
    tpl = random.choice(pool)
    return tpl.format(
        time=time_str,
        minutes=inactive_min,
        last_active=last_active_str,
        count=count,
    )


_planner = DailyPlanner()


class Supervisor:
    """Evaluates and executes daily rituals with full context awareness."""

    async def run_cycle(self) -> None:
        """Main supervisor cycle — called every 5 minutes."""
        async with direct_session_factory() as db:
            try:
                state = await self._get_or_create_state(db)
                context = await self._get_or_create_context(db)
                now = datetime.now(USER_TZ)

                await self._check_all_rituals(db, state, context, now)
                await self._check_proactive_ping(db, state, context, now)
            except Exception:
                logger.exception("Supervisor cycle failed")

    # ------------------------------------------------------------------
    # Core ritual logic
    # ------------------------------------------------------------------

    async def _check_all_rituals(
        self, db: AsyncSession, state: DailyState, context: DailyContext, now: datetime
    ) -> None:
        for ritual in RITUAL_SCHEDULE:
            await self._check_ritual(db, state, context, ritual, now)

    async def _check_ritual(
        self,
        db: AsyncSession,
        state: DailyState,
        context: DailyContext,
        ritual: dict,
        now: datetime,
    ) -> None:
        plan_type = ritual["type"]
        status = getattr(state, f"{plan_type}_status")

        if status in ("done", "skipped"):
            return  # Already handled today

        trigger_dt = now.replace(
            hour=ritual["hour"], minute=ritual["minute"],
            second=0, microsecond=0,
        )
        recovery_until_dt = now.replace(
            hour=ritual["recovery_until_hour"], minute=0,
            second=0, microsecond=0,
        )

        if now < trigger_dt:
            return  # Too early — not yet time

        if now >= recovery_until_dt:
            # Past the recovery window — permanently skip
            setattr(state, f"{plan_type}_status", "skipped")
            await db.commit()
            logger.info("Ritual '%s' skipped — past recovery window (%s)", plan_type, now.strftime("%H:%M"))
            return

        # Determine if this is a late/recovery execution
        on_time_window_end = trigger_dt + timedelta(minutes=ON_TIME_WINDOW_MINUTES)
        is_recovery = now > on_time_window_end

        await self._execute_ritual(db, state, context, plan_type, is_recovery, now)

    async def _execute_ritual(
        self,
        db: AsyncSession,
        state: DailyState,
        context: DailyContext,
        plan_type: str,
        is_recovery: bool,
        now: datetime,
    ) -> None:
        """Generate plan, build adaptive message, send to user, update state."""
        try:
            plan = await self._generate_plan(db, plan_type)

            reminder_count = getattr(state, f"{plan_type}_reminder_count", 0)
            message = build_message(plan, context, is_recovery, reminder_count)

            await _send_to_user(message)

            setattr(state, f"{plan_type}_status", "done")
            setattr(state, f"{plan_type}_executed_at", now.astimezone(timezone.utc))
            await db.commit()

            from app.services.ai.adaptive_messenger import decide_tone
            tone = decide_tone(context, plan, reminder_count, is_recovery)
            await self._record_interaction(
                db, context,
                interaction_type="ritual",
                category=plan_type,
                summary=message[:200],
                tone=tone,
            )

            logger.info("Ritual '%s' executed (is_recovery=%s, tone=%s)", plan_type, is_recovery, tone)

        except Exception:
            logger.exception("Failed to execute ritual '%s'", plan_type)

    # ------------------------------------------------------------------
    # Proactive ping logic
    # ------------------------------------------------------------------

    async def _check_proactive_ping(
        self,
        db: AsyncSession,
        state: DailyState,
        context: DailyContext,
        now: datetime,
    ) -> None:
        """Ping user if idle, or check in on active work session."""

        # Don't ping right after a deploy — give the process 10 minutes to settle
        now_utc = now.astimezone(timezone.utc)
        if (now_utc - _PROCESS_START_UTC).total_seconds() < _STARTUP_GRACE_SECONDS:
            return

        # Only during working hours
        if not (WORKING_HOURS_START <= now.hour < WORKING_HOURS_END):
            return

        # Don't ping before morning ritual ran — user hasn't even seen their plan yet
        if state.morning_status not in ("done",) and not context.user_active_today:
            return

        # EOD done — day is over, stop all pinging
        if state.eod_status == "done":
            return

        work_session = context.work_session

        if work_session:
            await self._check_work_session(db, context, state, work_session, now)
        else:
            await self._check_idle_ping(db, context, now)

    async def _check_work_session(
        self,
        db: AsyncSession,
        context: DailyContext,
        state: DailyState,
        session: dict,
        now: datetime,
    ) -> None:
        """Check mid-point and end of an active work session."""
        try:
            started_at_str = session.get("started_at", "")
            if not started_at_str:
                return

            started_at = datetime.fromisoformat(started_at_str)
            if started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=timezone.utc)

            now_utc = now.astimezone(timezone.utc)
            elapsed_min = (now_utc - started_at).total_seconds() / 60
            task_title = session.get("task_title", "задача")
            estimate_min = session.get("estimate_min")

            if estimate_min:
                half_min = estimate_min / 2
                # Mid-check at halfway point
                if not session.get("mid_checked") and elapsed_min >= half_min:
                    remaining = max(0, int(estimate_min - elapsed_min))
                    msg = random.choice(_MID_CHECK).format(
                        task=task_title,
                        elapsed=int(elapsed_min),
                        estimate=estimate_min,
                        remaining=remaining,
                    )
                    await _send_to_user(msg)
                    session["mid_checked"] = True
                    context.work_session = dict(session)
                    await db.commit()
                    logger.info("Work session mid-check sent for '%s'", task_title)
                    return

                # Result check when time is up
                if session.get("mid_checked") and not session.get("result_asked") and elapsed_min >= estimate_min:
                    msg = random.choice(_RESULT_CHECK).format(
                        task=task_title,
                        estimate=estimate_min,
                    )
                    await _send_to_user(msg)
                    session["result_asked"] = True
                    context.work_session = dict(session)
                    await db.commit()
                    logger.info("Work session result-check sent for '%s'", task_title)
                    return

                # After result asked — treat as idle and ping if no response
                if session.get("result_asked"):
                    await self._check_idle_ping(db, context, now)

            else:
                # No estimate — check every 30 min
                last_check_str = session.get("last_check_at")
                if last_check_str:
                    last_check = datetime.fromisoformat(last_check_str)
                    if last_check.tzinfo is None:
                        last_check = last_check.replace(tzinfo=timezone.utc)
                    if (now_utc - last_check).total_seconds() < WORK_CHECK_NO_ESTIMATE_MINUTES * 60:
                        return

                msg = random.choice(_NO_ESTIMATE_CHECK).format(
                    task=task_title,
                    elapsed=int(elapsed_min),
                )
                await _send_to_user(msg)
                session["last_check_at"] = now_utc.isoformat()
                context.work_session = dict(session)
                await db.commit()
                logger.info("Work session no-estimate check sent for '%s'", task_title)

        except Exception:
            logger.exception("Error in _check_work_session")

    async def _check_idle_ping(
        self,
        db: AsyncSession,
        context: DailyContext,
        now: datetime,
    ) -> None:
        """Ping if user has been idle for 15+ minutes."""
        try:
            now_utc = now.astimezone(timezone.utc)
            last_active = context.user_last_active_at
            last_ping = context.last_ping_at
            ping_count = context.ping_count or 0

            # Calculate inactivity
            inactive_sec = 0
            last_active_str = "давно"
            if last_active:
                lа = last_active if last_active.tzinfo else last_active.replace(tzinfo=timezone.utc)
                inactive_sec = (now_utc - lа).total_seconds()
                inactive_min = int(inactive_sec / 60)
                if inactive_min < 60:
                    last_active_str = f"{inactive_min} мин назад"
                else:
                    last_active_str = f"{inactive_min // 60}ч назад"
                # Not idle yet
                if inactive_sec < PING_INTERVAL_MINUTES * 60:
                    return
            else:
                # Never been active today — only ping if morning ritual ran
                inactive_sec = PING_INTERVAL_MINUTES * 60 + 1  # force ping

            inactive_min = int(inactive_sec / 60)

            # Respect ping interval — don't spam faster than every 15 min
            if last_ping:
                lp = last_ping if last_ping.tzinfo else last_ping.replace(tzinfo=timezone.utc)
                since_last_ping = (now_utc - lp).total_seconds()
                if since_last_ping < PING_INTERVAL_MINUTES * 60:
                    return

            msg = _build_ping_message(
                count=ping_count + 1,
                time_str=now.strftime("%H:%M"),
                inactive_min=inactive_min,
                last_active_str=last_active_str,
            )
            await _send_to_user(msg)

            context.last_ping_at = now_utc
            context.ping_count = ping_count + 1
            await db.commit()
            logger.info("Idle ping #%d sent (inactive %d min)", ping_count + 1, inactive_min)

        except Exception:
            logger.exception("Error in _check_idle_ping")

    # ------------------------------------------------------------------
    # Plan generation
    # ------------------------------------------------------------------

    async def _generate_plan(self, db: AsyncSession, plan_type: str) -> DailyPlan:
        if plan_type == "morning":
            return await _planner.generate_morning_plan(db)
        elif plan_type == "midday":
            return await _planner.generate_midday_replan(db)
        else:
            return await _planner.generate_eod_review(db)

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------

    async def _get_or_create_state(self, db: AsyncSession) -> DailyState:
        today = datetime.now(USER_TZ).date()
        result = await db.execute(
            select(DailyState).where(
                DailyState.user_id == DAVIT_USER_ID,
                DailyState.state_date == today,
            )
        )
        state = result.scalar_one_or_none()
        if not state:
            state = DailyState(
                id=uuid.uuid4(),
                user_id=DAVIT_USER_ID,
                state_date=today,
            )
            db.add(state)
            await db.commit()
            await db.refresh(state)
        return state

    async def _get_or_create_context(self, db: AsyncSession) -> DailyContext:
        today = datetime.now(USER_TZ).date()
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
            await db.commit()
            await db.refresh(ctx)
        return ctx

    # ------------------------------------------------------------------
    # Context updates
    # ------------------------------------------------------------------

    async def _record_interaction(
        self,
        db: AsyncSession,
        context: DailyContext,
        interaction_type: str,
        category: str,
        summary: str,
        tone: str,
    ) -> None:
        interactions = list(context.interactions or [])
        interactions.append({
            "type": interaction_type,
            "category": category,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": summary,
            "tone": tone,
        })
        context.interactions = interactions[-50:]  # Keep last 50
        context.interaction_count = (context.interaction_count or 0) + 1
        await db.commit()


# ------------------------------------------------------------------
# Activity tracking (called from bot.py)
# ------------------------------------------------------------------

async def record_user_activity(message_text: str, category: str = "user_message") -> None:
    """Update DailyContext with a user interaction. Called from bot.py on every message.
    Also resets ping_count — user responded, so escalation counter starts over.
    """
    try:
        async with direct_session_factory() as db:
            now_utc = datetime.now(timezone.utc)
            today = datetime.now(USER_TZ).date()

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

            ctx.user_last_active_at = now_utc
            ctx.user_active_today = True
            ctx.interaction_count = (ctx.interaction_count or 0) + 1

            # User responded — reset consecutive ping count
            ctx.ping_count = 0

            interactions = list(ctx.interactions or [])
            interactions.append({
                "type": "user_message",
                "category": category,
                "timestamp": now_utc.isoformat(),
                "summary": message_text[:100],
                "tone": None,
            })
            ctx.interactions = interactions[-50:]

            await db.commit()
    except Exception:
        logger.exception("Failed to record user activity in DailyContext")


# ------------------------------------------------------------------
# Telegram helper
# ------------------------------------------------------------------

async def _send_to_user(text: str) -> None:
    if not text:
        return
    try:
        from app.services.telegram.bot import send_proactive_message
        await send_proactive_message(text)
    except Exception:
        logger.exception("Failed to send proactive Telegram message")


# Singleton instance
supervisor = Supervisor()
