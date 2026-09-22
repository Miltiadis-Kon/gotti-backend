from apscheduler.schedulers.asyncio import AsyncIOScheduler
from services.fund_engine import fund_engine
from services.logging_service import logger
from config.settings import settings


class TaskScheduler:
    """Manages periodic background tasks for Module 4."""

    def __init__(self):
        self._scheduler = AsyncIOScheduler()
        self._continuous_batch_running: bool = False

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

        # Git Sync across all 4 microservices — runs every N seconds (default 300 = 5 min)
        if settings.git_sync_enabled:
            git_interval = settings.git_sync_interval
            self._scheduler.add_job(
                self._sync_git_task,
                'interval',
                seconds=git_interval,
                id='git_sync',
                name='Git Ecosystem Sync',
            )
            logger.startup(f'Git Sync worker scheduled every {git_interval}s')

        # Note: Candlestick batch collection has been removed per user instruction.
        # Candlesticks (1-year 5-minute) are now collected strictly on-demand via ws_channels.news_listener
        # whenever live breaking news is received for a ticker.

        self._scheduler.start()
        logger.startup(f'Scheduler started — NAV sync every {interval}s')

    async def _continuous_candle_batch_task(self) -> None:
        """Decommissioned: batch collection has been removed in favor of live news-driven collection."""
        logger.debug("[BATCH RUNNER] Batch collection is disabled. Candlestick collection is event-driven via news stream.")
        return

    # Backwards compatibility alias
    _hourly_candle_batch_task = _continuous_candle_batch_task

    def get_job_statuses(self) -> list[dict]:
        """Return status and next run times of all scheduled jobs."""
        results = []
        for job in self._scheduler.get_jobs():
            results.append({
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
            })
        return results

    async def trigger_candle_batch_now(self) -> dict:
        """Decommissioned: batch runner has been removed."""
        return {
            "status": "disabled",
            "message": "Continuous batch runner has been decommissioned. Candlesticks are collected on-demand for tickers with incoming news."
        }

    def schedule_candle_backfill(self, delay_seconds: int = 15) -> None:
        """Decommissioned: batch backfill has been removed."""
        logger.info("Batch backfill scheduling is disabled. System is operating in event-driven news mode.")

    async def _sync_nav_task(self) -> None:
        """Periodic NAVPU sync task."""
        try:
            fund_engine.sync_all_vaults()
        except Exception as e:
            logger.error(f'Scheduled NAV sync failed: {e}')

    async def _sync_git_task(self) -> None:
        """Periodic Git repository change check & auto-reload task."""
        try:
            from services.git_sync_service import git_sync_service
            logger.info('Running periodic Git change check across all repositories...')
            res = git_sync_service.sync_all(auto_reload=True)
            if res.get('any_updates'):
                logger.info(f"Git updates pulled and reloaded services: {res.get('reloaded_services')}")
        except Exception as e:
            logger.error(f'Scheduled Git sync failed: {e}')

    def stop(self) -> None:
        """Shut down the scheduler."""
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.shutdown('Scheduler stopped')


# Singleton scheduler instance
task_scheduler = TaskScheduler()
