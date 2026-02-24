from unittest import TestCase
from unittest.mock import patch, MagicMock

import requests

from drupal_scout.module import Module
from drupal_scout.worker import Worker, _MAX_RETRIES
from drupal_scout.exceptions import ModuleNotFoundException


class TestWorker(TestCase):
    def test_find_transitive_entries(self):
        """
        Test native Python JSON parsing in find_transitive_entries.
        """
        module = Module(name='drupal/webform')
        worker = Worker(module=module, current_core='10.0.0')

        response_contents = {
            'packages': {
                'drupal/webform': [
                    {
                        'version': '6.1.0',
                        'require': {'drupal/core': '^9 || ^10'}
                    },
                    {
                        'version': '5.0.0',
                        'require': {'drupal/core': '^8 || ^9'}
                    },
                    {
                        'version': '4.0.0',
                        'require': {'some/other': '^1.0'}  # no drupal/core, should be excluded
                    },
                    {
                        'version': '3.0.0'  # no require at all, should be excluded
                    },
                ]
            }
        }

        entries = worker.find_transitive_entries(response_contents)

        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]['version'], '6.1.0')
        self.assertEqual(entries[0]['requirement'], '9 || 10')
        self.assertEqual(entries[0]['requirement_parts'], ['9', '10'])
        self.assertEqual(entries[1]['version'], '5.0.0')
        self.assertEqual(entries[1]['requirement'], '8 || 9')
        self.assertEqual(entries[1]['requirement_parts'], ['8', '9'])

    def test_find_transitive_entries_empty_response(self):
        """
        Test find_transitive_entries with an empty dict (e.g. non-200 response).
        """
        module = Module(name='drupal/webform')
        worker = Worker(module=module, current_core='10.0.0')

        entries = worker.find_transitive_entries({})

        self.assertEqual(entries, [])

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

    @patch('drupal_scout.worker.requests.get')
    def test_get_retries_on_connection_error(self, mock_get):
        """
        Test that _get() retries on ConnectionError and marks module as failed after exhaustion.
        """
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")
        module = Module(name='drupal/test_module')
        worker = Worker(module=module, current_core='10.0.0')

        with self.assertRaises(requests.exceptions.ConnectionError):
            worker._get(worker.prepare_composer_url(module.name))

        self.assertEqual(mock_get.call_count, _MAX_RETRIES)

    @patch('drupal_scout.worker.requests.get')
    def test_get_retries_on_timeout(self, mock_get):
        """
        Test that _get() retries on Timeout and marks module as failed after exhaustion.
        """
        mock_get.side_effect = requests.exceptions.Timeout("Request timed out")
        module = Module(name='drupal/test_module')
        worker = Worker(module=module, current_core='10.0.0')

        with self.assertRaises(requests.exceptions.Timeout):
            worker._get(worker.prepare_composer_url(module.name))

        self.assertEqual(mock_get.call_count, _MAX_RETRIES)

    @patch('drupal_scout.worker.requests.get')
    def test_get_retries_on_5xx(self, mock_get):
        """
        Test that _get() retries on server-side 5xx errors.
        """
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_get.return_value = mock_response
        module = Module(name='drupal/test_module')
        worker = Worker(module=module, current_core='10.0.0')

        with self.assertRaises(requests.exceptions.HTTPError):
            worker._get(worker.prepare_composer_url(module.name))

        self.assertEqual(mock_get.call_count, _MAX_RETRIES)

    @patch('drupal_scout.worker.time.sleep')
    @patch('drupal_scout.worker.requests.get')
    def test_run_marks_module_failed_on_connection_error(self, mock_get, mock_sleep):
        """
        Test that run() marks the module as failed when all retries are exhausted.
        """
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")
        module = Module(name='drupal/test_module')
        worker = Worker(module=module, current_core='10.0.0')

        import threading
        semaphore = threading.Semaphore(1)
        worker.run(semaphore)

        self.assertTrue(module.failed)
        self.assertTrue(module.active)  # active should remain True (not a 404)

    @patch('drupal_scout.worker.time.sleep')
    @patch('drupal_scout.worker.requests.get')
    def test_get_succeeds_after_transient_failure(self, mock_get, mock_sleep):
        """
        Test that _get() succeeds when the first attempt fails but a later one succeeds.
        """
        error_response = MagicMock()
        error_response.status_code = 503
        success_response = MagicMock()
        success_response.status_code = 200
        mock_get.side_effect = [error_response, success_response]
        module = Module(name='drupal/test_module')
        worker = Worker(module=module, current_core='10.0.0')

        response = worker._get(worker.prepare_composer_url(module.name))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_get.call_count, 2)
