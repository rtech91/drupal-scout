import argparse
import tempfile
import json
from io import StringIO
from os import mkdir
from os.path import join
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch, MagicMock
from importlib.metadata import PackageNotFoundError

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
            f.write('{"require": {"drupal/core": "^8.8.5"}}')
        args = argparse.Namespace(directory=temp_dir.name, no_lock=True)
        app.determine_drupal_core_version(args)
        # ^8.8.5 gets stripped to 8.8.5
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

    def test_handle_info(self):
        """
        Test handle_info method for diagnostic output correctness.
        """
        app = Application()
        temp_dir = tempfile.TemporaryDirectory()
        
        # Create dummy composer.json
        with open(join(temp_dir.name, 'composer.json'), 'w') as f:
            json.dump({"require": {"drupal/core": "9.5.0"}}, f)
            
        args = argparse.Namespace(directory=temp_dir.name, command='info')
        
        # Mocking system dependencies
        with patch('importlib.metadata.version') as mock_version, \
             patch('subprocess.run') as mock_run, \
             patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            
            mock_version.return_value = "1.1.0"
            mock_run.return_value = MagicMock() # success for jq check
            
            app.handle_info(args)
            
            output = mock_stdout.getvalue()
            self.assertIn("Drupal Scout v1.1.0", output)
            self.assertIn("Version: 1.1.0 (verified from metadata)", output)
            self.assertIn("Dependencies: jq binary is FOUND and FUNCTIONAL", output)
            self.assertIn("composer.json: DETECTED", output)
            self.assertIn("Drupal Core Version: 9.5.0", output)

        temp_dir.cleanup()

    @patch('drupal_scout.application.Application.handle_info')
    def test_run_calls_handle_info(self, mock_handle_info):
        """
        Test that app.run() correctly routes to handle_info when the 'info' command is passed.
        """
        app = Application()
        with tempfile.TemporaryDirectory() as temp_dir:
            # Note: Argparse typically expects info as the command
            # We mock sys.argv to simulate: drupal-scout -d /tmp info
            with patch('sys.argv', ['drupal-scout', '-d', temp_dir, 'info']):
                app.run()
                mock_handle_info.assert_called_once()

    def test_handle_info_fallback_version(self):
        """
        Test handle_info fallback to pyproject.toml when package metadata is missing.
        """
        app = Application()
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a mock pyproject.toml in the temp dir
            # We need to mock os.path.abspath to point to a place where we can find pyproject.toml
            # but it is easier to just mock 'open' for that specific path or mock the logic.
            
            args = argparse.Namespace(directory=temp_dir, command='info')
            
            with patch('importlib.metadata.version', side_effect=PackageNotFoundError), \
                 patch('subprocess.run') as mock_run, \
                 patch('sys.stdout', new_callable=StringIO) as mock_stdout, \
                 patch('builtins.open', patch.multiple('builtins', open=open)) as mock_open:
                
                # We need to selectively mock open for pyproject.toml
                original_open = open
                def side_effect(path, *args, **kwargs):
                    if 'pyproject.toml' in str(path):
                        return StringIO('version = "1.2.3-fallback"')
                    return original_open(path, *args, **kwargs)
                
                with patch('builtins.open', side_effect=side_effect):
                    app.handle_info(args)
                    output = mock_stdout.getvalue()
                    self.assertIn("Drupal Scout v1.2.3-fallback", output)

    def test_handle_info_jq_missing(self):
        """
        Test handle_info when jq is missing.
        """
        app = Application()
        with tempfile.TemporaryDirectory() as temp_dir:
            args = argparse.Namespace(directory=temp_dir, command='info')
            with patch('importlib.metadata.version', return_value="1.1.0"), \
                 patch('subprocess.run', side_effect=FileNotFoundError), \
                 patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                
                app.handle_info(args)
                output = mock_stdout.getvalue()
                self.assertIn("Dependencies: jq binary is NOT FOUND OR NOT FUNCTIONAL", output)

    def test_run_directory_not_found(self):
        """
        Test app.run() raises DirectoryNotFoundException and exits for non-existent directory.
        """
        app = Application()
        with patch('sys.argv', ['drupal-scout', '-d', '/non/existent/path/for/test']):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                with self.assertRaises(SystemExit) as cm:
                    app.run()
                self.assertEqual(cm.exception.code, 1)
                output = mock_stdout.getvalue()
                self.assertIn("does not exist", output)

    def test_run_no_composer_json(self):
        """
        Test app.run() raises NoComposerJSONFileException and exits when composer.json is missing.
        """
        app = Application()
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('sys.argv', ['drupal-scout', '-d', temp_dir]):
                with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                    with self.assertRaises(SystemExit) as cm:
                        app.run()
                    self.assertEqual(cm.exception.code, 1)
                    output = mock_stdout.getvalue()
                    self.assertIn("does not contain the composer.json file", output)

    def test_run_version(self):
        """
        Test that app.run() correctly outputs the version when --version is called.
        """
        app = Application()
        # Mocking get_version to return a predictable string
        with patch('drupal_scout.application.Application.get_version', return_value="1.1.0"):
            with patch('sys.argv', ['drupal-scout', '--version']):
                with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                    # argparse version action usually prints to stdout and exits with 0
                    with self.assertRaises(SystemExit) as cm:
                        app.run()
                    self.assertEqual(cm.exception.code, 0)
                    output = mock_stdout.getvalue()
                    self.assertIn("drupal-scout 1.1.0", output)
