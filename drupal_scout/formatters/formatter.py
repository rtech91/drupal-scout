from abc import ABC, abstractmethod

from drupal_scout.module import Module


class Formatter(ABC):
    """
    Abstract class for formatters
    """
    @abstractmethod
    def format(self, modules: [Module]) -> str:
        pass
