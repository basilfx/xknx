"""Tests for `xknx memory` commands."""

from unittest.mock import AsyncMock

from asyncclick.testing import CliRunner

from xknx.cli._common import format_hex_dump
from xknx.cli.main import cli
from xknx.exceptions import ManagementConnectionTimeout
from xknx.telegram import IndividualAddress, Telegram, apci


def _response(address: int, count: int = 1, data: bytes = b"") -> Telegram:
    return Telegram(
        destination_address=IndividualAddress("0.0.0"),
        payload=apci.MemoryResponse(address=address, count=count, data=data),
    )


async def test_memory_read(mock_p2p_connection: AsyncMock) -> None:
    """`memory read` prints the returned data as an xxd-style hex dump."""
    mock_p2p_connection.return_value = _response(
        address=0x0060, count=2, data=b"\xaa\xbb"
    )

    result = await CliRunner().invoke(cli, ["memory", "read", "1.1.1", "0x60"])

    assert result.exit_code == 0, result.output
    assert result.stdout.strip() == format_hex_dump(b"\xaa\xbb", start_address=0x60)
    assert (
        result.stdout.strip() == "00000060: aabb                                     .."
    )
    assert "Reading memory address 0x0060 from 1.1.1..." in result.stderr
    mock_p2p_connection.assert_awaited_once()
    payload = mock_p2p_connection.await_args.kwargs["payload"]
    assert isinstance(payload, apci.MemoryRead)
    assert payload.address == 0x60
    assert payload.count == 1


async def test_memory_read_decimal_address_and_count(
    mock_p2p_connection: AsyncMock,
) -> None:
    """A decimal address and an explicit --count are both accepted."""
    mock_p2p_connection.return_value = _response(address=96, count=4, data=b"\x01" * 4)

    result = await CliRunner().invoke(
        cli, ["memory", "read", "1.1.1", "96", "--count", "4"]
    )

    assert result.exit_code == 0, result.output
    assert result.stdout.strip() == format_hex_dump(b"\x01" * 4, start_address=96)
    payload = mock_p2p_connection.await_args.kwargs["payload"]
    assert payload.address == 96
    assert payload.count == 4


async def test_memory_read_multiline_dump(mock_p2p_connection: AsyncMock) -> None:
    """A read spanning more than 16 bytes wraps onto multiple xxd-style lines."""
    data = bytes(range(20))
    mock_p2p_connection.return_value = _response(address=0x60, count=20, data=data)

    result = await CliRunner().invoke(
        cli, ["memory", "read", "1.1.1", "0x60", "--count", "20"]
    )

    assert result.exit_code == 0, result.output
    lines = result.stdout.strip().splitlines()
    assert len(lines) == 2
    assert lines[0].startswith("00000060:")
    assert lines[1].startswith("00000070:")
    assert result.stdout.strip() == format_hex_dump(data, start_address=0x60)


async def test_memory_read_not_found(mock_p2p_connection: AsyncMock) -> None:
    """count=0 in the response signals the device could not return the data."""
    mock_p2p_connection.return_value = _response(address=0x60, count=0)

    result = await CliRunner().invoke(cli, ["memory", "read", "1.1.1", "0x60"])

    assert result.exit_code == 1
    assert "Memory read failed" in result.output


async def test_memory_read_invalid_address() -> None:
    """A non-numeric address is rejected before any bus access."""
    result = await CliRunner().invoke(cli, ["memory", "read", "1.1.1", "not-a-number"])

    assert result.exit_code == 2
    assert "not a valid integer" in result.output


async def test_memory_read_connection_error(mock_p2p_connection: AsyncMock) -> None:
    """A management connection error becomes a friendly, non-zero-exit message."""
    mock_p2p_connection.side_effect = ManagementConnectionTimeout("no ACK received")

    result = await CliRunner().invoke(cli, ["memory", "read", "1.1.1", "0x60"])

    assert result.exit_code == 1
    assert "no ACK received" in result.output


async def test_memory_write(mock_p2p_connection: AsyncMock) -> None:
    """`memory write` sends the hex-decoded data and reports success."""
    mock_p2p_connection.return_value = _response(
        address=0x60, count=2, data=b"\xaa\xbb"
    )

    result = await CliRunner().invoke(cli, ["memory", "write", "1.1.1", "0x60", "aabb"])

    assert result.exit_code == 0, result.output
    assert "Writing memory address 0x0060 on 1.1.1..." in result.stderr
    payload = mock_p2p_connection.await_args.kwargs["payload"]
    assert isinstance(payload, apci.MemoryWrite)
    assert payload.address == 0x60
    assert payload.data == b"\xaa\xbb"


async def test_memory_write_rejected(mock_p2p_connection: AsyncMock) -> None:
    """count=0 in the response signals the device rejected the write."""
    mock_p2p_connection.return_value = _response(address=0x60, count=0)

    result = await CliRunner().invoke(cli, ["memory", "write", "1.1.1", "0x60", "aabb"])

    assert result.exit_code == 1
    assert "Memory write failed" in result.output


async def test_memory_write_invalid_hex() -> None:
    """An odd-length/non-hex DATA argument is rejected before any bus access."""
    result = await CliRunner().invoke(cli, ["memory", "write", "1.1.1", "0x60", "zz"])

    assert result.exit_code == 2
    assert "not a valid hex string" in result.output
