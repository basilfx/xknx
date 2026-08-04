"""Tests for the top-level `xknx monitor` command."""

from unittest.mock import AsyncMock, Mock, patch

from asyncclick.testing import CliRunner

from xknx.cli.main import cli
from xknx.dpt import DPTBinary
from xknx.telegram import GroupAddress, Telegram
from xknx.telegram.apci import GroupValueRead, GroupValueResponse


async def test_monitor_registers_callback_and_filter() -> None:
    """`monitor` runs in daemon mode and registers the given address filter."""
    mock_xknx = Mock()
    mock_xknx.start = AsyncMock()
    mock_xknx.stop = AsyncMock()

    with patch("xknx.cli.monitor.XKNX", return_value=mock_xknx) as mock_xknx_cls:
        result = await CliRunner().invoke(cli, ["monitor", "--filter", "1/2/*"])

    assert result.exit_code == 0, result.output
    assert "Listening for telegrams (press Ctrl+C to stop)..." in result.stderr
    assert mock_xknx_cls.call_args.kwargs["daemon_mode"] is True
    mock_xknx.telegram_queue.register_telegram_received_cb.assert_called_once()
    _cb, filters = mock_xknx.telegram_queue.register_telegram_received_cb.call_args.args
    assert filters is not None
    assert len(filters) == 1
    assert filters[0].match("1/2/5")
    assert not filters[0].match("3/2/5")
    mock_xknx.start.assert_awaited_once()
    mock_xknx.stop.assert_awaited_once()


async def test_monitor_without_filter_registers_none() -> None:
    """Without --filter, every telegram is shown (address_filters=None)."""
    mock_xknx = Mock()
    mock_xknx.start = AsyncMock()
    mock_xknx.stop = AsyncMock()

    with patch("xknx.cli.monitor.XKNX", return_value=mock_xknx):
        result = await CliRunner().invoke(cli, ["monitor"])

    assert result.exit_code == 0, result.output
    _cb, filters = mock_xknx.telegram_queue.register_telegram_received_cb.call_args.args
    assert filters is None


async def test_monitor_prints_received_telegrams() -> None:
    """The registered callback prints a value telegram and a non-value telegram."""
    sample_telegrams = [
        Telegram(
            destination_address=GroupAddress("1/2/3"),
            payload=GroupValueResponse(DPTBinary(1)),
        ),
        Telegram(destination_address=GroupAddress("1/2/3"), payload=GroupValueRead()),
    ]

    def fake_register(cb: object, _filters: object) -> None:
        # Invoke while CliRunner still captures stdout, unlike the caller.
        for telegram in sample_telegrams:
            cb(telegram)  # type: ignore[operator]

    mock_xknx = Mock()
    mock_xknx.start = AsyncMock()
    mock_xknx.stop = AsyncMock()
    mock_xknx.telegram_queue.register_telegram_received_cb = Mock(
        side_effect=fake_register
    )

    with patch("xknx.cli.monitor.XKNX", return_value=mock_xknx):
        result = await CliRunner().invoke(cli, ["monitor"])

    assert result.exit_code == 0, result.output
    assert "1/2/3: 1" in result.output
    assert "GroupValueRead" in result.output
