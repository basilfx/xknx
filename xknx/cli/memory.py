"""`xknx memory` commands: read/write raw memory on a device."""

from __future__ import annotations

import asyncclick as click

from xknx import XKNX
from xknx.io import ConnectionConfig
from xknx.telegram import apci
from xknx.telegram.address import IndividualAddress

from ._common import (
    HEX_BYTES,
    INDIVIDUAL_ADDRESS,
    INT,
    async_command,
    format_hex_dump,
    progress,
)


@click.group(name="memory")
def memory() -> None:
    """Read or write raw memory on a device."""


@memory.command(name="read")
@click.argument("individual_address", type=INDIVIDUAL_ADDRESS)
@click.argument("address", type=INT)
@click.option(
    "--count",
    type=int,
    default=1,
    show_default=True,
    help="Number of bytes to read (1-63).",
)
@click.pass_obj
@async_command
async def read(
    connection_config: ConnectionConfig,
    individual_address: IndividualAddress,
    address: int,
    count: int,
) -> None:
    """Read raw memory from a device. ADDRESS is a decimal or 0x-prefixed hex int."""
    progress(f"Reading memory address {address:#06x} from {individual_address}...")
    async with (
        XKNX(connection_config=connection_config) as xknx,
        xknx.management.connection(address=individual_address) as connection,
    ):
        response = await connection.request(
            payload=apci.MemoryRead(address=address, count=count),
            expected=apci.MemoryResponse,
        )

    assert isinstance(response.payload, apci.MemoryResponse)
    if response.payload.count == 0:
        raise click.ClickException(
            f"Memory read failed - {individual_address} did not return data for"
            f" address {address:#06x}."
        )
    click.echo(format_hex_dump(response.payload.data, start_address=address))


@memory.command(name="write")
@click.argument("individual_address", type=INDIVIDUAL_ADDRESS)
@click.argument("address", type=INT)
@click.argument("data", type=HEX_BYTES)
@click.pass_obj
@async_command
async def write(
    connection_config: ConnectionConfig,
    individual_address: IndividualAddress,
    address: int,
    data: bytes,
) -> None:
    """Write raw memory on a device. ADDRESS is a decimal or 0x-prefixed hex int, DATA a hex string."""
    progress(f"Writing memory address {address:#06x} on {individual_address}...")
    async with (
        XKNX(connection_config=connection_config) as xknx,
        xknx.management.connection(address=individual_address) as connection,
    ):
        response = await connection.request(
            payload=apci.MemoryWrite(address=address, data=data),
            expected=apci.MemoryResponse,
        )

    assert isinstance(response.payload, apci.MemoryResponse)
    if response.payload.count == 0:
        raise click.ClickException(
            f"Memory write failed - {individual_address} rejected the write to"
            f" address {address:#06x}."
        )
    click.echo(
        f"Wrote {data.hex()} to memory address {address:#06x} on {individual_address}."
    )
