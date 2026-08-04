"""Tests for `xknx gateway` commands."""

from collections.abc import AsyncGenerator
from unittest.mock import patch

from asyncclick.testing import CliRunner

from xknx.cli.main import cli
from xknx.io.gateway_scanner import GatewayDescriptor, GatewayScanner
from xknx.telegram import IndividualAddress


async def test_gateway_scan_found() -> None:
    """A found gateway is printed with its connection capabilities."""
    descriptor = GatewayDescriptor(
        ip_addr="10.1.0.1",
        port=3671,
        name="Test IP Router",
        individual_address=IndividualAddress("1.1.0"),
        supports_routing=True,
        multicast_address="224.0.23.12",
        serial_number="AABBCCDDEEFF",
        mac_address="00:11:22:33:44:55",
    )

    async def fake_async_scan(
        self: GatewayScanner,
    ) -> AsyncGenerator[GatewayDescriptor]:
        yield descriptor

    with patch.object(GatewayScanner, "async_scan", new=fake_async_scan):
        result = await CliRunner().invoke(cli, ["gateway", "scan"])

    assert result.exit_code == 0, result.output
    assert "Scanning for KNX/IP interfaces..." in result.stderr
    assert "Test IP Router" in result.output
    assert "10.1.0.1:3671" in result.output
    assert f"{'Routing:':<19} Plain" in result.output
    assert f"{'Multicast group:':<19} 224.0.23.12" in result.output


async def test_gateway_scan_not_found() -> None:
    """No gateways found prints a clear message and still exits 0."""

    async def fake_async_scan(
        self: GatewayScanner,
    ) -> AsyncGenerator[GatewayDescriptor]:
        return
        yield  # pragma: no cover - makes this an async generator

    with patch.object(GatewayScanner, "async_scan", new=fake_async_scan):
        result = await CliRunner().invoke(cli, ["gateway", "scan"])

    assert result.exit_code == 0, result.output
    assert "No gateways found." in result.output
