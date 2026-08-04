"""Tests for the top-level `xknx` group: connection option resolution."""

import logging
from unittest.mock import patch

from asyncclick.testing import CliRunner

from xknx.cli.main import cli
from xknx.io import ConnectionType


async def test_secure_requires_routing_or_tunneling_tcp() -> None:
    """--secure is rejected for --connection=automatic/tunneling."""
    result = await CliRunner().invoke(
        cli, ["--connection", "tunneling", "--secure", "group-value", "read", "1/2/3"]
    )

    assert result.exit_code == 2
    assert "--secure can only be used with" in result.output


async def test_connection_config_from_flags() -> None:
    """Global flags are resolved into a matching ConnectionConfig on ctx.obj."""
    with patch("xknx.cli.group_value.group_value_write") as mock_write:
        result = await CliRunner().invoke(
            cli,
            [
                "--connection",
                "routing",
                "--secure",
                "--gateway-ip",
                "10.1.0.40",
                "group-value",
                "write",
                "1/2/3",
                "1",
            ],
        )

    assert result.exit_code == 0, result.output
    connection_config = mock_write.call_args.args[0].knxip_interface.connection_config
    assert connection_config.connection_type is ConnectionType.ROUTING_SECURE
    assert connection_config.gateway_ip == "10.1.0.40"


async def test_connection_config_from_env_vars() -> None:
    """Connection options fall back to their XKNX_* environment variables."""
    with patch("xknx.cli.group_value.group_value_write") as mock_write:
        result = await CliRunner().invoke(
            cli,
            ["group-value", "write", "1/2/3", "1"],
            env={"XKNX_CONNECTION": "tunneling", "XKNX_GATEWAY_IP": "10.1.0.41"},
        )

    assert result.exit_code == 0, result.output
    connection_config = mock_write.call_args.args[0].knxip_interface.connection_config
    assert connection_config.connection_type is ConnectionType.TUNNELING
    assert connection_config.gateway_ip == "10.1.0.41"


async def test_secure_config_from_flags() -> None:
    """Secure options are collected into a SecureConfig on the ConnectionConfig."""
    with patch("xknx.cli.group_value.group_value_write") as mock_write:
        result = await CliRunner().invoke(
            cli,
            [
                "--connection",
                "routing",
                "--secure",
                "--backbone-key",
                "00112233445566778899aabbccddeeff",
                "--knxkeys-password",
                "secret",
                "group-value",
                "write",
                "1/2/3",
                "1",
            ],
        )

    assert result.exit_code == 0, result.output
    connection_config = mock_write.call_args.args[0].knxip_interface.connection_config
    assert connection_config.secure_config is not None
    assert connection_config.secure_config.backbone_key == bytes.fromhex(
        "00112233445566778899aabbccddeeff"
    )
    assert connection_config.secure_config.knxkeys_password == "secret"


async def test_debug_flag_enables_debug_logging() -> None:
    """--debug raises the xknx.log logger to DEBUG level."""
    logger = logging.getLogger("xknx.log")
    previous_level = logger.level
    try:
        with patch("xknx.cli.group_value.group_value_write"):
            result = await CliRunner().invoke(
                cli, ["--debug", "group-value", "write", "1/2/3", "1"]
            )
        assert result.exit_code == 0, result.output
        assert logger.level == logging.DEBUG
    finally:
        logger.setLevel(previous_level)
