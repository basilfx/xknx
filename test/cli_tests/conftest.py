"""Conftest for CLI tests."""

from collections.abc import Iterator
from unittest.mock import AsyncMock, Mock, patch

import pytest

from xknx.io import ConnectionConfig
from xknx.xknx import XKNX


@pytest.fixture(autouse=True)
def _mock_knx_interface() -> Iterator[None]:
    """Patch the KNX/IP interface factory so CLI commands never touch the network."""

    def knx_ip_interface_mock(xknx: XKNX, connection_config: ConnectionConfig) -> Mock:
        mock = Mock()
        mock.connection_config = connection_config
        mock.start = AsyncMock()
        mock.stop = AsyncMock()
        mock.send_cemi = AsyncMock()
        return mock

    with patch("xknx.xknx.knx_interface_factory", side_effect=knx_ip_interface_mock):
        yield


@pytest.fixture
def mock_p2p_connection() -> Iterator[AsyncMock]:
    """
    Patch P2PConnection's wire protocol so management commands skip it.

    connect()/disconnect() become no-ops (no real TConnect/TDisconnect exchange)
    and request() is an AsyncMock the test configures with return_value/side_effect
    - this is the boundary at which `device info`/`property-value read`/`property-value write`
    talk to the bus, so mocking it exercises the CLI's own APCI construction and
    response handling without needing to simulate a device.
    """
    with (
        patch("xknx.management.management.P2PConnection.connect", new=AsyncMock()),
        patch("xknx.management.management.P2PConnection.disconnect", new=AsyncMock()),
        patch(
            "xknx.management.management.P2PConnection.request", new=AsyncMock()
        ) as mock_request,
    ):
        yield mock_request
