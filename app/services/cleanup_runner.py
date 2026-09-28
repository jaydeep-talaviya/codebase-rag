"""Background loop that reclaims idle repositories."""

import asyncio
import logging

from sqlmodel import Session

from app.config import settings
from app.db.db import engine
from app.services.cleanup import sweep_once

logger = logging.getLogger(__name__)


def run_sweep() -> list[int]:
    """One synchronous sweep. Safe to call from startup and from the loop."""
    if not settings.repo_cleanup_enabled:
        logger.debug("cleanup disabled by configuration")
        return []
    with Session(engine) as db:
        removed = sweep_once(db, settings.repo_idle_ttl_hours)
    if removed:
        logger.info("cleanup removed %s repositories: %s", len(removed), removed)
    return removed


async def cleanup_loop(stop: asyncio.Event) -> None:
    """Sweep every `repo_cleanup_interval_minutes` until asked to stop.

    Waits *before* the first sweep rather than after it. Startup already runs
    one sweep from the lifespan handler, so sweeping first here would run two
    back to back. The interval is measured from the end of one sweep to the
    start of the next, so a slow sweep delays the next one instead of
    overlapping with it.
    """
    interval = max(1, settings.repo_cleanup_interval_minutes) * 60
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
            return  # stop was set; shut down without another sweep
        except asyncio.TimeoutError:
            pass

        try:
            # The sweep blocks on file and database I/O, so it must not run on
            # the event loop that is also serving requests.
            await asyncio.to_thread(run_sweep)
        except Exception:
            # A failing sweep must not take the application down with it.
            logger.exception("repository cleanup sweep failed")
