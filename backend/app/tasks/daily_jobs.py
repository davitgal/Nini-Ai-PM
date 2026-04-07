"""Proactive daily jobs loop — delegates all decision-making to the Supervisor.

Schedule (Asia/Yerevan / UTC+4):
  10:30 — Morning plan
  14:00 — Midday replan
  21:00 — EOD review

The Supervisor handles:
- Whether each ritual should run
- Recovery if the backend was down at trigger time
- Marking rituals as skipped past the recovery window
- Context-aware adaptive messaging
"""

import asyncio
import logging

from app.services.supervisor import supervisor

logger = logging.getLogger(__name__)


async def daily_jobs_loop() -> None:
    """Main loop: run supervisor cycle every 5 minutes."""
    logger.info("Daily jobs loop started — supervisor mode (timezone: Asia/Yerevan)")

    while True:
        await supervisor.run_cycle()
        await asyncio.sleep(300)  # Check every 5 minutes
