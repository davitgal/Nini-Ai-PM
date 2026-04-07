"""Supervisor — background decision layer for proactive AI behavior.

Runs every 5 minutes and decides:
1. Whether a ritual (morning/midday/eod) should run
2. Whether it's a late/recovery execution
3. Whether to mark a ritual as permanently skipped (past recovery window)

Replaces the simple time-check loop in daily_jobs.py with proper state tracking,
recovery support, and context-aware messaging.
"""

import logging
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

# Ritual schedule: trigger time + recovery_until_hour (after which we give up)
RITUAL_SCHEDULE = [
    {"type": "morning", "hour": 10, "minute": 30, "recovery_until_hour": 14},
    {"type": "midday",  "hour": 14, "minute":  0, "recovery_until_hour": 18},
    {"type": "eod",     "hour": 21, "minute":  0, "recovery_until_hour": 23},
]

# A ritual run within this window of the trigger time is considered "on-time"
ON_TIME_WINDOW_MINUTES = 30

_planner = DailyPlanner()


class Supervisor:
    """Evaluates and executes daily rituals with full context awareness."""

    async def run_cycle(self) -> None:
        """Main supervisor cycle — called every 5 minutes."""
        async with direct_session_factory() as db:
            try:
                await self._check_all_rituals(db)
            except Exception:
                logger.exception("Supervisor cycle failed")

    # ------------------------------------------------------------------
    # Core ritual logic
    # ------------------------------------------------------------------

    async def _check_all_rituals(self, db: AsyncSession) -> None:
        state = await self._get_or_create_state(db)
        context = await self._get_or_create_context(db)
        now = datetime.now(USER_TZ)

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

        if is_recovery:
            logger.info(
                "Executing ritual '%s' in recovery mode (trigger was %s, now %s)",
                plan_type,
                trigger_dt.strftime("%H:%M"),
                now.strftime("%H:%M"),
            )
        else:
            logger.info("Executing ritual '%s' on schedule", plan_type)

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
            # 1. Generate the structured plan (saved to DB by planner)
            plan = await self._generate_plan(db, plan_type)

            # 2. Build context-aware message (no extra Claude call)
            reminder_count = getattr(state, f"{plan_type}_reminder_count", 0)
            message = build_message(plan, context, is_recovery, reminder_count)

            # 3. Send to Telegram
            await _send_to_user(message)

            # 4. Update state: mark ritual as done
            setattr(state, f"{plan_type}_status", "done")
            setattr(state, f"{plan_type}_executed_at", now.astimezone(timezone.utc))
            await db.commit()

            # 5. Record in DailyContext interaction history
            from app.services.ai.adaptive_messenger import decide_tone
            tone = decide_tone(context, plan, reminder_count, is_recovery)
            await self._record_interaction(
                db, context,
                interaction_type="ritual",
                category=plan_type,
                summary=message[:200],
                tone=tone,
            )

            logger.info(
                "Ritual '%s' executed successfully (is_recovery=%s, tone=%s)",
                plan_type, is_recovery, tone,
            )

        except Exception:
            logger.exception("Failed to execute ritual '%s'", plan_type)

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
    """Update DailyContext with a user interaction. Called from bot.py on every message."""
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
