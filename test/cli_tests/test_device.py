"""Tests for `xknx device` commands."""

from unittest.mock import AsyncMock, patch

from asyncclick.testing import CliRunner

from xknx.cli.main import cli
from xknx.exceptions import ManagementConnectionError
from xknx.telegram import IndividualAddress, Telegram, apci

_DEVICE = IndividualAddress("1.1.1")
_SERIAL = bytes.fromhex("aabbccddeeff")


async def test_device_restart() -> None:
    """`device restart` calls dm_restart with the given address."""
    with patch("xknx.cli.device.dm_restart", new=AsyncMock()) as mock_restart:
        result = await CliRunner().invoke(cli, ["device", "restart", "1.1.1"])

    assert result.exit_code == 0, result.output
    assert "Restarting 1.1.1..." in result.stderr
    assert "Restarted 1.1.1" in result.stdout
    mock_restart.assert_awaited_once()
    assert mock_restart.await_args.args[1] == _DEVICE


async def test_device_info(mock_p2p_connection: AsyncMock) -> None:
    """`device info` reads the mask version, manufacturer id and serial number."""
    mock_p2p_connection.side_effect = [
        Telegram(
            destination_address=_DEVICE,
            payload=apci.DeviceDescriptorResponse(descriptor=0, value=0x07B0),
        ),
        Telegram(
            destination_address=_DEVICE,
            payload=apci.PropertyValueResponse(
                property_id=12, count=1, data=b"\x00\x01"
            ),
        ),
        Telegram(
            destination_address=_DEVICE,
            payload=apci.PropertyValueResponse(
                property_id=11, count=1, data=b"\x00\x01\x02\x03\x04\x05"
            ),
        ),
    ]

    result = await CliRunner().invoke(cli, ["device", "info", "1.1.1"])

    assert result.exit_code == 0, result.output
    assert "Requesting information from 1.1.1..." in result.stderr
    assert result.stdout == (
        f"{'Individual address:':<20} 1.1.1\n"
        f"{'Mask version:':<20} 07B0\n"
        f"{'Manufacturer id:':<20} 1\n"
        f"{'Serial number:':<20} 0001:02030405\n"
    )


async def test_device_info_unknown_properties(mock_p2p_connection: AsyncMock) -> None:
    """A count=0 property response is shown as 'unknown' instead of failing outright."""
    mock_p2p_connection.side_effect = [
        Telegram(
            destination_address=_DEVICE,
            payload=apci.DeviceDescriptorResponse(descriptor=0, value=0x07B0),
        ),
        Telegram(
            destination_address=_DEVICE,
            payload=apci.PropertyValueResponse(property_id=12, count=0),
        ),
        Telegram(
            destination_address=_DEVICE,
            payload=apci.PropertyValueResponse(property_id=11, count=0),
        ),
    ]

    result = await CliRunner().invoke(cli, ["device", "info", "1.1.1"])

    assert result.exit_code == 0, result.output
    assert f"{'Manufacturer id:':<20} unknown" in result.output
    assert f"{'Serial number:':<20} unknown" in result.output


async def test_device_discover_found() -> None:
    """`device discover` prints the found address."""
    with patch(
        "xknx.cli.device.nm_individual_address_read",
        new=AsyncMock(return_value=[_DEVICE]),
    ):
        result = await CliRunner().invoke(cli, ["device", "discover"])

    assert result.exit_code == 0, result.output
    assert "Searching for a device in programming mode..." in result.stderr
    assert result.stdout.strip() == "1.1.1"


async def test_device_discover_not_found() -> None:
    """No device in programming mode is a clear, non-zero-exit error."""
    with patch(
        "xknx.cli.device.nm_individual_address_read",
        new=AsyncMock(return_value=[]),
    ):
        result = await CliRunner().invoke(cli, ["device", "discover"])

    assert result.exit_code == 1
    assert "No device in programming mode found" in result.output


