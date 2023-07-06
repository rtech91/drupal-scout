from .formatter import Formatter
from .jsonformatter import JSONFormatter
from .tableformatter import TableFormatter
from .suggestformatter import SuggestFormatter


class FormatterFactory:
    """
    Factory class for formatters.
    """

    @staticmethod
    def get_formatter(name: str) -> Formatter:
        """
        Get the formatter object.
        :param name:    the name of the formatter
        :type name:     str
        :return:        the formatter object
        :rtype:         Formatter
        """
        if name == 'json':
            return JSONFormatter()
        elif name == 'table':
            return TableFormatter()
