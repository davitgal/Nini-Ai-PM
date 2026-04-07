"""Adaptive messenger — generates context-aware, non-repetitive Telegram messages.

Wraps the plan summary produced by DailyPlanner with situational framing:
- Recovery notice if the ritual ran late
- Tone adjustment based on user activity, urgency, and reminder count
- Avoids repeating the same opener pattern each day
"""

import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.models.daily_context import DailyContext
from app.models.daily_plan import DailyPlan

logger = logging.getLogger(__name__)

USER_TZ = ZoneInfo("Asia/Yerevan")

# Tone → recovery prefix options (rotated to avoid repetition)
_RECOVERY_PREFIXES = {
    "morning": [
        "Да, немного задержалась с планом — вот он:",
        "Утренний план с опозданием, но лучше поздно чем никогда:",
        "Задержалась, зато актуально. Вот план на сегодня:",
    ],
    "midday": [
        "Перепланирование чуть запоздало, но вот:",
        "Немного опоздала с апдейтом — вот что сейчас важно:",
        "Поздновато, но лучше так, чем без обновления:",
    ],
    "eod": [
        "Итог дня с небольшой задержкой:",
        "Поздно подвожу итоги, но вот как прошёл день:",
        "Итог — с задержкой, зато честный:",
    ],
}

# Tone-specific openers injected before the plan summary
_TONE_PREFIXES = {
    "assertive": {
        "morning": "Стоп. У тебя горящие задачи. Смотри внимательно:\n\n",
        "midday": "Давит, половина дня прошла. Смотри что происходит:\n\n",
        "eod": "Серьёзно, надо поговорить про этот день:\n\n",
    },
    "soft": {
        "morning": "",
        "midday": "",
        "eod": "",
    },
    "casual": {
        "morning": "Кстати, план на сегодня — ",
        "midday": "Ок, вот апдейт по дню — ",
        "eod": "Всё, день закончился. Итого: ",
    },
    "neutral": {
        "morning": "",
        "midday": "",
        "eod": "",
    },
}


def decide_tone(
    context: DailyContext,
    plan: DailyPlan,
    reminder_count: int,
    is_recovery: bool,
) -> str:
    """Decide message tone based on context, urgency, and reminder history.

    Returns: "soft" | "neutral" | "assertive" | "casual"
    """
    # Don't nag if we've already sent multiple reminders
    if reminder_count >= 2:
        return "soft"

    # Check for critical or overdue tasks
    must_do = plan.must_do or []
    today_str = datetime.now(USER_TZ).date().isoformat()
    has_overdue = any(
        t.get("due_date") and t["due_date"] < today_str
        for t in must_do[:5]
    )
    has_critical = any(t.get("priority") == "critical" for t in must_do[:5])

    # Check if user was recently active (last 30 min)
    is_user_active = False
    if context.user_last_active_at:
        delta = datetime.now(timezone.utc) - context.user_last_active_at
        is_user_active = delta.total_seconds() < 1800

    if is_recovery:
        return "casual"
    elif (has_overdue or has_critical) and not is_user_active:
        return "assertive"
    elif is_user_active:
        return "neutral"
    else:
        return "neutral"


def build_message(
    plan: DailyPlan,
    context: DailyContext,
    is_recovery: bool,
    reminder_count: int,
) -> str:
    """Build the final user-facing message with adaptive framing.

    The DailyPlanner already called Claude to produce plan.summary.
    We add contextual framing without an extra API call.
    """
    plan_type = plan.plan_type
    summary = plan.summary or ""

    tone = decide_tone(context, plan, reminder_count, is_recovery)

    parts: list[str] = []

    # Recovery prefix
    if is_recovery:
        recovery_options = _RECOVERY_PREFIXES.get(plan_type, [])
        if recovery_options:
            # Pick based on interaction count to rotate options
            idx = context.interaction_count % len(recovery_options)
            parts.append(f"<i>{recovery_options[idx]}</i>\n\n")

    # Tone prefix
    tone_prefix = _TONE_PREFIXES.get(tone, {}).get(plan_type, "")
    if tone_prefix:
        parts.append(tone_prefix)

    parts.append(summary)

    return "".join(parts)
