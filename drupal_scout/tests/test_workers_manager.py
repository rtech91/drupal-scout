import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from drupal_scout.workers_manager import WorkersManager
from drupal_scout.module import Module


@pytest.mark.asyncio
async def test_run_with_custom_concurrency():
    """Test WorkersManager with a custom concurrency limit."""
    modules = [Module("module_1"), Module("module_2")]

    manager = WorkersManager(modules=modules, concurrency_limit=4, current_core="9", use_lock_version=True)
    assert manager.concurrency_limit == 4

    with patch('drupal_scout.workers_manager.Worker') as mock_worker_class:
        mock_worker_instance = AsyncMock()
        mock_worker_class.return_value = mock_worker_instance

        await manager.run()

        # Ensure Worker was instantiated for each module
        assert mock_worker_class.call_count == 2

        # Ensure run was called for each worker (via TaskGroup)
        assert mock_worker_instance.run.call_count == 2


@pytest.mark.asyncio
async def test_run_with_default_cpu_concurrency():
    """Test WorkersManager falls back to cpu_count when concurrency_limit <= 0."""
    with patch('drupal_scout.workers_manager.cpu_count', return_value=8):
        modules = [Module("module_1")]
        manager = WorkersManager(modules=modules, concurrency_limit=0, current_core="8.8", use_lock_version=False)
        assert manager.concurrency_limit == 8

    with patch('drupal_scout.workers_manager.Worker') as mock_worker_class:
        mock_worker_instance = AsyncMock()
        mock_worker_class.return_value = mock_worker_instance

        await manager.run()

        assert mock_worker_class.call_count == 1
        assert mock_worker_instance.run.call_count == 1
