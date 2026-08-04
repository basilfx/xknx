"""Top-level `xknx completion` command: shell completion script generation."""

from __future__ import annotations

import asyncclick as click
from asyncclick.shell_completion import get_completion_class


@click.command(name="completion")
@click.argument("shell", type=click.Choice(["bash", "zsh", "fish"]))
@click.pass_context
def completion(ctx: click.Context, shell: str) -> None:
    """
    Print a shell completion script for SHELL.

    Add to your shell profile to enable tab completion, e.g. for zsh in
    ~/.zshrc:

        eval "$(xknx completion zsh)"

    Or generate it once and load it as a function for faster shell startup:

        xknx completion zsh > ~/.zfunc/_xknx
        # with `fpath+=~/.zfunc` and `autoload -Uz compinit && compinit`
        # somewhere earlier in ~/.zshrc
    """
    root_ctx = ctx.find_root()
    prog_name = root_ctx.info_name or "xknx"
    complete_name = prog_name.replace("-", "_").replace(".", "_")
    complete_var = f"_{complete_name}_COMPLETE".upper()

    complete_cls = get_completion_class(shell)
    if complete_cls is None:
        raise click.ClickException(f"Shell {shell!r} is not supported.")

    click.echo(complete_cls(root_ctx.command, {}, prog_name, complete_var).source())
