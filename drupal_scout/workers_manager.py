import threading

from .worker import Worker
from multiprocessing import cpu_count


class WorkersManager:
    """
    The main workers manager class.
    """

    def __init__(self, modules: list, number_of_threads: int, current_core: str = None, use_lock_version: bool = False):
        """
        Initialize the singleton workers manager.
        """
        self.modules = modules
        self.number_of_threads = number_of_threads
        self.use_lock_version = use_lock_version
        self.current_core = current_core
        self.workers = []
        # determine the number of threads in current CPU core and set it as the number of threads
        # to be used by the workers
        self.number_of_threads = number_of_threads if number_of_threads >= 1 else cpu_count()

    def run(self):
        """
        Run the workers.
        """
        semaphore = threading.Semaphore(self.number_of_threads)
        threads = []
        for module in self.modules:
            worker = Worker(
                module=module,
                use_lock_version=self.use_lock_version,
                current_core=self.current_core
            )
            thread = threading.Thread(target=worker.run, args=(semaphore,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()
