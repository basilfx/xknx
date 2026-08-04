"""Shared helpers for the xknx CLI: parameter types and error handling."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import wraps
import struct
from typing import Any, ParamSpec, TypeVar

import asyncclick as click

from xknx.exceptions import CouldNotParseAddress, XKNXException
from xknx.profile import ResourceDevicePropertyId, ResourceGenericPropertyId
from xknx.telegram.address import (
    DeviceGroupAddress,
    IndividualAddress,
    parse_device_group_address,
)

_P = ParamSpec("_P")
_T = TypeVar("_T")


class _IndividualAddressParamType(click.ParamType[IndividualAddress]):
    """Click parameter type parsing a KNX individual address (e.g. '1.1.1')."""

    name = "individual_address"

    def convert(
        self, value: Any, param: click.Parameter | None, ctx: click.Context | None
    ) -> IndividualAddress:
        """Parse value to an IndividualAddress."""
        try:
            return IndividualAddress(value)
        except CouldNotParseAddress as exc:
            self.fail(str(exc), param, ctx)


class _GroupAddressParamType(click.ParamType[DeviceGroupAddress]):
    """Click parameter type parsing a KNX group address (e.g. '1/2/3')."""

    name = "group_address"

    def convert(
        self, value: Any, param: click.Parameter | None, ctx: click.Context | None
    ) -> DeviceGroupAddress:
        """Parse value to a GroupAddress or InternalGroupAddress."""
        try:
            return parse_device_group_address(value)
        except CouldNotParseAddress as exc:
            self.fail(str(exc), param, ctx)


class _PropertyIdParamType(click.ParamType[int]):
    """Click parameter type parsing a property id: an int, hex int or PID name."""

    name = "property_id"

    def convert(
        self, value: Any, param: click.Parameter | None, ctx: click.Context | None
    ) -> int:
        """Parse value to a property id."""
        if isinstance(value, int):
            return value
        try:
            return int(value, 0)
        except ValueError:
            pass
        name = value.upper()
        for resource in (ResourceGenericPropertyId, ResourceDevicePropertyId):
            try:
                return int(resource[name])
            except KeyError:
                continue
        self.fail(
            f"{value!r} is not a valid property id (expected an integer or a"
            " ResourceGenericPropertyId / ResourceDevicePropertyId name, e.g."
            " PID_SERIAL_NUMBER)",
            param,
            ctx,
        )


class _IntParamType(click.ParamType[int]):
    """Click parameter type parsing a decimal or 0x-prefixed hex integer."""

    name = "int"

    def convert(
        self, value: Any, param: click.Parameter | None, ctx: click.Context | None
    ) -> int:
        """Parse value to an int."""
        if isinstance(value, int):
            return value
        try:
            return int(value, 0)
        except ValueError:
            self.fail(f"{value!r} is not a valid integer.", param, ctx)


class _HexBytesParamType(click.ParamType[bytes]):
    """Click parameter type parsing a hex string (e.g. 'a1b2c3') into bytes."""

    name = "hex_bytes"

    def convert(
        self, value: Any, param: click.Parameter | None, ctx: click.Context | None
    ) -> bytes:
        """Parse value to bytes."""
        try:
            return bytes.fromhex(value)
        except ValueError as exc:
            self.fail(f"{value!r} is not a valid hex string: {exc}", param, ctx)


class _SerialNumberParamType(click.ParamType[bytes]):
    """Click parameter type parsing a 6-byte KNX serial number (hex, colons optional)."""

    name = "serial_number"

    def convert(
        self, value: Any, param: click.Parameter | None, ctx: click.Context | None
    ) -> bytes:
        """Parse value to a 6-byte serial number."""
        try:
            serial = bytes.fromhex(value.replace(":", ""))
        except ValueError as exc:
            self.fail(f"{value!r} is not a valid hex string: {exc}", param, ctx)
        if len(serial) != 6:
            self.fail(f"{value!r} is not a 6-byte serial number.", param, ctx)
        return serial


INDIVIDUAL_ADDRESS = _IndividualAddressParamType()
GROUP_ADDRESS = _GroupAddressParamType()
PROPERTY_ID = _PropertyIdParamType()
INT = _IntParamType()
HEX_BYTES = _HexBytesParamType()
SERIAL_NUMBER = _SerialNumberParamType()


def format_raw_value(raw: int | tuple[int, ...]) -> str:
    """Format a raw group value payload for display."""
    return f"0x{bytes(raw).hex()}" if isinstance(raw, tuple) else str(raw)


def format_hex_dump(data: bytes, start_address: int = 0) -> str:
    """Format bytes as an xxd-style hex dump: offset, hex bytes, then ASCII."""
    lines = []
    for offset in range(0, len(data), 16):
        chunk = data[offset : offset + 16]
        hex_groups = " ".join(chunk[i : i + 2].hex() for i in range(0, len(chunk), 2))
        ascii_repr = "".join(chr(b) if 0x20 <= b < 0x7F else "." for b in chunk)
        lines.append(f"{start_address + offset:08x}: {hex_groups:<39}  {ascii_repr}")
    return "\n".join(lines)


def progress(message: str) -> None:
    """
    Print a status message before a possibly slow bus operation.

    Written to stderr so stdout stays clean for scripting - only the actual
    result of a command goes to stdout.
    """
    click.echo(message, err=True)


def async_command(
    func: Callable[_P, Awaitable[_T]],
) -> Callable[_P, Awaitable[_T]]:
    """Turn library/parsing errors into a friendly ClickException instead of a traceback."""

    @wraps(func)
    async def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _T:
        try:
            return await func(*args, **kwargs)
        except (XKNXException, ValueError, TypeError, OSError, struct.error) as exc:
            raise click.ClickException(str(exc)) from exc

    return wrapper
