import pytest
from unittest.mock import Mock
from aiohttp.client_reqrep import ClientResponse


@pytest.fixture(autouse=True, scope="session")
def _patch_aiohttp_clientresponse_init_stream_writer():
    """Ensure tests remain compatible with aiohttp >= 3.14 when stream_writer is required."""

    original_init = ClientResponse.__init__

    def patched_init(self, *args, **kwargs):
        kwargs.setdefault("stream_writer", Mock())
        return original_init(self, *args, **kwargs)

    ClientResponse.__init__ = patched_init  # type: ignore[method-assign]
    try:
        yield
    finally:
        ClientResponse.__init__ = original_init  # type: ignore[method-assign]
