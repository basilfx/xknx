"""Tests for the top-level `xknx completion` command."""

from asyncclick.testing import CliRunner

from xknx.cli.main import cli


async def test_completion_zsh() -> None:
    """`completion zsh` prints a zsh completion script wired to _XKNX_COMPLETE."""
    result = await CliRunner().invoke(cli, ["completion", "zsh"])

    assert result.exit_code == 0, result.output
    assert "#compdef xknx" in result.output
    assert "_XKNX_COMPLETE=zsh_complete xknx" in result.output


async def test_completion_bash() -> None:
    """`completion bash` prints a bash completion script."""
    result = await CliRunner().invoke(cli, ["completion", "bash"])

    assert result.exit_code == 0, result.output
    assert "_XKNX_COMPLETE=bash_complete" in result.output


async def test_completion_fish() -> None:
    """`completion fish` prints a fish completion script."""
    result = await CliRunner().invoke(cli, ["completion", "fish"])

    assert result.exit_code == 0, result.output
    assert "_XKNX_COMPLETE=fish_complete" in result.output


async def test_completion_invalid_shell() -> None:
    """An unsupported shell is rejected by the parameter type."""
    result = await CliRunner().invoke(cli, ["completion", "powershell"])

    assert result.exit_code == 2


async def test_shell_completion_protocol_resolves_subcommands() -> None:
    """
    The completion protocol the generated script shells out to actually works.

    _XKNX_COMPLETE is asyncclick's own env-var completion trigger (checked by
    every command's main()/__call__(), not something xknx.cli implements) -
    this confirms the `xknx` console script is wired up correctly for it, not
    just that `completion zsh` prints a plausible-looking script.
    """
    result = await CliRunner().invoke(
        cli,
        [],
        env={
            "COMP_WORDS": "xknx group-",
            "COMP_CWORD": "1",
            "_XKNX_COMPLETE": "zsh_complete",
        },
    )

    assert result.exit_code == 0, result.output
    assert "group-value" in result.output
