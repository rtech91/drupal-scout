from argparse import Namespace

from .formatter import Formatter
from .jsonformatter import JSONFormatter
from .tableformatter import TableFormatter
from .suggestformatter import SuggestFormatter


class FormatterFactory:
    """
    Factory class for formatters.
    """

    @staticmethod
    def get_formatter(args: Namespace) -> Formatter:
        """
        Get the formatter object.
        :param args:    the arguments passed to the application
        :type args:     argparse.Namespace
        :return:        the formatter object
        :rtype:         Formatter
        """
        format_name = args.format
        if format_name == 'json':
            return JSONFormatter()
        elif format_name == 'table':
            return TableFormatter()
        elif format_name == 'suggest':
            return SuggestFormatter(args)
