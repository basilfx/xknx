"""Top-level `xknx monitor` command: live group telegram sniffing."""

from __future__ import annotations

import asyncclick as click

from xknx import XKNX
from xknx.io import ConnectionConfig
from xknx.telegram import AddressFilter, Telegram
from xknx.telegram.apci import GroupValueResponse, GroupValueWrite

from ._common import async_command, format_raw_value, progress


@click.command(name="monitor")
@click.option(
    "--filter",
    "address_filters",
    multiple=True,
    metavar="PATTERN",
    help=(
        "Only show telegrams for group addresses matching PATTERN"
        " (e.g. '1/2/*' or '1/4/[5-6]'). May be given multiple times."
    ),
)
@click.pass_obj
@async_command
async def monitor(
    connection_config: ConnectionConfig, address_filters: tuple[str, ...]
) -> None:
    """Listen for incoming group telegrams until interrupted (Ctrl+C)."""
    filters = [AddressFilter(pattern) for pattern in address_filters] or None
    progress("Listening for telegrams (press Ctrl+C to stop)...")

    def telegram_received_cb(telegram: Telegram) -> None:
        payload = telegram.payload
        if isinstance(payload, GroupValueWrite | GroupValueResponse):
            value = format_raw_value(payload.value.value)
        else:
            value = type(payload).__name__
        click.echo(
            f"{telegram.source_address} -> {telegram.destination_address}: {value}"
        )

    xknx = XKNX(connection_config=connection_config, daemon_mode=True)
    xknx.telegram_queue.register_telegram_received_cb(telegram_received_cb, filters)
    await xknx.start()
    await xknx.stop()
