import asyncio
from unittest import TestCase
from unittest.mock import patch, MagicMock, AsyncMock

import aiohttp
import pytest

from drupal_scout.module import Module
from drupal_scout.worker import Worker, _MAX_RETRIES
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


@pytest.mark.asyncio
async def test_get_retries_on_connection_error():
    """
    Test that _get() retries on ClientConnectorError and raises after exhaustion.
    """
    module = Module(name='drupal/test_module')
    worker = Worker(module=module, current_core='10.0.0')

    with patch('aiohttp.ClientSession.get', side_effect=aiohttp.ClientConnectorError(
            connection_key=MagicMock(), os_error=OSError("Connection refused"))):
        with pytest.raises(aiohttp.ClientConnectorError):
            await worker._get(worker.prepare_composer_url(module.name))


@pytest.mark.asyncio
async def test_get_retries_on_timeout():
    """
    Test that _get() retries on TimeoutError and raises after exhaustion.
    """
    module = Module(name='drupal/test_module')
    worker = Worker(module=module, current_core='10.0.0')

    with patch('aiohttp.ClientSession.get', side_effect=asyncio.TimeoutError("Request timed out")):
        with pytest.raises(asyncio.TimeoutError):
            await worker._get(worker.prepare_composer_url(module.name))


@pytest.mark.asyncio
async def test_get_retries_on_5xx():
    """
    Test that _get() retries on server-side 5xx errors.
    """
    module = Module(name='drupal/test_module')
    worker = Worker(module=module, current_core='10.0.0')

    call_count = 0

    def make_503_response():
        mock_response = MagicMock()
        mock_response.status = 503
        mock_response.request_info = MagicMock()
        mock_response.history = ()
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)
        return mock_response

    def make_session():
        nonlocal call_count
        call_count += 1
        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=make_503_response())
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        return mock_session

    with patch('aiohttp.ClientSession', side_effect=lambda **kwargs: make_session()):
        with pytest.raises(aiohttp.ClientResponseError):
            await worker._get(worker.prepare_composer_url(module.name))

    assert call_count == _MAX_RETRIES


@pytest.mark.asyncio
async def test_run_marks_module_failed_on_connection_error():
    """
    Test that run() marks the module as failed when all retries are exhausted.
    """
    module = Module(name='drupal/test_module')
    worker = Worker(module=module, current_core='10.0.0')

    def make_failing_session():
        mock_session = MagicMock()
        mock_session.get = MagicMock(side_effect=aiohttp.ClientConnectorError(
            connection_key=MagicMock(), os_error=OSError("Connection refused")))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        return mock_session

    with patch('aiohttp.ClientSession', side_effect=lambda **kwargs: make_failing_session()):
        semaphore = asyncio.Semaphore(1)
        await worker.run(semaphore)

    assert module.failed is True
    assert module.active is True  # active should remain True (not a 404)


@pytest.mark.asyncio
async def test_get_succeeds_after_transient_failure():
    """
    Test that _get() succeeds when the first attempt fails but a later one succeeds.
    """
    module = Module(name='drupal/test_module')
    worker = Worker(module=module, current_core='10.0.0')

    # First call: 503 response
    error_response = MagicMock()
    error_response.status = 503
    error_response.request_info = MagicMock()
    error_response.history = ()
    error_response.__aenter__ = AsyncMock(return_value=error_response)
    error_response.__aexit__ = AsyncMock(return_value=False)

    # Second call: 200 response
    success_response = MagicMock()
    success_response.status = 200
    success_response.json = AsyncMock(return_value={"packages": {}})
    success_response.__aenter__ = AsyncMock(return_value=success_response)
    success_response.__aexit__ = AsyncMock(return_value=False)

    error_session = MagicMock()
    error_session.get = MagicMock(return_value=error_response)
    error_session.__aenter__ = AsyncMock(return_value=error_session)
    error_session.__aexit__ = AsyncMock(return_value=False)

    success_session = MagicMock()
    success_session.get = MagicMock(return_value=success_response)
    success_session.__aenter__ = AsyncMock(return_value=success_session)
    success_session.__aexit__ = AsyncMock(return_value=False)

    sessions = iter([error_session, success_session])
    with patch('aiohttp.ClientSession', side_effect=lambda **kwargs: next(sessions)):
        result = await worker._get(worker.prepare_composer_url(module.name))

    assert result == {"packages": {}}


@pytest.mark.asyncio
async def test_run_success_flow():
    """
    Test that run() populates transitive and suitable entries on a successful fetch.
    Covers the success path in run(): lines 42-43.
    """
    module = Module(name='drupal/test_module')
    worker = Worker(module=module, current_core='10.0.0')

    fake_response = {
        "packages": {
            "drupal/test_module": [
                {"version": "1.0.0", "require": {"drupal/core": "^9 || ^10"}},
                {"version": "2.0.0", "require": {"drupal/core": "^10"}},
            ]
        }
    }

    with patch.object(worker, '_get', new_callable=AsyncMock, return_value=fake_response):
        semaphore = asyncio.Semaphore(1)
        await worker.run(semaphore)

    assert len(module.transitive_entries) > 0
    assert len(module.suitable_entries) > 0
    assert module.failed is False
    assert module.active is True


@pytest.mark.asyncio
async def test_run_marks_module_inactive_on_404():
    """
    Test that run() sets module.active = False when ModuleNotFoundException is raised.
    Covers lines 47-49 in run().
    """
    module = Module(name='drupal/nonexistent_module')
    worker = Worker(module=module, current_core='10.0.0')

    with patch.object(worker, '_get', new_callable=AsyncMock,
                      side_effect=ModuleNotFoundException("The module drupal/nonexistent_module is not found.")):
        semaphore = asyncio.Semaphore(1)
        await worker.run(semaphore)

    assert module.active is False
    assert module.failed is False


@pytest.mark.asyncio
async def test_get_raises_module_not_found_on_404():
    """
    Test that _get() raises ModuleNotFoundException when the server returns 404.
    Covers lines 74 and 92 in _get().
    """
    module = Module(name='drupal/missing_module')
    worker = Worker(module=module, current_core='10.0.0')

    mock_response = MagicMock()
    mock_response.status = 404
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)

    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_response)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch('aiohttp.ClientSession', side_effect=lambda **kwargs: mock_session):
        with pytest.raises(ModuleNotFoundException) as exc_info:
            await worker._get(worker.prepare_composer_url(module.name))
        assert "drupal/missing_module" in exc_info.value.message


def test_find_transitive_entries_with_jq():
    """
    Test find_transitive_entries() using real jq parsing on a realistic payload.
    Covers lines 120-130.
    """
    module = Module(name='drupal/webform')
    worker = Worker(module=module, current_core='10.0.0')

    response_contents = {
        "packages": {
            "drupal/webform": [
                {"version": "6.1.0", "require": {"drupal/core": "^9.4 || ^10"}},
                {"version": "6.2.0", "require": {"drupal/core": "^10"}},
                {"version": "5.0.0"},  # no 'require' key — should be skipped by jq
            ]
        }
    }

    entries = worker.find_transitive_entries(response_contents)

    # Only the entry with || in the requirement should be returned
    assert len(entries) == 1
    assert entries[0]['version'] == '6.1.0'
    assert 'requirement_parts' in entries[0]
    assert '9.4' in entries[0]['requirement_parts']
    assert '10' in entries[0]['requirement_parts']
