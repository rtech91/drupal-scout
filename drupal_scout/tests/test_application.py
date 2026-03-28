import argparse
import tempfile
import json
from io import StringIO
from os import mkdir
from os.path import join
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch, MagicMock, AsyncMock
from importlib.metadata import PackageNotFoundError

import pytest

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
        
        args = parser.parse_args(['-d', '/tmp', '-n', '-l', '4', '-f', 'json'])
        self.assertEqual(args.directory, '/tmp')
        self.assertTrue(args.no_lock)
        self.assertEqual(args.limit, 4)
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


@pytest.mark.asyncio
async def test_run_success_flow():
    app = Application()
    temp_dir = tempfile.TemporaryDirectory()
    
    # Setup valid composer.json and Composer 2 structure
    mkdir(temp_dir.name + '/vendor')
    mkdir(temp_dir.name + '/vendor/composer')
    Path(temp_dir.name + '/vendor/composer/platform_check.php').touch()
    
    composer_data = {"require": {"drupal/core-recommended": "9.5.0", "drupal/test": "1.0"}}
    with open(temp_dir.name + '/composer.json', 'w') as f:
        json.dump(composer_data, f)
        
    with patch('drupal_scout.application.FormatterFactory') as MockFormatterFactory, \
         patch('drupal_scout.application.WorkersManager') as MockWorkersManager:
        MockWorkersManager.return_value.run = AsyncMock()
        # Mock sys.argv to emulate CLI run
        with patch('sys.argv', ['drupal-scout', '-d', temp_dir.name, '-n']):
            await app.run()
            
        # Ensure WorkersManager was initialized and run
        MockWorkersManager.assert_called_once()
        MockWorkersManager.return_value.run.assert_called_once()
        
        # Ensure Formatting happened
        MockFormatterFactory.get_formatter.assert_called_once()
    temp_dir.cleanup()


def test_handle_info():
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
        assert "Drupal Scout v1.1.0" in output
        assert "Version: 1.1.0 (verified from metadata)" in output
        assert "Dependencies: jq binary is FOUND and FUNCTIONAL" in output
        assert "composer.json: DETECTED" in output
        assert "Drupal Core Version: 9.5.0" in output

    temp_dir.cleanup()


@pytest.mark.asyncio
async def test_run_calls_handle_info():
    """
    Test that app.run() correctly routes to handle_info when the 'info' command is passed.
    """
    app = Application()
    with tempfile.TemporaryDirectory() as temp_dir:
        with patch.object(app, 'handle_info') as mock_handle_info:
            with patch('sys.argv', ['drupal-scout', '-d', temp_dir, 'info']):
                await app.run()
                mock_handle_info.assert_called_once()


def test_handle_info_fallback_version():
    """
    Test handle_info fallback to pyproject.toml when package metadata is missing.
    """
    app = Application()
    with tempfile.TemporaryDirectory() as temp_dir:
        args = argparse.Namespace(directory=temp_dir, command='info')
        
        with patch('importlib.metadata.version', side_effect=PackageNotFoundError), \
             patch('subprocess.run') as mock_run, \
             patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            
            original_open = open
            def side_effect(path, *args, **kwargs):
                if 'pyproject.toml' in str(path):
                    return StringIO('version = "1.2.3-fallback"')
                return original_open(path, *args, **kwargs)
            
            with patch('builtins.open', side_effect=side_effect):
                app.handle_info(args)
                output = mock_stdout.getvalue()
                assert "Drupal Scout v1.2.3-fallback" in output


def test_handle_info_jq_missing():
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
            assert "Dependencies: jq binary is NOT FOUND OR NOT FUNCTIONAL" in output


@pytest.mark.asyncio
async def test_run_directory_not_found():
    """
    Test app.run() raises DirectoryNotFoundException and exits for non-existent directory.
    """
    app = Application()
    with patch('sys.argv', ['drupal-scout', '-d', '/non/existent/path/for/test']):
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            with pytest.raises(SystemExit) as exc_info:
                await app.run()
            assert exc_info.value.code == 1
            output = mock_stdout.getvalue()
            assert "does not exist" in output


@pytest.mark.asyncio
async def test_run_no_composer_json():
    """
    Test app.run() raises NoComposerJSONFileException and exits when composer.json is missing.
    """
    app = Application()
    with tempfile.TemporaryDirectory() as temp_dir:
        with patch('sys.argv', ['drupal-scout', '-d', temp_dir]):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                with pytest.raises(SystemExit) as exc_info:
                    await app.run()
                assert exc_info.value.code == 1
                output = mock_stdout.getvalue()
                assert "does not contain the composer.json file" in output


@pytest.mark.asyncio
async def test_run_version():
    """
    Test that app.run() correctly outputs the version when --version is called.
    """
    app = Application()
    # Mocking get_version to return a predictable string
    with patch('drupal_scout.application.Application.get_version', return_value="1.1.0"):
        with patch('sys.argv', ['drupal-scout', '--version']):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                # argparse version action usually prints to stdout and exits with 0
                with pytest.raises(SystemExit) as exc_info:
                    await app.run()
                assert exc_info.value.code == 0
                output = mock_stdout.getvalue()
                assert "drupal-scout 1.1.0" in output


@pytest.mark.asyncio
async def test_run_composer_v1_exits():
    """
    Test app.run() exits with code 1 when Composer v1 is detected.
    Covers line 49 (raise ComposerV1Exception).
    """
    app = Application()
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create composer.json but NO vendor/composer/platform_check.php (Composer v1)
        with open(join(temp_dir, 'composer.json'), 'w') as f:
            json.dump({"require": {"drupal/core": "^9"}}, f)

        with patch('sys.argv', ['drupal-scout', '-d', temp_dir]):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                with pytest.raises(SystemExit) as exc_info:
                    await app.run()
                assert exc_info.value.code == 1
                output = mock_stdout.getvalue()
                assert "Composer v1" in output


