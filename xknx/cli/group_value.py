"""`xknx group-value` commands: read and write group addresses on the bus."""

from __future__ import annotations

from typing import Any

import asyncclick as click

from xknx import XKNX
from xknx.core.value_reader import ValueReader
from xknx.dpt import DPTBase, DPTNumeric
from xknx.io import ConnectionConfig
from xknx.telegram.address import DeviceGroupAddress
from xknx.telegram.apci import GroupValueResponse, GroupValueWrite
from xknx.tools import group_value_write

from ._common import GROUP_ADDRESS, async_command, format_raw_value, progress


def _parse_write_value(value: str, value_type: str | None) -> Any:
    """Parse a CLI value argument for `group-value write`."""
    if value_type is None:
        try:
            return int(value, 0)
        except ValueError:
            pass
        try:
            return list(bytes.fromhex(value))
        except ValueError:
            raise click.ClickException(
                f"{value!r} is not a valid raw value - pass an integer, a"
                " 0x-prefixed hex integer, or a hex byte string, or use --dpt to"
                " encode it with a specific data point type."
            ) from None
    transcoder = DPTBase.get_dpt(value_type)
    if issubclass(transcoder, DPTNumeric):
        try:
            return int(value)
        except ValueError:
            return float(value)
    return value


@click.group(name="group-value")
def group() -> None:
    """Read or write group addresses."""


@group.command(name="read")
@click.argument("group_address", type=GROUP_ADDRESS)
@click.option(
    "--dpt",
    "value_type",
    help="Data point type to decode the response with, e.g. 'temperature' or '9.001'.",
)
@click.option(
    "--timeout",
    type=float,
    default=2.0,
    show_default=True,
    help="Seconds to wait for a response.",
)
@click.pass_obj
@async_command
async def read(
    connection_config: ConnectionConfig,
    group_address: DeviceGroupAddress,
    value_type: str | None,
    timeout: float,
) -> None:
    """Send a GroupValueRead telegram and print the response."""
    transcoder = DPTBase.get_dpt(value_type) if value_type else None
    progress(f"Reading {group_address}...")
    async with XKNX(connection_config=connection_config) as xknx:
        telegram = await ValueReader(
            xknx, group_address, timeout_in_seconds=timeout
        ).read()

    if telegram is None:
        raise click.ClickException(f"No response received within {timeout}s.")
    assert isinstance(telegram.payload, GroupValueWrite | GroupValueResponse)

    if transcoder is not None:
        click.echo(transcoder.from_knx(telegram.payload.value))
    else:
        click.echo(format_raw_value(telegram.payload.value.value))


@group.command(name="write")
@click.argument("group_address", type=GROUP_ADDRESS)
@click.argument("value")
@click.option(
    "--dpt",
    "value_type",
    help="Data point type to encode the value with, e.g. 'switch' or '1.001'.",
)
@click.pass_obj
@async_command
async def write(
    connection_config: ConnectionConfig,
    group_address: DeviceGroupAddress,
    value: str,
    value_type: str | None,
) -> None:
    """Send a GroupValueWrite telegram."""
    parsed_value = _parse_write_value(value, value_type)
    progress(f"Writing to {group_address}...")
    async with XKNX(connection_config=connection_config) as xknx:
        group_value_write(xknx, group_address, parsed_value, value_type=value_type)
