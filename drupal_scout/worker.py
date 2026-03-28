import asyncio
import logging

import aiohttp
import jq
from packaging import version
from .exceptions import ModuleNotFoundException
from .module import Module

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_BACKOFF_FACTOR = 1
_RETRY_STATUS_CODES = frozenset([500, 502, 503, 504])
_REQUEST_TIMEOUT = aiohttp.ClientTimeout(sock_connect=5, sock_read=30)


class Worker:
    """
    The main worker class.
    """

    def __init__(self, module: Module, use_lock_version: str | bool = False, current_core: str = '8'):
        """
        Initialize the worker.
        :param module:           the module to be processed
        :param use_lock_version:  whether to use the version from the lock file
        :param current_core:
        """
        self.current_core = current_core.replace("^", "").replace("~", "")
        self.module = module
        self.use_lock_version: str | bool = False
        if type(use_lock_version) is str:
            self.use_lock_version = use_lock_version.replace("^", "").replace("~", "")

    async def run(self, semaphore: asyncio.Semaphore):
        async with semaphore:
            # This is the main entry point for the worker.
            try:
                composer_url = self.prepare_composer_url(self.module.name)
                contents = await self._get(composer_url)
                self.module.transitive_entries = self.find_transitive_entries(contents)
                self.module.suitable_entries = self.find_suitable_entries(self.module.transitive_entries)
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logger.error("Module %s failed after %d attempts: %s", self.module.name, _MAX_RETRIES, e)
                self.module.failed = True
            except ModuleNotFoundException as e:
                self.module.active = False
                print(e.message)

    async def _get(self, url: str) -> dict:
        """
        Perform an HTTP GET request with retry logic and exponential backoff.
        Retries on connection errors, timeouts, and server-side HTTP errors (5xx).
        :param url:     the URL to fetch
        :type url:      str
        :return:        the parsed JSON response
        :rtype:         dict
        :raises:        aiohttp.ClientError, asyncio.TimeoutError on exhausted retries
        """
        last_exception: BaseException | None = None
        for attempt in range(1, _MAX_RETRIES + 1):
            if attempt > 1:
                wait = _BACKOFF_FACTOR * (2 ** (attempt - 2))
                logger.warning(
                    "Retrying module %s... attempt %d/%d",
                    self.module.name, attempt, _MAX_RETRIES
                )
                await asyncio.sleep(wait)
            try:
                async with aiohttp.ClientSession(timeout=_REQUEST_TIMEOUT) as session:
                    async with session.get(url) as response:
                        if response.status == 404:
                            raise ModuleNotFoundException(
                                "The module {} is not found. Possibly it is no more supported.".format(self.module.name))
                        if response.status in _RETRY_STATUS_CODES:
                            last_exception = aiohttp.ClientResponseError(
                                response.request_info,
                                response.history,
                                status=response.status,
                                message=f"HTTP {response.status} for {url}",
                            )
                            if attempt < _MAX_RETRIES:
                                logger.warning(
                                    "Retrying module %s... attempt %d/%d (HTTP %d)",
                                    self.module.name, attempt + 1, _MAX_RETRIES, response.status
                                )
                            continue
                        contents = await response.json()
                        return contents
            except ModuleNotFoundException:
                raise
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                last_exception = exc
                if attempt < _MAX_RETRIES:
                    logger.warning(
                        "Retrying module %s... attempt %d/%d (%s)",
                        self.module.name, attempt + 1, _MAX_RETRIES, type(exc).__name__
                    )
        assert last_exception is not None
        raise last_exception

    def prepare_composer_url(self, module_name: str) -> str:
        """
        Prepare the URL to the JSON data of the module.
        :param module_name: the name of the module
        :type module_name:  str
        :return:   the URL to the JSON data of the module
        :rtype:    str
        """
        return 'https://packages.drupal.org/files/packages/8/p2/' + module_name + '.json'

    def find_transitive_entries(self, response_contents: dict) -> list:
        """
        Find the transitive entries of the module relative to the current core version.
        :param response_contents:   the contents of the response
        :type response_contents:    str
        :return:    the transitive entries of the module
        :rtype:     list
        """
        transitive_entries = []
        entries = jq.compile(
            '.packages."' + self.module.name + '" | .[] | select(.require != null) | {"version", '
                                               '"requirement":.require."drupal/core"}').input(response_contents).all()
        for entry in entries:
            if "|" in entry['requirement']:
                entry['requirement'] = entry['requirement'].replace("^", "").replace(" ", "")
                entry["requirement_parts"] = [p for p in entry['requirement'].split("|") if p]
                entry['requirement'] = " || ".join(entry['requirement_parts'])
                transitive_entries.append(entry)
        return transitive_entries

    def find_suitable_entries(self, transitive_entries: list) -> list:
        """
        Get the suitable transitive versions of the module.
        :param transitive_entries:  the transitive entries of the module
        :type transitive_entries:   list
        :return:    the suitable versions of the module
        :rtype:     list
        """
        suitable_entries = []
        current_major_version = version.parse(self.current_core).major
        for entry in transitive_entries:
            # Parse all requirement parts to extract major versions
            requirement_major_versions = [version.parse(req_part).major for req_part in entry['requirement_parts']]
            
            # Check if the current major version is in the list of supported major versions
            # The requirement uses || to indicate OR, so the module supports any of these versions
            if current_major_version in requirement_major_versions:
                suitable_entries.append(entry)

        # apply post-filtering if the lock version is used and the module version is specified
        if self.use_lock_version and self.module.version:
            suitable_entries = [
                entry for entry in suitable_entries
                if version.parse(entry['version']) >= version.parse(self.module.version)
            ]
        return suitable_entries
