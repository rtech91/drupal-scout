import argparse
import tempfile
import json
from os import mkdir
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from drupal_scout.application import Application
from drupal_scout.module import Module


class TestApplication(TestCase):
    def test_is_composer2(self):
        """
        Test the case when the project uses Composer 2.
        Uses a temporary directory to construct the folder structure.
        """
        app = Application()
        temp_dir = tempfile.TemporaryDirectory()
        mkdir(temp_dir.name + '/vendor')
        mkdir(temp_dir.name + '/vendor/composer')
        Path(temp_dir.name + '/vendor/composer/platform_check.php').touch()
        args = argparse.Namespace(directory=temp_dir.name)
        self.assertTrue(app.is_composer2(args))
        temp_dir.cleanup()
        self.assertFalse(app.is_composer2(args))

    def test_get_drupal_core_version(self):
        """
        Test the case when the Drupal core version is found.
        Uses a temporary directory to construct the folder structure.
        """
        app = Application()
        temp_dir = tempfile.TemporaryDirectory()
        Path(temp_dir.name + '/composer.json').touch()
        # write to the file to test the reading
        with open(temp_dir.name + '/composer.json', 'w') as f:
            f.write('{"require": {"drupal/core": "8.8.5"}}')
        args = argparse.Namespace(directory=temp_dir.name, no_lock=True)
        app.determine_drupal_core_version(args)
        # 8.8.5 gets stripped
        self.assertEqual(app._Application__drupal_core_version, '8.8.5')
        
        args = argparse.Namespace(directory=temp_dir.name, no_lock=False)
        Path(temp_dir.name + '/composer.lock').touch()
        # write to the file to test the reading
        with open(temp_dir.name + '/composer.lock', 'w') as f:
            f.write('{"packages": [{"name": "drupal/core", "version": "8.8.7"}]}')
        app.determine_drupal_core_version(args)
        self.assertEqual(app._Application__drupal_core_version, '8.8.7')
        temp_dir.cleanup()

    def test_get_argparser_configuration(self):
        app = Application()
        parser = argparse.ArgumentParser()
        parser = app.get_argparser_configuration(parser)
        
        args = parser.parse_args(['-d', '/tmp', '-n', '-t', '4', '-f', 'json'])
        self.assertEqual(args.directory, '/tmp')
        self.assertTrue(args.no_lock)
        self.assertEqual(args.threads, 4)
        self.assertEqual(args.format, 'json')
        self.assertFalse(args.save_dump)

    def test_get_required_modules(self):
        app = Application()
        temp_dir = tempfile.TemporaryDirectory()
        Path(temp_dir.name + '/composer.json').touch()
        
        # Test composer.json parsing using jq logic for getting required modules
        composer_data = {
            "require": {
                "drupal/core": "^9",
                "drupal/webform": "^6.0",
                "drupal/token": "^1.0",
                "symfony/yaml": "^4"
            }
        }
        with open(temp_dir.name + '/composer.json', 'w') as f:
            json.dump(composer_data, f)
            
        args = argparse.Namespace(directory=temp_dir.name)
        app.get_required_modules(args)
        
        # Verify that only drupal/* (excluding core) are added
        modules = app._Application__modules
        self.assertIn("drupal/webform", modules)
        self.assertIn("drupal/token", modules)
        self.assertNotIn("drupal/core", modules)
        self.assertNotIn("symfony/yaml", modules)
        temp_dir.cleanup()

    def test_determine_module_versions(self):
        app = Application()
        # Pretend we already loaded modules
        app._Application__modules = {
            "drupal/token": Module("drupal/token"),
            "drupal/webform": Module("drupal/webform")
        }
        
        temp_dir = tempfile.TemporaryDirectory()
        Path(temp_dir.name + '/composer.lock').touch()
        lock_data = {
            "packages": [
                {"name": "drupal/token", "version": "1.5.0"},
                {"name": "drupal/webform", "version": "6.1.2"}
            ]
        }
        with open(temp_dir.name + '/composer.lock', 'w') as f:
            json.dump(lock_data, f)

        args = argparse.Namespace(directory=temp_dir.name, no_lock=False)
        app.determine_module_versions(args)
        
        modules = app._Application__modules
        self.assertEqual(modules["drupal/token"].version, "1.5.0")
        self.assertEqual(modules["drupal/webform"].version, "6.1.2")
        temp_dir.cleanup()

    @patch('drupal_scout.application.FormatterFactory')
    @patch('drupal_scout.application.WorkersManager')
    def test_run_success_flow(self, MockWorkersManager, MockFormatterFactory):
        app = Application()
        temp_dir = tempfile.TemporaryDirectory()
        
        # Setup valid composer.json and Composer 2 structure
        mkdir(temp_dir.name + '/vendor')
        mkdir(temp_dir.name + '/vendor/composer')
        Path(temp_dir.name + '/vendor/composer/platform_check.php').touch()
        
        composer_data = {"require": {"drupal/core-recommended": "9.5.0", "drupal/test": "1.0"}}
        with open(temp_dir.name + '/composer.json', 'w') as f:
            json.dump(composer_data, f)
            
        # Mock sys.argv to emulate CLI run
        with patch('sys.argv', ['drupal-scout', '-d', temp_dir.name, '-n']):
            app.run()
            
        # Ensure WorkersManager was initialized and run
        MockWorkersManager.assert_called_once()
        MockWorkersManager.return_value.run.assert_called_once()
        
        # Ensure Formatting happened
        MockFormatterFactory.get_formatter.assert_called_once()
        temp_dir.cleanup()
