import json
from unittest import TestCase

from drupal_scout.formatters.jsonformatter import JSONFormatter
from drupal_scout.module import Module


class TestJSONFormatter(TestCase):
    def setUp(self):
        self.formatter = JSONFormatter()

    def test_format_active_module_with_entries(self):
        """
        Test formatting an active module with suitable entries.
        """
        module = Module(name='drupal/webform')
        module.version = '6.2.0'
        module.suitable_entries = [
            {'version': '6.2.1', 'requirement': '^9 || ^10'},
            {'version': '6.3.0', 'requirement': '^10'},
        ]

        result = json.loads(self.formatter.format([module]))

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['name'], 'drupal/webform')
        self.assertEqual(result[0]['version'], '6.2.0')
        self.assertFalse(result[0]['failed'])
        self.assertEqual(len(result[0]['suitable_entries']), 2)
        self.assertEqual(result[0]['suitable_entries'][0]['version'], '6.2.1')
        self.assertEqual(result[0]['suitable_entries'][1]['version'], '6.3.0')

    def test_format_inactive_module(self):
        """
        Test that inactive modules have their suitable entries omitted from output.
        """
        module = Module(name='drupal/inactive_module')
        module.version = '1.0.0'
        module.active = False
        module.suitable_entries = [
            {'version': '1.1.0', 'requirement': '^10'},
        ]

        result = json.loads(self.formatter.format([module]))

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['name'], 'drupal/inactive_module')
        # suitable_entries should be empty because inactive modules are skipped
        self.assertEqual(len(result[0]['suitable_entries']), 0)

    def test_format_failed_module(self):
        """
        Test that failed modules have their suitable entries omitted from output.
        """
        module = Module(name='drupal/broken_module')
        module.version = '2.0.0'
        module.failed = True
        module.suitable_entries = [
            {'version': '2.1.0', 'requirement': '^10'},
        ]

        result = json.loads(self.formatter.format([module]))

        self.assertEqual(len(result), 1)
        self.assertTrue(result[0]['failed'])
        self.assertEqual(len(result[0]['suitable_entries']), 0)

    def test_format_empty_list(self):
        """
        Test formatting an empty module list.
        """
        result = json.loads(self.formatter.format([]))
        self.assertEqual(result, [])

    def test_format_multiple_modules(self):
        """
        Test formatting a mix of active, inactive, and failed modules.
        """
        active_module = Module(name='drupal/active')
        active_module.version = '1.0.0'
        active_module.suitable_entries = [
            {'version': '1.1.0', 'requirement': '^10'},
        ]

        inactive_module = Module(name='drupal/inactive')
        inactive_module.version = '2.0.0'
        inactive_module.active = False

        failed_module = Module(name='drupal/failed')
        failed_module.version = '3.0.0'
        failed_module.failed = True

        result = json.loads(self.formatter.format([active_module, inactive_module, failed_module]))

        self.assertEqual(len(result), 3)
        # Active module should have entries
        self.assertEqual(len(result[0]['suitable_entries']), 1)
        # Inactive module should have no entries
        self.assertEqual(len(result[1]['suitable_entries']), 0)
        # Failed module should have no entries
        self.assertEqual(len(result[2]['suitable_entries']), 0)

    def test_format_module_with_git_audit(self):
        """
        Test that git_audit field is included when present on the module.
        """
        from drupal_scout.module import ModuleGitAudit, AuditStatus

        module = Module(name='drupal/webform')
        module.version = '6.2.0'
        module.git_audit = ModuleGitAudit(
            module_path='web/modules/contrib/webform',
            index_status=AuditStatus.FOUND,
            history_status=AuditStatus.CLEAR,
            index_reason=None,
            history_reason=None
        )

        result = json.loads(self.formatter.format([module]))
        self.assertEqual(len(result), 1)
        self.assertIn('git_audit', result[0])
        self.assertEqual(result[0]['git_audit']['module_path'], 'web/modules/contrib/webform')
        self.assertEqual(result[0]['git_audit']['index_status'], 'found')
        self.assertEqual(result[0]['git_audit']['history_status'], 'clear')
        self.assertIsNone(result[0]['git_audit']['index_reason'])
        self.assertIsNone(result[0]['git_audit']['history_reason'])

    def test_format_module_without_git_audit(self):
        """
        Test that git_audit field is omitted when not present on the module.
        """
        module = Module(name='drupal/webform')
        module.version = '6.2.0'

        result = json.loads(self.formatter.format([module]))
        self.assertEqual(len(result), 1)
        self.assertNotIn('git_audit', result[0])
