"""`xknx device` commands: restart, info, discovery, flashing and addressing."""

from __future__ import annotations

import asyncio

import asyncclick as click

from xknx import XKNX
from xknx.io import ConnectionConfig
from xknx.management import P2PConnection
from xknx.management.procedures import (
    dm_restart,
    nm_individual_address_check,
    nm_individual_address_read,
    nm_individual_address_serial_number_write,
    nm_individual_address_write,
)
from xknx.profile import ResourceDevicePropertyId, ResourceGenericPropertyId
from xknx.telegram import apci
from xknx.telegram.address import IndividualAddress

from ._common import INDIVIDUAL_ADDRESS, SERIAL_NUMBER, async_command, progress

# The well-known KNX factory-default individual address of an unprogrammed
# device (area 15, line 15, device 255) - what `address unload` resets to.
UNLOADED_ADDRESS = IndividualAddress("15.15.255")


@click.group()
def device() -> None:
    """
    Restart, read info from, discover, flash, or address devices.

    Discovery and address load/unload talk to whichever device is in
    programming mode (the button on the device itself) - not to any specific
    individual address - unless --serial-number is given.
    """


@device.command(name="restart")
@click.argument("individual_address", type=INDIVIDUAL_ADDRESS)
@click.pass_obj
@async_command
async def restart(
    connection_config: ConnectionConfig, individual_address: IndividualAddress
) -> None:
    """Restart a device."""
    progress(f"Restarting {individual_address}...")
    async with XKNX(connection_config=connection_config) as xknx:
        await dm_restart(xknx, individual_address)
    click.echo(f"Restarted {individual_address}.")


async def _read_property(connection: P2PConnection, property_id: int) -> bytes | None:
    """Read a property, returning None if the device reports failure (count 0)."""
    response = await connection.request(
        payload=apci.PropertyValueRead(property_id=property_id),
        expected=apci.PropertyValueResponse,
    )
    assert isinstance(response.payload, apci.PropertyValueResponse)
    return response.payload.data if response.payload.count else None


@device.command(name="info")
@click.argument("individual_address", type=INDIVIDUAL_ADDRESS)
@click.pass_obj
@async_command
async def info(
    connection_config: ConnectionConfig, individual_address: IndividualAddress
) -> None:
    """Read the manufacturer id, serial number and mask version from a device."""
    progress(f"Requesting information from {individual_address}...")
    async with (
        XKNX(connection_config=connection_config) as xknx,
        xknx.management.connection(address=individual_address) as connection,
    ):
        descriptor_response = await connection.request(
            payload=apci.DeviceDescriptorRead(descriptor=0),
            expected=apci.DeviceDescriptorResponse,
        )
        manufacturer_id = await _read_property(
            connection, ResourceGenericPropertyId.PID_MANUFACTURER_ID
        )
        serial_number = await _read_property(
            connection, ResourceGenericPropertyId.PID_SERIAL_NUMBER
        )

    assert isinstance(descriptor_response.payload, apci.DeviceDescriptorResponse)
    mask_version = descriptor_response.payload.value

    click.echo(f"{'Individual address:':<20} {individual_address}")
    click.echo(f"{'Mask version:':<20} {mask_version:04X}")
    click.echo(
        f"{'Manufacturer id:':<20} "
        + (
            str(int.from_bytes(manufacturer_id, byteorder="big"))
            if manufacturer_id
            else "unknown"
        )
    )
    click.echo(
        f"{'Serial number:':<20} "
        + (
            f"{serial_number[:2].hex()}:{serial_number[2:].hex()}"
            if serial_number
            else "unknown"
        )
    )


@device.command(name="discover")
@click.option(
    "--timeout",
    type=float,
    default=3.0,
    show_default=True,
    help="Seconds to wait for devices in programming mode.",
)
@click.pass_obj
@async_command
async def discover(connection_config: ConnectionConfig, timeout: float) -> None:
    """Find the device currently in programming mode."""
    progress("Searching for a device in programming mode...")
    async with XKNX(connection_config=connection_config) as xknx:
        found = await nm_individual_address_read(
            xknx, timeout=timeout, raise_if_multiple=True
        )
    if not found:
        raise click.ClickException("No device in programming mode found.")
    click.echo(str(found[0]))


