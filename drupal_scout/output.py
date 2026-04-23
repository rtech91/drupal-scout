import io
import sys
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, ContextManager
from rich.console import Console
from rich.table import Table

# Initialize the central event logger
logger = logging.getLogger("drupal_scout")
logger.setLevel(logging.INFO)
# Prevent propagation to root logger by default so we don't double print
logger.propagate = False

class DynamicStderrHandler(logging.StreamHandler):
    """A stream handler that dynamically resolves sys.stderr on every emit.
    This ensures testing frameworks tracking sys.stderr see output robustly."""
    def emit(self, record):
        self.stream = sys.stderr
        super().emit(record)

console_handler = DynamicStderrHandler()
formatter = logging.Formatter('%(message)s')
console_handler.setFormatter(formatter)
if not logger.handlers:
    logger.addHandler(console_handler)

class OutputHandler(ABC):
    """Abstract strategy for handling application output and data formatting."""
    
    @abstractmethod
    def print(self, message: str, error: bool = False):
        """Emit arbitrary raw text."""
        pass

    @abstractmethod
    def render_info_table(self, title: str, status_dict: Dict[str, Any]):
        """Render a structural info table."""
        pass

    @abstractmethod
    def progress_bar(self) -> ContextManager:
        """Return a progress bar context manager."""
        pass

class ConsoleOutputHandler(OutputHandler):
    """Outputs to standard streams natively, fully resolving streams dynamically at call-time."""
    
    def __init__(self, out_stream=None, err_stream=None):
        self._out_stream = out_stream
        self._err_stream = err_stream

    def _get_console(self, error: bool = False) -> Console:
        if error:
            stream = self._err_stream if self._err_stream is not None else sys.stderr
        else:
            stream = self._out_stream if self._out_stream is not None else sys.stdout
        # rich Console handles stream formatting
        return Console(file=stream)

    def print(self, message: str, error: bool = False):
        console = self._get_console(error)
        console.print(message)

    def render_info_table(self, title: str, status_dict: Dict[str, Any]):
        console = self._get_console(error=False)
        table = Table(title=title)
        table.add_column("Property", justify="right", style="cyan", no_wrap=True)
        table.add_column("Value / Status", style="magenta")

        for key, value in status_dict.items():
            table.add_row(str(key), str(value))

        console.print(table)

    def progress_bar(self) -> ContextManager:
        from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=self._get_console(),
            transient=True
        )

class SilentOutputHandler(ConsoleOutputHandler):
    """An output handler that guarantees system output purity by writing to memory buffers.
    Perfect for FastMCP where sys.stdout must stream pure JSON."""
    
    def __init__(self):
        super().__init__(out_stream=io.StringIO(), err_stream=io.StringIO())

    def progress_bar(self) -> ContextManager:
        """Silent output handler should not show a progress bar."""
        import contextlib
        @contextlib.contextmanager
        def silent_progress():
            class MockProgress:
                def add_task(self, *args, **kwargs): return 0
                def update(self, *args, **kwargs): pass
                def advance(self, *args, **kwargs): pass
            yield MockProgress()
        return silent_progress()
