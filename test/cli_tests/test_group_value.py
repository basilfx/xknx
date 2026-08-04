"""Tests for `xknx group-value` commands."""

from unittest.mock import AsyncMock, patch

from asyncclick.testing import CliRunner

from xknx.cli.main import cli
from xknx.dpt import DPTBase, DPTBinary
from xknx.telegram import GroupAddress, Telegram
from xknx.telegram.apci import GroupValueResponse


async def test_group_write_raw_int() -> None:
    """Without --dpt, an integer value is sent as a raw payload."""
    with patch("xknx.cli.group_value.group_value_write") as mock_write:
        result = await CliRunner().invoke(cli, ["group-value", "write", "1/2/3", "42"])

    assert result.exit_code == 0, result.output
    mock_write.assert_called_once()
    args, kwargs = mock_write.call_args
    assert args[1] == GroupAddress("1/2/3")
    assert args[2] == 42
    assert kwargs["value_type"] is None
    assert "Writing to 1/2/3..." in result.stderr


async def test_group_write_raw_hex() -> None:
    """Without --dpt, a hex byte string is sent as a raw payload."""
    with patch("xknx.cli.group_value.group_value_write") as mock_write:
        result = await CliRunner().invoke(
            cli, ["group-value", "write", "1/2/3", "aabb"]
        )

    assert result.exit_code == 0, result.output
    args, _ = mock_write.call_args
    assert args[2] == [0xAA, 0xBB]


async def test_group_write_with_dpt() -> None:
    """--dpt is forwarded to group_value_write, which encodes the raw value."""
    with patch("xknx.cli.group_value.group_value_write") as mock_write:
        result = await CliRunner().invoke(
            cli, ["group-value", "write", "--dpt", "temperature", "1/2/3", "21.5"]
        )

    assert result.exit_code == 0, result.output
    args, kwargs = mock_write.call_args
    assert args[2] == 21.5
    assert kwargs["value_type"] == "temperature"


async def test_group_write_with_enum_dpt() -> None:
    """A non-numeric --dpt (e.g. an enum) passes the raw string value through."""
    with patch("xknx.cli.group_value.group_value_write") as mock_write:
        result = await CliRunner().invoke(
            cli, ["group-value", "write", "--dpt", "switch", "1/2/3", "on"]
        )

    assert result.exit_code == 0, result.output
    args, kwargs = mock_write.call_args
    assert args[2] == "on"
    assert kwargs["value_type"] == "switch"


async def test_group_write_invalid_raw_value() -> None:
    """A non-numeric, non-hex value without --dpt is rejected before any bus access."""
    result = await CliRunner().invoke(
        cli, ["group-value", "write", "1/2/3", "not-a-number"]
    )

    assert result.exit_code == 1
    assert "not a valid raw value" in result.output


async def test_group_write_invalid_group_address() -> None:
    """An invalid group address is rejected by the parameter type."""
    result = await CliRunner().invoke(cli, ["group-value", "write", "not-a-ga", "1"])

    assert result.exit_code == 2


async def test_group_read_raw() -> None:
    """Without --dpt, the raw payload value is printed."""
    telegram = Telegram(
        destination_address=GroupAddress("1/2/3"),
        payload=GroupValueResponse(DPTBinary(1)),
    )
    with patch("xknx.cli.group_value.ValueReader") as mock_reader_cls:
        mock_reader_cls.return_value.read = AsyncMock(return_value=telegram)
        result = await CliRunner().invoke(cli, ["group-value", "read", "1/2/3"])

    assert result.exit_code == 0, result.output
    assert result.stdout.strip() == "1"
    assert "Reading 1/2/3..." in result.stderr


async def test_group_read_with_dpt() -> None:
    """With --dpt, the response is decoded using that data point type."""
    transcoder = DPTBase.get_dpt("temperature")
    encoded = transcoder.to_knx(21.5)
    telegram = Telegram(
        destination_address=GroupAddress("5/1/20"),
        payload=GroupValueResponse(encoded),
    )
    with patch("xknx.cli.group_value.ValueReader") as mock_reader_cls:
        mock_reader_cls.return_value.read = AsyncMock(return_value=telegram)
        result = await CliRunner().invoke(
            cli, ["group-value", "read", "--dpt", "temperature", "5/1/20"]
        )

    assert result.exit_code == 0, result.output
    assert result.stdout.strip() == str(transcoder.from_knx(encoded))


async def test_group_read_timeout() -> None:
    """No response within the timeout is a clear, non-zero-exit error."""
    with patch("xknx.cli.group_value.ValueReader") as mock_reader_cls:
        mock_reader_cls.return_value.read = AsyncMock(return_value=None)
        result = await CliRunner().invoke(
            cli, ["group-value", "read", "1/2/3", "--timeout", "0.1"]
        )

    assert result.exit_code == 1
    assert "No response received" in result.output
