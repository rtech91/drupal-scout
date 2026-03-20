from argparse import Namespace
from unittest import TestCase

from drupal_scout.formatters.formatterfactory import FormatterFactory
from drupal_scout.formatters.jsonformatter import JSONFormatter
from drupal_scout.formatters.tableformatter import TableFormatter
from drupal_scout.formatters.suggestformatter import SuggestFormatter


class TestFormatterFactory(TestCase):
    def test_get_json_formatter(self):
        """
        Test that get_formatter returns JSONFormatter for 'json' format.
        """
        args = Namespace(format='json')
        formatter = FormatterFactory.get_formatter(args)
        self.assertIsInstance(formatter, JSONFormatter)

    def test_get_table_formatter(self):
        """
        Test that get_formatter returns TableFormatter for 'table' format.
        """
        args = Namespace(format='table')
        formatter = FormatterFactory.get_formatter(args)
        self.assertIsInstance(formatter, TableFormatter)

    def test_get_suggest_formatter(self):
        """
        Test that get_formatter returns SuggestFormatter for 'suggest' format.
        """
        args = Namespace(format='suggest', directory='/tmp', save_dump=False)
        formatter = FormatterFactory.get_formatter(args)
        self.assertIsInstance(formatter, SuggestFormatter)

    def test_get_unknown_formatter_returns_none(self):
        """
        Test that get_formatter returns None for an unknown format name.
        """
        args = Namespace(format='unknown')
        formatter = FormatterFactory.get_formatter(args)
        self.assertIsNone(formatter)
