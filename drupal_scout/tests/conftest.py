import pytest
from unittest.mock import Mock
from aiohttp.client_reqrep import ClientResponse

# Save original __init__
original_init = ClientResponse.__init__

def patched_init(self, *args, **kwargs):
    # If stream_writer is not provided, mock it to prevent TypeError in aiohttp >= 3.14.0
    if 'stream_writer' not in kwargs:
        kwargs['stream_writer'] = Mock()
    original_init(self, *args, **kwargs)

ClientResponse.__init__ = patched_init  # type: ignore[method-assign]
