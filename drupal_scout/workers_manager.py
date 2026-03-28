import asyncio
from os import cpu_count

from .worker import Worker


class WorkersManager:
    """
    The main workers manager class.
    """

    def __init__(self, modules: list, concurrency_limit: int, current_core: str | None = None, use_lock_version: bool = False):
        """
        Initialize the singleton workers manager.
        """
        self.modules = modules
        self.concurrency_limit = concurrency_limit
        self.use_lock_version = use_lock_version
        self.current_core = current_core
        self.workers: list[Worker] = []
        # determine the concurrency limit; fall back to cpu_count if invalid
        self.concurrency_limit = concurrency_limit if concurrency_limit >= 1 else (cpu_count() or 4)

    async def run(self):
        """
        Run the workers concurrently using asyncio TaskGroup.
        """
        semaphore = asyncio.Semaphore(self.concurrency_limit)
        async with asyncio.TaskGroup() as tg:
            for module in self.modules:
                worker = Worker(
                    module=module,
                    use_lock_version=self.use_lock_version,
                    current_core=self.current_core
                )
                tg.create_task(worker.run(semaphore))
