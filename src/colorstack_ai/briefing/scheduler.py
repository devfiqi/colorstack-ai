import logging
from collections.abc import Awaitable, Callable
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)


class DailyBriefScheduler:
    def __init__(
        self,
        *,
        enabled: bool,
        scheduled_time: time,
        timezone: str,
        job: Callable[[date], Awaitable[object]],
    ) -> None:
        self._enabled = enabled
        self._time = scheduled_time
        self._timezone = ZoneInfo(timezone)
        self._job = job
        self._scheduler = AsyncIOScheduler(timezone=self._timezone)
        self._started = False

    def start(self) -> None:
        if not self._enabled or self._started:
            return
        self._scheduler.add_job(
            self._run,
            CronTrigger(
                hour=self._time.hour,
                minute=self._time.minute,
                timezone=self._timezone,
            ),
            id="daily-executive-brief",
            coalesce=True,
            max_instances=1,
            misfire_grace_time=3600,
            replace_existing=True,
        )
        self._scheduler.start()
        self._started = True
        logger.info("Daily executive brief scheduler started; next run: %s", self.next_run_time)

    async def _run(self) -> None:
        today = datetime.now(self._timezone).date()
        try:
            await self._job(today)
        except Exception:
            logger.exception("Scheduled daily executive brief failed")

    @property
    def next_run_time(self) -> object | None:
        job = self._scheduler.get_job("daily-executive-brief")
        return job.next_run_time if job is not None else None

    @property
    def running(self) -> bool:
        return self._started

    def shutdown(self) -> None:
        if self._started:
            self._scheduler.shutdown(wait=False)
            self._started = False
