import asyncio
from os import cpu_count
from typing import TYPE_CHECKING
from .worker import Worker

if TYPE_CHECKING:
    from .output import OutputHandler

class WorkersManager:
    """
    The main workers manager class.
    """

    def __init__(self, modules: list, concurrency_limit: int, output: 'OutputHandler', current_core: str | None = None, use_lock_version: bool = False):
        """
        Initialize the singleton workers manager.
        """
        self.modules = modules
        self.output = output
        self.concurrency_limit = concurrency_limit
        self.use_lock_version = use_lock_version
        self.current_core = current_core
        self.workers: list[Worker] = []
        # determine the concurrency limit; fall back to cpu_count if invalid
        self.concurrency_limit = concurrency_limit if concurrency_limit >= 1 else (cpu_count() or 4)

    async def run(self):
        """
        Run the workers concurrently using asyncio TaskGroup and show progress via Rich.
        """
        semaphore = asyncio.Semaphore(self.concurrency_limit)
        
        with self.output.progress_bar() as progress:
            main_task = progress.add_task("[cyan]Scanning modules...", total=len(self.modules))
            
            async with asyncio.TaskGroup() as tg:
                for module in self.modules:
                    worker = Worker(
                        module=module,
                        use_lock_version=self.use_lock_version,
                        current_core=self.current_core
                    )
                    
                    async def run_worker_with_progress(w, s, p, t):
                        await w.run(s)
                        p.advance(t)
                        
                    tg.create_task(run_worker_with_progress(worker, semaphore, progress, main_task))
