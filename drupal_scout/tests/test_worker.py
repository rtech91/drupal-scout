from unittest import TestCase

from drupal_scout.module import Module
from drupal_scout.worker import Worker
from drupal_scout.exceptions import ModuleNotFoundException


class TestWorker(TestCase):
    def test_composer_url(self):
        """
        Test the URL composition.
        """
        module = Module(name='drupal/webform')
        worker = Worker(module=module)
        self.assertEqual(
            worker.prepare_composer_url('drupal/webform'),
            'https://packages.drupal.org/files/packages/8/p2/drupal/webform.json'
        )

    def test_find_suitable_entries_drupal_8(self):
        """
        Test finding suitable entries for Drupal 8.
        """
        module = Module(name='drupal/test_module')
        worker = Worker(module=module, current_core='8.9.0')
        
        transitive_entries = [
            {'version': '1.0.0', 'requirement': '^8 || ^9 || ^10', 'requirement_parts': ['8', '9', '10']},
            {'version': '2.0.0', 'requirement': '^9 || ^10', 'requirement_parts': ['9', '10']},
            {'version': '3.0.0', 'requirement': '^8', 'requirement_parts': ['8']},
        ]
        
        suitable = worker.find_suitable_entries(transitive_entries)
        
        # Should find entries that support Drupal 8
        self.assertEqual(len(suitable), 2)
        self.assertEqual(suitable[0]['version'], '1.0.0')
        self.assertEqual(suitable[1]['version'], '3.0.0')

    def test_find_suitable_entries_drupal_9(self):
        """
        Test finding suitable entries for Drupal 9.
        """
        module = Module(name='drupal/test_module')
        worker = Worker(module=module, current_core='9.5.0')
        
        transitive_entries = [
            {'version': '1.0.0', 'requirement': '^8 || ^9 || ^10', 'requirement_parts': ['8', '9', '10']},
            {'version': '2.0.0', 'requirement': '^9 || ^10', 'requirement_parts': ['9', '10']},
            {'version': '3.0.0', 'requirement': '^8', 'requirement_parts': ['8']},
        ]
        
        suitable = worker.find_suitable_entries(transitive_entries)
        
        # Should find entries that support Drupal 9
        self.assertEqual(len(suitable), 2)
        self.assertEqual(suitable[0]['version'], '1.0.0')
        self.assertEqual(suitable[1]['version'], '2.0.0')

    def test_find_suitable_entries_drupal_10(self):
        """
        Test finding suitable entries for Drupal 10.
        """
        module = Module(name='drupal/test_module')
        worker = Worker(module=module, current_core='10.0.0')
        
        transitive_entries = [
            {'version': '1.0.0', 'requirement': '^8 || ^9 || ^10', 'requirement_parts': ['8', '9', '10']},
            {'version': '2.0.0', 'requirement': '^9 || ^10', 'requirement_parts': ['9', '10']},
            {'version': '3.0.0', 'requirement': '^8', 'requirement_parts': ['8']},
        ]
        
        suitable = worker.find_suitable_entries(transitive_entries)
        
        # Should find entries that support Drupal 10
        self.assertEqual(len(suitable), 2)
        self.assertEqual(suitable[0]['version'], '1.0.0')
        self.assertEqual(suitable[1]['version'], '2.0.0')

    def test_find_suitable_entries_drupal_11(self):
        """
        Test finding suitable entries for Drupal 11 (future version).
        """
        module = Module(name='drupal/test_module')
        worker = Worker(module=module, current_core='11.0.0')
        
        transitive_entries = [
            {'version': '1.0.0', 'requirement': '^8 || ^9 || ^10', 'requirement_parts': ['8', '9', '10']},
            {'version': '2.0.0', 'requirement': '^10 || ^11', 'requirement_parts': ['10', '11']},
            {'version': '3.0.0', 'requirement': '^11', 'requirement_parts': ['11']},
            {'version': '4.0.0', 'requirement': '^9 || ^10 || ^11', 'requirement_parts': ['9', '10', '11']},
        ]
        
        suitable = worker.find_suitable_entries(transitive_entries)
        
        # Should find entries that support Drupal 11
        self.assertEqual(len(suitable), 3)
        self.assertEqual(suitable[0]['version'], '2.0.0')
        self.assertEqual(suitable[1]['version'], '3.0.0')
        self.assertEqual(suitable[2]['version'], '4.0.0')

    def test_find_suitable_entries_single_requirement(self):
        """
        Test finding suitable entries with a single requirement.
        """
        module = Module(name='drupal/test_module')
        worker = Worker(module=module, current_core='10.0.0')
        
        transitive_entries = [
            {'version': '1.0.0', 'requirement': '^10', 'requirement_parts': ['10']},
            {'version': '2.0.0', 'requirement': '^9', 'requirement_parts': ['9']},
        ]
        
        suitable = worker.find_suitable_entries(transitive_entries)
        
        # Should only find the entry that matches Drupal 10
        self.assertEqual(len(suitable), 1)
        self.assertEqual(suitable[0]['version'], '1.0.0')

    def test_find_suitable_entries_with_lock_version(self):
        """
        Test finding suitable entries with lock version filtering.
        """
        module = Module(name='drupal/test_module')
        module.version = '2.0.0'
        worker = Worker(module=module, use_lock_version='2.0.0', current_core='10.0.0')
        
        transitive_entries = [
            {'version': '1.0.0', 'requirement': '^10', 'requirement_parts': ['10']},
            {'version': '2.0.0', 'requirement': '^10', 'requirement_parts': ['10']},
            {'version': '3.0.0', 'requirement': '^10', 'requirement_parts': ['10']},
        ]
        
        suitable = worker.find_suitable_entries(transitive_entries)
        
        # Should only find entries >= lock version
        self.assertEqual(len(suitable), 2)
        self.assertEqual(suitable[0]['version'], '2.0.0')
        self.assertEqual(suitable[1]['version'], '3.0.0')

    def test_find_suitable_entries_no_match(self):
        """
        Test finding suitable entries when no entries match.
        """
        module = Module(name='drupal/test_module')
        worker = Worker(module=module, current_core='11.0.0')
        
        transitive_entries = [
            {'version': '1.0.0', 'requirement': '^8 || ^9', 'requirement_parts': ['8', '9']},
            {'version': '2.0.0', 'requirement': '^10', 'requirement_parts': ['10']},
        ]
        
        suitable = worker.find_suitable_entries(transitive_entries)
        
        # Should find no entries for Drupal 11
        self.assertEqual(len(suitable), 0)