async def _write_progmode(connection: P2PConnection, enabled: bool) -> None:
    """Turn a device's programming LED/button on or off via PID_PROGMODE."""
    response = await connection.request(
        payload=apci.PropertyValueWrite(
            property_id=ResourceDevicePropertyId.PID_PROGMODE,
            data=bytes([1 if enabled else 0]),
        ),
        expected=apci.PropertyValueResponse,
    )
    assert isinstance(response.payload, apci.PropertyValueResponse)
    if response.payload.count == 0:
        state = "enable" if enabled else "disable"
        raise click.ClickException(
            f"Failed to {state} programming mode on {connection.address}."
        )


@device.command(name="flash")
@click.argument("individual_address", type=INDIVIDUAL_ADDRESS)
@click.option(
    "--timeout",
    type=float,
    default=5.0,
    show_default=True,
    help="Seconds to keep the programming LED blinking.",
)
@click.pass_obj
@async_command
async def flash(
    connection_config: ConnectionConfig,
    individual_address: IndividualAddress,
    timeout: float,
) -> None:
    """Blink a device's programming LED for --timeout seconds, to identify it."""
    progress(f"Flashing {individual_address} for {timeout}s...")
    async with (
        XKNX(connection_config=connection_config) as xknx,
        xknx.management.connection(address=individual_address) as connection,
    ):
        await _write_progmode(connection, enabled=True)
        try:
            await asyncio.sleep(timeout)
        finally:
            await _write_progmode(connection, enabled=False)
    click.echo(f"Stopped flashing {individual_address}.")


async def _write_individual_address(
    connection_config: ConnectionConfig,
    individual_address: IndividualAddress,
    serial_number: bytes | None,
) -> None:
    """Write individual_address to a device, by serial number or programming mode."""
    async with XKNX(connection_config=connection_config) as xknx:
        if serial_number is not None:
            progress(
                f"Writing address {individual_address} to device with serial"
                f" number {serial_number.hex()}..."
            )
            await nm_individual_address_serial_number_write(
                xknx, serial_number, individual_address
            )
        else:
            progress(
                f"Writing address {individual_address} to device in programming mode..."
            )
            await nm_individual_address_write(xknx, individual_address)


_SERIAL_NUMBER_OPTION_HELP = (
    "6-byte serial number (hex, colons optional) of the device. If omitted,"
    " targets whichever single device is currently in programming mode instead."
)


@device.group(name="address")
def address() -> None:
    """Load (write) or unload (reset) a device's individual address."""


@address.command(name="load")
@click.argument("individual_address", type=INDIVIDUAL_ADDRESS)
@click.option("--serial-number", type=SERIAL_NUMBER, help=_SERIAL_NUMBER_OPTION_HELP)
@click.pass_obj
@async_command
async def load(
    connection_config: ConnectionConfig,
    individual_address: IndividualAddress,
    serial_number: bytes | None,
) -> None:
    """Write a new individual address to a device."""
    await _write_individual_address(
        connection_config, individual_address, serial_number
    )
    click.echo(f"Loaded {individual_address}.")


@address.command(name="unload")
@click.option("--serial-number", type=SERIAL_NUMBER, help=_SERIAL_NUMBER_OPTION_HELP)
@click.pass_obj
@async_command
async def unload(
    connection_config: ConnectionConfig, serial_number: bytes | None
) -> None:
    """Reset a device's individual address to the factory default (15.15.255)."""
    await _write_individual_address(connection_config, UNLOADED_ADDRESS, serial_number)
    click.echo(f"Unloaded - reset to {UNLOADED_ADDRESS}.")


@address.command(name="check")
@click.argument("individual_address", type=INDIVIDUAL_ADDRESS)
@click.pass_context
@async_command
async def check(ctx: click.Context, individual_address: IndividualAddress) -> None:
    """
    Check whether an individual address is occupied on the bus.

    Exits 0 if the address is available (free to use), 1 if it is occupied
    by a device - so this can be used directly in shell conditionals.
    """
    progress(f"Checking address {individual_address}...")
    async with XKNX(connection_config=ctx.obj) as xknx:
        occupied = await nm_individual_address_check(xknx, individual_address)
    click.echo(f"{individual_address} is {'occupied' if occupied else 'available'}.")
    await ctx.aexit(1 if occupied else 0)
