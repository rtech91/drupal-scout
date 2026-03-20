import unittest
from drupal_scout.exceptions import (
    ComposerV1Exception,
    DirectoryNotFoundException,
    NoComposerJSONFileException,
    ModuleNotFoundException,
)

class TestExceptions(unittest.TestCase):

    def test_composer_v1_exception_default_message(self):
        exc = ComposerV1Exception()
        self.assertEqual(exc.message, "The Drupal project uses Composer v1. Please upgrade to Composer v2.")
        self.assertEqual(str(exc), "The Drupal project uses Composer v1. Please upgrade to Composer v2.")

    def test_composer_v1_exception_custom_message(self):
        exc = ComposerV1Exception("Custom message")
        self.assertEqual(exc.message, "Custom message")
        self.assertEqual(str(exc), "Custom message")

    def test_directory_not_found_exception(self):
        exc = DirectoryNotFoundException("Missing dir")
        self.assertEqual(exc.message, "Missing dir")
        self.assertEqual(str(exc), "Missing dir")

    def test_no_composer_json_file_exception_default_message(self):
        exc = NoComposerJSONFileException()
        self.assertEqual(exc.message, "The directory does not contain the composer.json file.")
        self.assertEqual(str(exc), "The directory does not contain the composer.json file.")

    def test_no_composer_json_file_exception_custom_message(self):
        exc = NoComposerJSONFileException("Missing file")
        self.assertEqual(exc.message, "Missing file")
        self.assertEqual(str(exc), "Missing file")

    def test_module_not_found_exception(self):
        exc = ModuleNotFoundException("Module X not found")
        self.assertEqual(exc.message, "Module X not found")
        self.assertEqual(str(exc), "Module X not found")

if __name__ == '__main__':
    unittest.main()
