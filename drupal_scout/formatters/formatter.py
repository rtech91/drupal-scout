from abc import ABC, abstractmethod
from typing import Any
from drupal_scout.module import Module


class Formatter(ABC):
    """
    Abstract class for formatters
    """
    @abstractmethod
    def format(self, modules: list[Module]) -> Any:
        pass
