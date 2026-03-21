from unittest import TestCase
from unittest.mock import patch, MagicMock
from drupal_scout.workers_manager import WorkersManager
from drupal_scout.module import Module

class TestWorkersManager(TestCase):

    @patch('drupal_scout.workers_manager.cpu_count')
    @patch('drupal_scout.workers_manager.threading')
    @patch('drupal_scout.workers_manager.Worker')
    def test_run_with_custom_threads(self, mock_worker_class, mock_threading, mock_cpu_count):
        # Setup mocks
        mock_cpu_count.return_value = 8
        mock_threads = []
        def create_mock_thread(*args, **kwargs):
            mock_thread = MagicMock()
            mock_threads.append(mock_thread)
            return mock_thread
        
        mock_threading.Thread.side_effect = create_mock_thread
        
        # We pass 2 modules
        modules = [Module("module_1"), Module("module_2")]
        
        # Test 1: Number of threads > 0, so it uses the passed number
        manager = WorkersManager(modules=modules, number_of_threads=4, current_core="9", use_lock_version=True)
        self.assertEqual(manager.number_of_threads, 4)
        
        manager.run()
        
        # Ensure Semaphore was initialized with the correct number of threads
        mock_threading.Semaphore.assert_called_with(4)
        
        # Ensure Worker was instantiated for each module
        self.assertEqual(mock_worker_class.call_count, 2)
        
        # Ensure threading.Thread was called to create a thread for each module
        self.assertEqual(mock_threading.Thread.call_count, 2)
        
        # Ensure start and join were called on the threads exactly once per unique thread
        self.assertEqual(len(mock_threads), 2)
        for thread in mock_threads:
            thread.start.assert_called_once()
            thread.join.assert_called_once()

    @patch('drupal_scout.workers_manager.cpu_count')
    @patch('drupal_scout.workers_manager.threading')
    @patch('drupal_scout.workers_manager.Worker')
    def test_run_with_default_cpu_threads(self, mock_worker_class, mock_threading, mock_cpu_count):
        # Setup mocks
        mock_cpu_count.return_value = 8
        mock_threads = []
        def create_mock_thread(*args, **kwargs):
            mock_thread = MagicMock()
            mock_threads.append(mock_thread)
            return mock_thread
        
        mock_threading.Thread.side_effect = create_mock_thread
        
        modules = [Module("module_1")]
        
        # Test 2: Number of threads <= 0, so it uses cpu_count()
        manager = WorkersManager(modules=modules, number_of_threads=0, current_core="8.8", use_lock_version=False)
        self.assertEqual(manager.number_of_threads, 8)
        
        manager.run()
        
        # Ensure Semaphore was initialized with the CPU count (8)
        mock_threading.Semaphore.assert_called_with(8)

