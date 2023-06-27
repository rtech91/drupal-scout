import argparse
import tempfile
from os import mkdir
from pathlib import Path
from unittest import TestCase

from drupal_scout.application import Application


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
        args = argparse.Namespace(directory=temp_dir.name)
        self.assertEqual(app.get_drupal_core_version(args), '8.8.5')
        self.assertNotEquals(app.get_drupal_core_version(args), '8.8.6')
        temp_dir.cleanup()
