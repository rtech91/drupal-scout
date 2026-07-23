from io import StringIO
from unittest import TestCase

from rich.console import Console

from drupal_scout.formatters.tableformatter import TableFormatter
from drupal_scout.module import Module


class TestTableFormatter(TestCase):
    def setUp(self):
        self.formatter = TableFormatter()
        self.console = Console(
            file=StringIO(), width=100, force_terminal=False, color_system=None
        )

    def _render_to_string(self, table) -> str:
        with self.console.capture() as capture:
            self.console.print(table)
        return capture.get()

    def test_format_module_with_multiple_entries(self):
        """
        Test formatting a module with multiple suitable entries.
        Each entry should appear as 'vX.Y.Z [requirement]'.
        """
        module = Module(name="drupal/webform")
        module.version = "6.2.0"
        module.suitable_entries = [
            {"version": "6.2.1", "requirement": "^9 || ^10"},
            {"version": "6.3.0", "requirement": "^10"},
        ]

        table = self.formatter.format([module])
        result = self._render_to_string(table)

        self.assertIn("drupal/webform", result)
        self.assertIn("6.2.0", result)
        self.assertIn("v6.2.1", result)
        self.assertIn("v6.3.0", result)
        self.assertIn("^9 || ^10", result)
        self.assertIn("^10", result)

    def test_format_failed_module(self):
        """
        Test that a failed module shows 'Failed to fetch module data'.
        """
        module = Module(name="drupal/broken")
        module.version = "1.0.0"
        module.failed = True

        table = self.formatter.format([module])
        result = self._render_to_string(table)

        self.assertIn("drupal/broken", result)
        self.assertIn("Failed to fetch module data", result)

    def test_format_inactive_module(self):
        """
        Test that an inactive module shows 'Module possibly not active'.
        """
        module = Module(name="drupal/old_module")
        module.version = "2.0.0"
        module.active = False

        table = self.formatter.format([module])
        result = self._render_to_string(table)

        self.assertIn("drupal/old_module", result)
        self.assertIn("Module possibly not active", result)

    def test_format_no_suitable_entries(self):
        """
        Test that an active, non-failed module with no entries shows 'No suitable entries found'.
        """
        module = Module(name="drupal/no_match")
        module.version = "3.0.0"

        table = self.formatter.format([module])
        result = self._render_to_string(table)

        self.assertIn("drupal/no_match", result)
        self.assertIn("No suitable entries found", result)

    def test_format_module_with_deep_scan_columns(self):
        """
        Test that Git index and Git history columns appear when deep_scan is present.
        """
        from drupal_scout.module import AuditStatus, ModuleDeepScan

        module = Module(name="drupal/webform")
        module.version = "6.2.0"
        module.deep_scan = ModuleDeepScan(
            module_path="web/modules/contrib/webform",
            index_status=AuditStatus.FOUND,
            history_status=AuditStatus.CLEAR,
        )

        table = self.formatter.format([module])
        result = self._render_to_string(table)

        self.assertIn("Git index", result)
        self.assertIn("Git history", result)
        self.assertIn("found", result)
        self.assertIn("clear", result)

    def test_format_module_without_deep_scan_columns(self):
        """
        Test that Git index and Git history columns are omitted when deep_scan is None.
        """
        module = Module(name="drupal/webform")
        module.version = "6.2.0"

        table = self.formatter.format([module])
        result = self._render_to_string(table)

        self.assertNotIn("Git index", result)
        self.assertNotIn("Git history", result)

    def test_format_module_deep_scan_mode_patches_columns(self):
        """Test that mode=patches renders only Patches column, not Git columns."""
        from drupal_scout.module import ModuleDeepScan

        module = Module(name="drupal/webform")
        module.version = "6.2.0"
        module.deep_scan = ModuleDeepScan(
            mode="patches", patches=[{"description": "Fix bug", "source": "p.patch"}]
        )

        table = self.formatter.format([module])
        result = self._render_to_string(table)

        self.assertIn("Patches", result)
        self.assertNotIn("Git index", result)
        self.assertNotIn("Git history", result)

    def test_format_module_deep_scan_mode_git_columns(self):
        """Test that mode=git renders only Git columns, not Patches column."""
        from drupal_scout.module import AuditStatus, ModuleDeepScan

        module = Module(name="drupal/webform")
        module.version = "6.2.0"
        module.deep_scan = ModuleDeepScan(
            mode="git",
            module_path="web/modules/contrib/webform",
            index_status=AuditStatus.FOUND,
            history_status=AuditStatus.CLEAR,
        )

        table = self.formatter.format([module])
        result = self._render_to_string(table)

        self.assertIn("Git index", result)
        self.assertIn("Git history", result)
        self.assertNotIn("Patches", result)
        self.assertIn("found", result)
        self.assertIn("clear", result)
