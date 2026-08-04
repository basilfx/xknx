"""`xknx property-value` commands: read/write KNX interface object properties."""

from __future__ import annotations

import asyncclick as click

from xknx import XKNX
from xknx.io import ConnectionConfig
from xknx.telegram import apci
from xknx.telegram.address import IndividualAddress

from ._common import HEX_BYTES, INDIVIDUAL_ADDRESS, PROPERTY_ID, async_command, progress

object_index_option = click.option(
    "--object-index",
    type=int,
    default=0,
    show_default=True,
    help="Interface object index (0 is the device object).",
)
count_option = click.option(
    "--count",
    type=int,
    default=1,
    show_default=True,
    help="Number of elements to read/write.",
)
start_index_option = click.option(
    "--start-index",
    type=int,
    default=1,
    show_default=True,
    help="1-based start index of the first element.",
)


@click.group(name="property-value")
def property_group() -> None:
    """Read or write KNX interface object properties."""


@property_group.command(name="read")
@click.argument("individual_address", type=INDIVIDUAL_ADDRESS)
@click.argument("property_id", type=PROPERTY_ID)
@object_index_option
@count_option
@start_index_option
@click.pass_obj
@async_command
async def read(
    connection_config: ConnectionConfig,
    individual_address: IndividualAddress,
    property_id: int,
    object_index: int,
    count: int,
    start_index: int,
) -> None:
    """Read a property from a device's interface object."""
    progress(f"Reading property {property_id} from {individual_address}...")
    async with (
        XKNX(connection_config=connection_config) as xknx,
        xknx.management.connection(address=individual_address) as connection,
    ):
        response = await connection.request(
            payload=apci.PropertyValueRead(
                object_index=object_index,
                property_id=property_id,
                count=count,
                start_index=start_index,
            ),
            expected=apci.PropertyValueResponse,
        )

    assert isinstance(response.payload, apci.PropertyValueResponse)
    if response.payload.count == 0:
        raise click.ClickException(
            f"Property read failed - object {object_index} has no property"
            f" {property_id} at index {start_index}."
        )
    click.echo(response.payload.data.hex())


@property_group.command(name="write")
@click.argument("individual_address", type=INDIVIDUAL_ADDRESS)
@click.argument("property_id", type=PROPERTY_ID)
@click.argument("data", type=HEX_BYTES)
@object_index_option
@count_option
@start_index_option
@click.pass_obj
@async_command
async def write(
    connection_config: ConnectionConfig,
    individual_address: IndividualAddress,
    property_id: int,
    data: bytes,
    object_index: int,
    count: int,
    start_index: int,
) -> None:
    """Write a property on a device's interface object. DATA is a hex string."""
    progress(f"Writing property {property_id} on {individual_address}...")
    async with (
        XKNX(connection_config=connection_config) as xknx,
        xknx.management.connection(address=individual_address) as connection,
    ):
        response = await connection.request(
            payload=apci.PropertyValueWrite(
                object_index=object_index,
                property_id=property_id,
                count=count,
                start_index=start_index,
                data=data,
            ),
            expected=apci.PropertyValueResponse,
        )

    assert isinstance(response.payload, apci.PropertyValueResponse)
    if response.payload.count == 0:
        raise click.ClickException(
            f"Property write failed - object {object_index} rejected"
            f" property {property_id} at index {start_index}."
        )
    click.echo(f"Wrote {data.hex()} to property {property_id} on {individual_address}.")
