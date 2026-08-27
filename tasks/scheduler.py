from apscheduler.schedulers.asyncio import AsyncIOScheduler
from services.fund_engine import fund_engine
from services.logging_service import logger
from config.settings import settings


class TaskScheduler:
    """Manages periodic background tasks for Module 4."""

    def __init__(self):
        self._scheduler = AsyncIOScheduler()

    def start(self) -> None:
        """Start the scheduler with configured tasks."""
        interval = settings.nav_sync_interval

        # NAVPU sync — runs every N seconds (default 300 = 5 min)
        self._scheduler.add_job(
            self._sync_nav_task,
            'interval',
            seconds=interval,
            id='nav_sync',
            name='NAVPU Sync',
        )

        self._scheduler.start()
        logger.startup(f'Scheduler started — NAV sync every {interval}s')

    async def _sync_nav_task(self) -> None:
        """Periodic NAVPU sync task."""
        try:
            fund_engine.sync_all_vaults()
        except Exception as e:
            logger.error(f'Scheduled NAV sync failed: {e}')

    def stop(self) -> None:
        """Shut down the scheduler."""
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.shutdown('Scheduler stopped')


# Singleton scheduler instance
task_scheduler = TaskScheduler()
