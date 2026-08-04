"""Tests for `xknx property-value` commands."""

from unittest.mock import AsyncMock

from asyncclick.testing import CliRunner

from xknx.cli.main import cli
from xknx.exceptions import ManagementConnectionTimeout
from xknx.telegram import IndividualAddress, Telegram, apci


def _response(
    property_id: int,
    count: int = 1,
    object_index: int = 0,
    start_index: int = 1,
    data: bytes = b"",
) -> Telegram:
    return Telegram(
        destination_address=IndividualAddress("0.0.0"),
        payload=apci.PropertyValueResponse(
            object_index=object_index,
            property_id=property_id,
            count=count,
            start_index=start_index,
            data=data,
        ),
    )


async def test_property_read(mock_p2p_connection: AsyncMock) -> None:
    """`property-value read` prints the returned data as hex."""
    mock_p2p_connection.return_value = _response(
        property_id=11, count=1, data=b"\xaa\xbb"
    )

    result = await CliRunner().invoke(
        cli, ["property-value", "read", "1.1.1", "PID_SERIAL_NUMBER"]
    )

    assert result.exit_code == 0, result.output
    assert result.stdout.strip() == "aabb"
    assert "Reading property 11 from 1.1.1..." in result.stderr
    mock_p2p_connection.assert_awaited_once()
    payload = mock_p2p_connection.await_args.kwargs["payload"]
    assert isinstance(payload, apci.PropertyValueRead)
    assert payload.property_id == 11
    assert payload.object_index == 0
    assert payload.count == 1
    assert payload.start_index == 1


async def test_property_read_by_int_id(mock_p2p_connection: AsyncMock) -> None:
    """A raw integer property id is accepted as well as a PID name."""
    mock_p2p_connection.return_value = _response(
        property_id=12, count=1, data=b"\x00\x01"
    )

    result = await CliRunner().invoke(cli, ["property-value", "read", "1.1.1", "12"])

    assert result.exit_code == 0, result.output
    assert result.stdout.strip() == "0001"


async def test_property_read_not_found(mock_p2p_connection: AsyncMock) -> None:
    """count=0 in the response signals the property does not exist."""
    mock_p2p_connection.return_value = _response(property_id=11, count=0)

    result = await CliRunner().invoke(
        cli, ["property-value", "read", "1.1.1", "PID_SERIAL_NUMBER"]
    )

    assert result.exit_code == 1
    assert "Property read failed" in result.output


async def test_property_read_unknown_pid() -> None:
    """An unresolvable PID name is rejected before any bus access."""
    result = await CliRunner().invoke(
        cli, ["property-value", "read", "1.1.1", "NOT_A_PID"]
    )

    assert result.exit_code == 2
    assert "not a valid property id" in result.output


async def test_property_read_invalid_individual_address() -> None:
    """An invalid individual address is rejected before any bus access."""
    result = await CliRunner().invoke(
        cli, ["property-value", "read", "not-an-address", "PID_SERIAL_NUMBER"]
    )

    assert result.exit_code == 2


async def test_property_read_connection_error(mock_p2p_connection: AsyncMock) -> None:
    """A management connection error becomes a friendly, non-zero-exit message."""
    mock_p2p_connection.side_effect = ManagementConnectionTimeout("no ACK received")

    result = await CliRunner().invoke(
        cli, ["property-value", "read", "1.1.1", "PID_SERIAL_NUMBER"]
    )

    assert result.exit_code == 1
    assert "no ACK received" in result.output


async def test_property_write(mock_p2p_connection: AsyncMock) -> None:
    """`property-value write` sends the hex-decoded data and reports success."""
    mock_p2p_connection.return_value = _response(
        property_id=11, count=1, data=b"\xaa\xbb"
    )

    result = await CliRunner().invoke(
        cli, ["property-value", "write", "1.1.1", "PID_SERIAL_NUMBER", "aabb"]
    )

    assert result.exit_code == 0, result.output
    assert "Writing property 11 on 1.1.1..." in result.stderr
    payload = mock_p2p_connection.await_args.kwargs["payload"]
    assert isinstance(payload, apci.PropertyValueWrite)
    assert payload.data == b"\xaa\xbb"
    assert payload.property_id == 11


async def test_property_write_rejected(mock_p2p_connection: AsyncMock) -> None:
    """count=0 in the response signals the device rejected the write."""
    mock_p2p_connection.return_value = _response(property_id=11, count=0)

    result = await CliRunner().invoke(
        cli, ["property-value", "write", "1.1.1", "PID_SERIAL_NUMBER", "aabb"]
    )

    assert result.exit_code == 1
    assert "Property write failed" in result.output


async def test_property_write_invalid_hex() -> None:
    """An odd-length/non-hex DATA argument is rejected before any bus access."""
    result = await CliRunner().invoke(
        cli, ["property-value", "write", "1.1.1", "PID_SERIAL_NUMBER", "zz"]
    )

    assert result.exit_code == 2
    assert "not a valid hex string" in result.output