@pytest.mark.asyncio
async def test_run_with_lock_file():
    """
    Test app.run() success path using the composer.lock file for module versions.
    Covers line 59 (self.determine_module_versions(args)).
    """
    app = Application()
    with tempfile.TemporaryDirectory() as temp_dir:
        # Setup Composer 2 structure
        mkdir(join(temp_dir, 'vendor'))
        mkdir(join(temp_dir, 'vendor', 'composer'))
        Path(join(temp_dir, 'vendor', 'composer', 'platform_check.php')).touch()

        composer_data = {"require": {"drupal/core-recommended": "^10.0", "drupal/token": "^1.0"}}
        with open(join(temp_dir, 'composer.json'), 'w') as f:
            json.dump(composer_data, f)

        lock_data = {
            "packages": [
                {"name": "drupal/core", "version": "10.2.0"},
                {"name": "drupal/token", "version": "1.5.0"}
            ]
        }
        with open(join(temp_dir, 'composer.lock'), 'w') as f:
            json.dump(lock_data, f)

        with patch('drupal_scout.application.FormatterFactory') as MockFormatterFactory, \
             patch('drupal_scout.application.WorkersManager') as MockWorkersManager:
            MockWorkersManager.return_value.run = AsyncMock()
            with patch('sys.argv', ['drupal-scout', '-d', temp_dir]):
                await app.run()

            MockWorkersManager.assert_called_once()
            # Verify determine_module_versions was reached (lock was used)
            modules = app._Application__modules
            assert modules["drupal/token"].version == "1.5.0"


@pytest.mark.asyncio
async def test_run_no_modules_found():
    """
    Test app.run() prints message when no modules are found in composer.json.
    Covers line 80.
    """
    app = Application()
    with tempfile.TemporaryDirectory() as temp_dir:
        # Setup Composer 2 structure
        mkdir(join(temp_dir, 'vendor'))
        mkdir(join(temp_dir, 'vendor', 'composer'))
        Path(join(temp_dir, 'vendor', 'composer', 'platform_check.php')).touch()

        # composer.json with only core — no drupal/* modules
        composer_data = {"require": {"drupal/core": "^10.0"}}
        with open(join(temp_dir, 'composer.json'), 'w') as f:
            json.dump(composer_data, f)

        lock_data = {"packages": [{"name": "drupal/core", "version": "10.2.0"}]}
        with open(join(temp_dir, 'composer.lock'), 'w') as f:
            json.dump(lock_data, f)

        with patch('sys.argv', ['drupal-scout', '-d', temp_dir]):
            with patch('drupal_scout.application.stderr', new_callable=StringIO) as mock_stderr:
                await app.run()
                output = mock_stderr.getvalue()
                assert "No modules were found" in output


def test_get_version_returns_unknown_on_all_failures():
    """
    Test get_version() returns 'Unknown' when both metadata and pyproject.toml fail.
    Covers lines 171-173.
    """
    app = Application()
    with patch('importlib.metadata.version', side_effect=PackageNotFoundError), \
         patch('builtins.open', side_effect=FileNotFoundError):
        result = app.get_version()
        assert result == "Unknown"


def test_handle_info_with_lock_detected():
    """
    Test handle_info when both composer.json and composer.lock are present.
    Covers line 211 (args_mock with no_lock=False).
    """
    app = Application()
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create both files
        with open(join(temp_dir, 'composer.json'), 'w') as f:
            json.dump({"require": {"drupal/core": "^10.0"}}, f)
        with open(join(temp_dir, 'composer.lock'), 'w') as f:
            json.dump({"packages": [{"name": "drupal/core", "version": "10.2.0"}]}, f)

        args = argparse.Namespace(directory=temp_dir, command='info')

        with patch('importlib.metadata.version', return_value="1.2.0"), \
             patch('subprocess.run') as mock_run, \
             patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            mock_run.return_value = MagicMock()
            app.handle_info(args)
            output = mock_stdout.getvalue()
            assert "Drupal Core Version: 10.2.0" in output
            assert "composer.lock: DETECTED" in output


def test_handle_info_core_version_detection_failure():
    """
    Test handle_info when core version detection raises an exception.
    Covers lines 223-224.
    """
    app = Application()
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create composer.json with bad content that will fail parsing (invalid JSON)
        with open(join(temp_dir, 'composer.json'), 'w') as f:
            f.write('{"require": invalid')

        args = argparse.Namespace(directory=temp_dir, command='info')

        with patch('importlib.metadata.version', return_value="1.2.0"), \
             patch('subprocess.run') as mock_run, \
             patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            mock_run.return_value = MagicMock()
            app.handle_info(args)
            output = mock_stdout.getvalue()
            # Should fall back to [Unknown] when detection fails
            assert "Drupal Core Version: [Unknown]" in output


def test_determine_module_versions_with_empty_modules():
    """
    Test determine_module_versions() exits when modules dict is empty.
    Covers lines 294-295.
    """
    app = Application()
    # Ensure __modules is empty
    app._Application__modules = {}

    with tempfile.TemporaryDirectory() as temp_dir:
        args = argparse.Namespace(directory=temp_dir)
        with patch('drupal_scout.application.stderr', new_callable=StringIO) as mock_stderr:
            with pytest.raises(SystemExit) as exc_info:
                app.determine_module_versions(args)
            assert exc_info.value.code == 0
            output = mock_stderr.getvalue()
            assert "No modules to check" in output
