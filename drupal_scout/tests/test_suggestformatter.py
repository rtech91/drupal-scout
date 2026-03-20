import json
import os
import tempfile
from argparse import Namespace
from unittest import TestCase

from drupal_scout.formatters.suggestformatter import SuggestFormatter
from drupal_scout.module import Module


class TestSuggestFormatter(TestCase):
    def _create_composer_json(self, temp_dir, require: dict):
        """
        Helper: write a composer.json with the given 'require' block into temp_dir.
        """
        composer_data = {"require": require}
        with open(os.path.join(temp_dir, "composer.json"), "w") as f:
            json.dump(composer_data, f)

    def test_format_single_suitable_entry(self):
        """
        Test that a module with exactly 1 suitable entry gets its composer.json
        requirement replaced with ^<entry_version>.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            self._create_composer_json(temp_dir, {"drupal/webform": "^6.1"})
            args = Namespace(directory=temp_dir, save_dump=False)
            formatter = SuggestFormatter(args)

            module = Module(name='drupal/webform')
            module.version = '6.1.0'
            module.suitable_entries = [
                {'version': '6.2.0', 'requirement': '^9 || ^10'},
            ]

            result = json.loads(formatter.format([module]))

            self.assertEqual(result['require']['drupal/webform'], '^6.2.0')

    def test_format_multiple_suitable_entries(self):
        """
        Test that a module with >1 suitable entries gets the lowest version picked.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            self._create_composer_json(temp_dir, {"drupal/webform": "^6.1"})
            args = Namespace(directory=temp_dir, save_dump=False)
            formatter = SuggestFormatter(args)

            module = Module(name='drupal/webform')
            module.version = '6.1.0'
            module.active = True
            module.suitable_entries = [
                {'version': '6.3.0', 'requirement': '^10'},
                {'version': '6.2.0', 'requirement': '^9 || ^10'},
            ]

            result = json.loads(formatter.format([module]))

            self.assertEqual(result['require']['drupal/webform'], '^6.2.0')

    def test_format_no_suitable_entries(self):
        """
        Test that a module with 0 suitable entries leaves composer.json unchanged.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            self._create_composer_json(temp_dir, {"drupal/webform": "^6.1"})
            args = Namespace(directory=temp_dir, save_dump=False)
            formatter = SuggestFormatter(args)

            module = Module(name='drupal/webform')
            module.version = '6.1.0'
            module.suitable_entries = []

            result = json.loads(formatter.format([module]))

            # Original version requirement should be preserved
            self.assertEqual(result['require']['drupal/webform'], '^6.1')

    def test_format_save_dump_writes_file(self):
        """
        Test that save_dump=True causes the composer.json to be written to disk.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            self._create_composer_json(temp_dir, {"drupal/webform": "^6.1"})
            args = Namespace(directory=temp_dir, save_dump=True)
            formatter = SuggestFormatter(args)

            module = Module(name='drupal/webform')
            module.version = '6.1.0'
            module.suitable_entries = [
                {'version': '6.2.0', 'requirement': '^9 || ^10'},
            ]

            formatter.format([module])

            # Read the file back and verify it was updated
            with open(os.path.join(temp_dir, "composer.json"), "r") as f:
                saved_data = json.load(f)

            self.assertEqual(saved_data['require']['drupal/webform'], '^6.2.0')

    def test_format_no_save_dump(self):
        """
        Test that save_dump=False does NOT modify the composer.json file on disk.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            self._create_composer_json(temp_dir, {"drupal/webform": "^6.1"})
            args = Namespace(directory=temp_dir, save_dump=False)
            formatter = SuggestFormatter(args)

            module = Module(name='drupal/webform')
            module.version = '6.1.0'
            module.suitable_entries = [
                {'version': '6.2.0', 'requirement': '^9 || ^10'},
            ]

            formatter.format([module])

            # File on disk should still have the original value
            with open(os.path.join(temp_dir, "composer.json"), "r") as f:
                saved_data = json.load(f)

            self.assertEqual(saved_data['require']['drupal/webform'], '^6.1')

    def test_find_lowest_version(self):
        """
        Test the find_lowest_version helper directly with various orderings.
        """
        args = Namespace(directory='/tmp', save_dump=False)
        formatter = SuggestFormatter(args)

        entries = [
            {'version': '3.0.0'},
            {'version': '1.5.0'},
            {'version': '2.0.0'},
            {'version': '1.0.0'},
        ]

        result = formatter.find_lowest_version(entries)
        self.assertEqual(result, '1.0.0')
