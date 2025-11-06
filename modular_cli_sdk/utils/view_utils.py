from __future__ import annotations

import datetime as _dt
import functools
from typing import Any, Callable, Optional, Union, Dict

import click


def _parse_date(
        value: Optional[Union[str, _dt.date]],
) -> Optional[_dt.date]:
    if value is None:
        return None
    if isinstance(value, _dt.date):
        return value
    if isinstance(value, str):
        try:
            return _dt.date.fromisoformat(value)
        except ValueError as e:
            raise ValueError(
                f"Invalid date '{value}'. Expected format YYYY-MM-DD."
            ) from e
    raise TypeError(f"Date must be str or datetime.date, got {type(value)!r}")


def _days_until(
        removal_date: _dt.date,
) -> int:
    return (removal_date - _dt.date.today()).days


def _format_block(
        info: Dict[str, Any],
) -> list[str]:
    """Build deprecation block lines."""
    days_left = _days_until(info["removal_date"])
    removal_str = info["removal_date"].isoformat()
    IND = "  "
    SEP = "=" * 69

    lines = [
        f"{IND}{SEP}",
        f"{IND}WARNING: This command is DEPRECATED"
    ]

    if info.get("deprecated_date"):
        lines.append(
            f"{IND}Deprecated since: {info['deprecated_date'].isoformat()}"
        )

    if info.get("version"):
        lines.append(f"{IND}Deprecated in version: {info['version']}")

    if days_left > 30:
        lines.append(
            f"{IND}Scheduled for removal on: {removal_str} ({days_left} "
            f"days left)"
        )
    elif days_left > 0:
        lines.append(
            f"{IND}Will be REMOVED in {days_left} days on: {removal_str}"
        )
    elif days_left == 0:
        lines.append(f"{IND}Will be REMOVED TODAY on: {removal_str}")
    else:
        lines.append(
            f"{IND}REMOVAL DATE PASSED on: {removal_str} ({abs(days_left)} "
            f"days ago)"
        )

    if info.get("alternative"):
        lines.append(f"{IND}Use instead: {info['alternative']}")

    if info.get("reason"):
        lines.append(f"{IND}Reason: {info['reason']}")

    lines.append(f"{IND}{SEP}")
    return lines


def deprecated(
        *,
        removal_date: Union[str, _dt.date],
        alternative: Optional[str] = None,
        deprecated_date: Optional[Union[str, _dt.date]] = None,
        version: Optional[str] = None,
        reason: Optional[str] = None,
        enforce_removal: bool = False,
) -> Callable[
    [Union[Callable[..., Any], click.Command]], Union[Callable[..., Any], click.Command]
]:
    """
    Decorator for marking Click commands/functions as deprecated.

    Shows a runtime warning and injects a block into --help.

    Args:
        removal_date: Date when command will be removed (YYYY-MM-DD)
        alternative: Suggested replacement command
        deprecated_date: Date when deprecation started (YYYY-MM-DD)
        version: Version where deprecation was introduced
        reason: Explanation for deprecation
        enforce_removal: If True, raises error after removal_date passes
    """
    removal_d = _parse_date(removal_date)
    if not removal_d:
        raise ValueError("removal_date is required and must be YYYY-MM-DD")
    deprecated_d = _parse_date(deprecated_date)
    if alternative is not None and not isinstance(alternative, str):
        raise ValueError("alternative must be a string if provided")

    base_info = dict(
        removal_date=removal_d,
        alternative=alternative,
        deprecated_date=deprecated_d,
        version=version,
        reason=reason,
    )

    def _emit_warning():
        days_left = _days_until(removal_d)

        # Check if removal date has passed and enforcement is enabled
        if enforce_removal and days_left < 0:
            click.secho("  " + "=" * 69, fg="red", bold=True, err=True)
            click.secho(
                message="  ERROR: This command has been REMOVED!",
                fg="red",
                bold=True,
                err=True,
            )
            click.secho(
                message=(
                    f"  Removal date: {removal_d.isoformat()} ({abs(days_left)}"
                    f" days ago)"
                ),
                fg="red",
                bold=True,
                err=True,
            )
            if alternative:
                click.secho(
                    message=f"  Use instead: {alternative}",
                    fg="red",
                    bold=True,
                    err=True,
                )
            click.secho("  " + "=" * 69, fg="red", bold=True, err=True)
            raise click.UsageError(
                f"Command removed on {removal_d.isoformat()}. Use: "
                f"{alternative if alternative else 'See documentation for alternatives'}"
            )

        # Show warning
        color = "yellow" if days_left > 30 else "red"
        for line in _format_block(base_info):
            click.secho(
                message=line,
                fg=color,
                bold=True,
                err=True,
            )

    def _decorate_function(
            func: Callable[..., Any],
    ) -> Callable[..., Any]:
        # Prepend deprecation block to docstring
        deprecation_text = "\n".join(_format_block(base_info))
        original_doc = func.__doc__ or ''
        func.__doc__ = f"{deprecation_text}\n\n{original_doc}"

        @functools.wraps(func)
        def _wrapper(*args, **kwargs):
            _emit_warning()
            return func(*args, **kwargs)

        _wrapper.__doc__ = func.__doc__
        return _wrapper

    def _decorate_command(
            cmd: click.Command,
    ) -> click.Command:
        original_help = cmd.help
        orig_cb = cmd.callback or (lambda *a, **kw: None)

        @functools.wraps(orig_cb)
        def wrapped_cb(*args, **kwargs):
            _emit_warning()
            return orig_cb(*args, **kwargs)

        cmd.callback = wrapped_cb

        def format_help(
                ctx: click.Context,
                formatter: click.HelpFormatter,
        ) -> None:
            """Custom help formatter that injects deprecation warning."""

            # 1. Write Usage section
            pieces = cmd.collect_usage_pieces(ctx)
            formatter.write_usage(
                prog=ctx.command_path,
                args=' '.join(pieces) if pieces else '',
            )
            formatter.write_paragraph()

            # 2. Write deprecation block WITH COLORS
            days_left = _days_until(base_info["removal_date"])
            color = "yellow" if days_left > 30 else "red"

            for line in _format_block(base_info):
                # Apply color styling
                styled_line = click.style(line, fg=color, bold=True)
                formatter.write(styled_line)
                formatter.write('\n')
            formatter.write_paragraph()

            # 3. Write command description/help
            help_text = original_help or ''
            if isinstance(help_text, str) and help_text:
                formatter.indent()
                formatter.write_text(help_text)
                formatter.dedent()

            # 4. Write Options section
            cmd.format_options(ctx, formatter)

            # 5. Write epilog if present
            if cmd.epilog:
                formatter.write_paragraph()
                epilog_text = cmd.epilog if isinstance(cmd.epilog, str) \
                    else str(cmd.epilog)
                formatter.write_text(epilog_text)

        cmd.format_help = format_help
        return cmd

    def _decorator(
            target: Union[Callable[..., Any], click.Command],
    ) -> Union[Callable[..., Any], click.Command]:
        if isinstance(target, click.Command):
            return _decorate_command(target)
        if callable(target):
            return _decorate_function(target)
        raise TypeError(
            "@deprecated can only decorate a function or click.Command."
        )

    return _decorator
