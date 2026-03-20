from unittest import TestCase

from drupal_scout.formatters.tableformatter import TableFormatter
from drupal_scout.module import Module


class TestTableFormatter(TestCase):
    def setUp(self):
        self.formatter = TableFormatter()

    def test_format_module_with_multiple_entries(self):
        """
        Test formatting a module with multiple suitable entries.
        Each entry should appear as 'vX.Y.Z [requirement]'.
        """
        module = Module(name='drupal/webform')
        module.version = '6.2.0'
        module.suitable_entries = [
            {'version': '6.2.1', 'requirement': '^9 || ^10'},
            {'version': '6.3.0', 'requirement': '^10'},
        ]

        result = self.formatter.format([module])

        self.assertIn('drupal/webform', result)
        self.assertIn('6.2.0', result)
        self.assertIn('v6.2.1', result)
        self.assertIn('v6.3.0', result)
        self.assertIn('^9 || ^10', result)
        self.assertIn('^10', result)

    def test_format_failed_module(self):
        """
        Test that a failed module shows 'Failed to fetch module data'.
        """
        module = Module(name='drupal/broken')
        module.version = '1.0.0'
        module.failed = True

        result = self.formatter.format([module])

        self.assertIn('drupal/broken', result)
        self.assertIn('Failed to fetch module data', result)

    def test_format_inactive_module(self):
        """
        Test that an inactive module shows 'Module possibly not active'.
        """
        module = Module(name='drupal/old_module')
        module.version = '2.0.0'
        module.active = False

        result = self.formatter.format([module])

        self.assertIn('drupal/old_module', result)
        self.assertIn('Module possibly not active', result)

    def test_format_no_suitable_entries(self):
        """
        Test that an active, non-failed module with no entries shows 'No suitable entries found'.
        """
        module = Module(name='drupal/no_match')
        module.version = '3.0.0'

        result = self.formatter.format([module])

        self.assertIn('drupal/no_match', result)
        self.assertIn('No suitable entries found', result)
