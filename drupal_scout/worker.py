import asyncio
import logging
import re

import aiohttp
import jq
from packaging import version
from packaging.specifiers import SpecifierSet, InvalidSpecifier
from packaging.version import InvalidVersion
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
            req_str = entry.get('requirement', '')
            if req_str and "|" in req_str:
                req_clean = req_str.replace("^", "").replace(" ", "")
                parts = [p.strip() for p in re.split(r'\|+', req_clean) if p.strip()]
                entry["requirement_parts"] = parts
                entry['requirement'] = " || ".join(parts)
                transitive_entries.append(entry)
        return transitive_entries

    def _is_clause_satisfied(self, clause: str) -> bool:
        """
        Check if a single requirement clause is satisfied by self.current_core.
        """
        try:
            core_ver = version.parse(self.current_core)
        except InvalidVersion:
            try:
                core_ver = version.parse(f"{self.current_core}.0.0")
            except InvalidVersion:
                return False

        raw_clause = clause.strip()
        if not raw_clause:
            return False

        # Fast path for simple numbers or caret major versions e.g. '8', '^8', '9', '10'
        if re.match(r'^[\^~]?\d+$', raw_clause):
            try:
                major = int(re.sub(r'[^\d]', '', raw_clause))
                return core_ver.major == major
            except ValueError:
                pass

        # Normalize specifiers for SpecifierSet
        spec_str = raw_clause
        def _expand_caret(m: re.Match) -> str:
            ver_str = m.group(1)
            major = int(ver_str.split('.')[0])
            return f">={ver_str}, <{major + 1}.0.0"
        spec_str = re.sub(r'\^(\d+(?:\.\d+)*)', _expand_caret, spec_str)
        spec_str = re.sub(r'(\d+(?:\.\d+)*)\s*([<>=!~])', r'\1, \2', spec_str)
        parts = [p.strip() for p in spec_str.split(',') if p.strip()]
        norm_parts = []
        for p in parts:
            if re.match(r'^\d+\.x$', p):
                norm_parts.append(f"=={p.split('.')[0]}.*")
            elif re.match(r'^\d+$', p):
                norm_parts.append(f"=={p}.*")
            elif re.match(r'^\d+(\.\d+)+$', p):
                norm_parts.append(f">={p}")
            else:
                norm_parts.append(p)
        norm_spec_str = ", ".join(norm_parts)

        try:
            spec_set = SpecifierSet(norm_spec_str)
            return core_ver in spec_set
        except (InvalidSpecifier, InvalidVersion) as exc:
            logger.warning("Failed to evaluate requirement clause %r as SpecifierSet: %s", clause, exc)
            matches = re.findall(r'\b\d+\b', raw_clause)
            if matches:
                try:
                    majors = [int(m) for m in matches]
                    return core_ver.major in majors
                except ValueError:
                    pass
            return False

    def find_suitable_entries(self, transitive_entries: list) -> list:
        """
        Get the suitable transitive versions of the module.
        :param transitive_entries:  the transitive entries of the module
        :type transitive_entries:   list
        :return:    the suitable versions of the module
        :rtype:     list
        """
        suitable_entries = []
        for entry in transitive_entries:
            req_parts = entry.get('requirement_parts', [])
            if not req_parts and 'requirement' in entry:
                req_parts = [p.strip() for p in re.split(r'\|+', entry['requirement']) if p.strip()]

            if any(self._is_clause_satisfied(part) for part in req_parts):
                suitable_entries.append(entry)

        # apply post-filtering if the lock version is used and the module version is specified
        if self.use_lock_version and self.module.version:
            filtered = []
            for entry in suitable_entries:
                try:
                    if version.parse(entry['version']) >= version.parse(self.module.version):
                        filtered.append(entry)
                except Exception:
                    filtered.append(entry)
            suitable_entries = filtered

        return suitable_entries