async def test_device_flash(mock_p2p_connection: AsyncMock) -> None:
    """`device flash` turns programming mode on, waits, then turns it off."""
    mock_p2p_connection.return_value = Telegram(
        destination_address=_DEVICE,
        payload=apci.PropertyValueResponse(property_id=54, count=1, data=b"\x01"),
    )

    with patch("xknx.cli.device.asyncio.sleep", new=AsyncMock()) as mock_sleep:
        result = await CliRunner().invoke(
            cli, ["device", "flash", "1.1.1", "--timeout", "2.5"]
        )

    assert result.exit_code == 0, result.output
    assert "Flashing 1.1.1 for 2.5s..." in result.stderr
    assert "Stopped flashing 1.1.1." in result.stdout
    mock_sleep.assert_awaited_once_with(2.5)
    assert mock_p2p_connection.await_count == 2
    on_payload = mock_p2p_connection.await_args_list[0].kwargs["payload"]
    off_payload = mock_p2p_connection.await_args_list[1].kwargs["payload"]
    assert isinstance(on_payload, apci.PropertyValueWrite)
    assert on_payload.property_id == 54
    assert on_payload.data == b"\x01"
    assert isinstance(off_payload, apci.PropertyValueWrite)
    assert off_payload.property_id == 54
    assert off_payload.data == b"\x00"


async def test_device_flash_enable_failed(mock_p2p_connection: AsyncMock) -> None:
    """count=0 while enabling programming mode fails clearly and never sleeps."""
    mock_p2p_connection.return_value = Telegram(
        destination_address=_DEVICE,
        payload=apci.PropertyValueResponse(property_id=54, count=0),
    )

    with patch("xknx.cli.device.asyncio.sleep", new=AsyncMock()) as mock_sleep:
        result = await CliRunner().invoke(cli, ["device", "flash", "1.1.1"])

    assert result.exit_code == 1
    assert "Failed to enable programming mode on 1.1.1." in result.output
    mock_sleep.assert_not_awaited()


async def test_device_flash_disable_failed(mock_p2p_connection: AsyncMock) -> None:
    """count=0 while disabling programming mode afterwards is reported clearly."""
    mock_p2p_connection.side_effect = [
        Telegram(
            destination_address=_DEVICE,
            payload=apci.PropertyValueResponse(property_id=54, count=1, data=b"\x01"),
        ),
        Telegram(
            destination_address=_DEVICE,
            payload=apci.PropertyValueResponse(property_id=54, count=0),
        ),
    ]

    with patch("xknx.cli.device.asyncio.sleep", new=AsyncMock()):
        result = await CliRunner().invoke(cli, ["device", "flash", "1.1.1"])

    assert result.exit_code == 1
    assert "Failed to disable programming mode on 1.1.1." in result.output


async def test_device_address_load_programming_mode() -> None:
    """Without --serial-number, the device in programming mode is loaded."""
    with patch(
        "xknx.cli.device.nm_individual_address_write", new=AsyncMock()
    ) as mock_write:
        result = await CliRunner().invoke(cli, ["device", "address", "load", "1.1.1"])

    assert result.exit_code == 0, result.output
    assert "Writing address 1.1.1 to device in programming mode..." in result.stderr
    assert "Loaded 1.1.1." in result.stdout
    mock_write.assert_awaited_once()
    assert mock_write.await_args.args[1] == _DEVICE


async def test_device_address_load_with_serial_number() -> None:
    """--serial-number loads the device directly, without programming mode."""
    with patch(
        "xknx.cli.device.nm_individual_address_serial_number_write", new=AsyncMock()
    ) as mock_write:
        result = await CliRunner().invoke(
            cli,
            [
                "device",
                "address",
                "load",
                "1.1.1",
                "--serial-number",
                "aabbccddeeff",
            ],
        )

    assert result.exit_code == 0, result.output
    assert (
        "Writing address 1.1.1 to device with serial number aabbccddeeff..."
        in result.stderr
    )
    assert "Loaded 1.1.1." in result.stdout
    mock_write.assert_awaited_once()
    assert mock_write.await_args.args[1] == _SERIAL
    assert mock_write.await_args.args[2] == _DEVICE


