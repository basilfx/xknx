"""`xknx gateway` commands: discover KNX/IP interfaces on the network."""

from __future__ import annotations

import asyncclick as click

from xknx import XKNX
from xknx.io import ConnectionConfig, GatewayScanner

from ._common import async_command, progress


@click.group()
def gateway() -> None:
    """Discover KNX/IP interfaces on the network."""


@gateway.command(name="scan")
@click.option(
    "--timeout",
    type=float,
    default=3.0,
    show_default=True,
    help="Seconds to wait for responses.",
)
@click.pass_obj
@async_command
async def scan(connection_config: ConnectionConfig, timeout: float) -> None:
    """Scan the local network for KNX/IP interfaces."""
    progress("Scanning for KNX/IP interfaces...")
    xknx = XKNX()
    scanner = GatewayScanner(
        xknx, local_ip=connection_config.local_ip, timeout_in_seconds=timeout
    )

    found = False
    async for gateway_descriptor in scanner.async_scan():
        found = True
        click.echo(gateway_descriptor.name)
        click.echo(
            f"  {'Individual address:':<19} {gateway_descriptor.individual_address}"
        )
        click.echo(
            f"  {'IP:':<19} {gateway_descriptor.ip_addr}:{gateway_descriptor.port}"
        )
        click.echo(f"  {'Serial number:':<19} {gateway_descriptor.serial_number}")
        click.echo(f"  {'MAC address:':<19} {gateway_descriptor.mac_address}")
        click.echo(
            f"  {'Supports secure:':<19}"
            f" {'Yes' if gateway_descriptor.supports_secure else 'No'}"
        )
        tunnelling = (
            "Secure"
            if gateway_descriptor.tunnelling_requires_secure
            else "TCP"
            if gateway_descriptor.supports_tunnelling_tcp
            else "UDP"
            if gateway_descriptor.supports_tunnelling
            else "Not supported"
        )
        click.echo(f"  {'Tunnelling:':<19} {tunnelling}")
        routing = (
            "Secure"
            if gateway_descriptor.routing_requires_secure
            else "Plain"
            if gateway_descriptor.supports_routing
            else "Not supported"
        )
        click.echo(f"  {'Routing:':<19} {routing}")
        if gateway_descriptor.supports_routing:
            click.echo(
                f"  {'Multicast group:':<19} {gateway_descriptor.multicast_address}"
            )
        click.echo()

    if not found:
        click.echo("No gateways found.")
