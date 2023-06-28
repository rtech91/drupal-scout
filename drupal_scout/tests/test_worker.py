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