async def test_device_address_load_with_colon_separated_serial() -> None:
    """Serial numbers may be given in the same 'xx:xxxxxx' form `device info` prints."""
    with patch(
        "xknx.cli.device.nm_individual_address_serial_number_write", new=AsyncMock()
    ) as mock_write:
        result = await CliRunner().invoke(
            cli,
            [
                "device",
                "address",
                "load",
                "1.1.1",
                "--serial-number",
                "aa:bbccddeeff",
            ],
        )

    assert result.exit_code == 0, result.output
    assert mock_write.await_args.args[1] == _SERIAL


async def test_device_address_load_invalid_serial_hex() -> None:
    """A non-hex serial number is rejected before any bus access."""
    result = await CliRunner().invoke(
        cli, ["device", "address", "load", "1.1.1", "--serial-number", "zz"]
    )

    assert result.exit_code == 2
    assert "not a valid hex string" in result.output


async def test_device_address_load_invalid_serial_length() -> None:
    """A serial number that isn't 6 bytes is rejected before any bus access."""
    result = await CliRunner().invoke(
        cli, ["device", "address", "load", "1.1.1", "--serial-number", "aabb"]
    )

    assert result.exit_code == 2
    assert "not a 6-byte serial number" in result.output


async def test_device_address_load_error() -> None:
    """A management error (e.g. no device in programming mode) is shown clearly."""
    with patch(
        "xknx.cli.device.nm_individual_address_write",
        new=AsyncMock(
            side_effect=ManagementConnectionError(
                "No device in programming mode detected."
            )
        ),
    ):
        result = await CliRunner().invoke(cli, ["device", "address", "load", "1.1.1"])

    assert result.exit_code == 1
    assert "No device in programming mode detected." in result.output


async def test_device_address_unload_programming_mode() -> None:
    """Without --serial-number, the device in programming mode is reset to 15.15.255."""
    with patch(
        "xknx.cli.device.nm_individual_address_write", new=AsyncMock()
    ) as mock_write:
        result = await CliRunner().invoke(cli, ["device", "address", "unload"])

    assert result.exit_code == 0, result.output
    assert "Writing address 15.15.255 to device in programming mode..." in result.stderr
    assert "Unloaded - reset to 15.15.255." in result.stdout
    mock_write.assert_awaited_once()
    assert mock_write.await_args.args[1] == IndividualAddress("15.15.255")


async def test_device_address_unload_with_serial_number() -> None:
    """--serial-number resets a specific device directly, without programming mode."""
    with patch(
        "xknx.cli.device.nm_individual_address_serial_number_write", new=AsyncMock()
    ) as mock_write:
        result = await CliRunner().invoke(
            cli,
            ["device", "address", "unload", "--serial-number", "aabbccddeeff"],
        )

    assert result.exit_code == 0, result.output
    mock_write.assert_awaited_once()
    assert mock_write.await_args.args[1] == _SERIAL
    assert mock_write.await_args.args[2] == IndividualAddress("15.15.255")


async def test_device_address_check_available() -> None:
    """An unoccupied address exits 0 and reports 'available'."""
    with patch(
        "xknx.cli.device.nm_individual_address_check",
        new=AsyncMock(return_value=False),
    ):
        result = await CliRunner().invoke(cli, ["device", "address", "check", "1.1.1"])

    assert result.exit_code == 0, result.output
    assert "Checking address 1.1.1..." in result.stderr
    assert "1.1.1 is available." in result.stdout


async def test_device_address_check_occupied() -> None:
    """An occupied address exits 1 and reports 'occupied', for shell conditionals."""
    with patch(
        "xknx.cli.device.nm_individual_address_check",
        new=AsyncMock(return_value=True),
    ):
        result = await CliRunner().invoke(cli, ["device", "address", "check", "1.1.1"])

    assert result.exit_code == 1
    assert "1.1.1 is occupied." in result.stdout
