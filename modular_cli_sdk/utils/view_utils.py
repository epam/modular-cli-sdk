from __future__ import annotations

import datetime as _dt
import functools
from typing import Any, Callable, Optional, Union, Dict, TypeVar

import click

G = TypeVar('G', bound=click.MultiCommand)


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
        entity_type: str = "command",
) -> list[str]:
    """Build deprecation block lines."""
    days_left = _days_until(info["removal_date"])
    removal_str = info["removal_date"].isoformat()
    SEP = "=" * 69

    lines = [
        SEP,
        f"WARNING: This {entity_type} is DEPRECATED"
    ]

    if info.get("deprecated_date"):
        lines.append(
            f"Deprecated since: {info['deprecated_date'].isoformat()}"
        )

    if info.get("version"):
        lines.append(f"Deprecated in version: {info['version']}")

    if days_left > 30:
        lines.append(
            f"Scheduled for removal on: {removal_str} ({days_left} days left)"
        )
    elif days_left > 0:
        lines.append(
            f"Will be REMOVED in {days_left} days on: {removal_str}"
        )
    elif days_left == 0:
        lines.append(f"Will be REMOVED TODAY on: {removal_str}")
    else:
        lines.append(
            f"REMOVAL DATE PASSED on: {removal_str} ({abs(days_left)} days ago)"
        )

    if info.get("alternative"):
        lines.append(f"Use instead: {info['alternative']}")

    if info.get("reason"):
        lines.append(f"Reason: {info['reason']}")

    lines.append(SEP)
    return lines


def deprecated_command(
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
    For Click groups, use @deprecated_group instead.

    Args:
        removal_date: Date when command will be removed (YYYY-MM-DD)
        alternative: Suggested replacement command
        deprecated_date: Date when deprecation started (YYYY-MM-DD)
        version: Version where deprecation was introduced
        reason: Explanation for deprecation
        enforce_removal: If True, raises error after removal_date passes

    Example:
        @deprecated_command(
            removal_date='2027-01-01',
            deprecated_date='2025-06-01',
            reason='Feature removed',
            alternative='m3admin new-cmd'
        )
        @cli.command()
        def old_cmd():
            pass
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
            click.secho("=" * 69, fg="red", bold=True, err=True)
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
            click.secho("=" * 69, fg="red", bold=True, err=True)
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
            cmd.format_usage(ctx, formatter)

            # Write deprecation block with colors
            days_left = _days_until(base_info["removal_date"])
            color = "yellow" if days_left > 30 else "red"

            formatter.write_paragraph()
            for line in _format_block(base_info):
                styled_line = click.style(line, fg=color, bold=True)
                formatter.write(styled_line)
                formatter.write('\n')

            cmd.format_help_text(ctx, formatter)
            cmd.format_options(ctx, formatter)
            cmd.format_epilog(ctx, formatter)

        cmd.format_help = format_help
        return cmd

    def _decorator(
            target: Union[Callable[..., Any], click.Command],
    ) -> Union[Callable[..., Any], click.Command]:
        if isinstance(target, click.MultiCommand):
            raise TypeError(
                "@deprecated_command cannot be used on click.Group/MultiCommand. "
                "Use @deprecated_group instead."
            )
        if isinstance(target, click.Command):
            return _decorate_command(target)
        if callable(target):
            return _decorate_function(target)
        raise TypeError(
            "@deprecated_command can only decorate a function or click.Command."
        )

    return _decorator


def deprecated_group(
        *,
        removal_date: Union[str, _dt.date],
        alternative: Optional[str] = None,
        deprecated_date: Optional[Union[str, _dt.date]] = None,
        version: Optional[str] = None,
        reason: Optional[str] = None,
        enforce_removal: bool = False,
        warn_on_subcommands: bool = True,
) -> Callable[[G], G]:
    """
    Decorator for marking Click groups/multi-commands as deprecated.

    Shows a runtime warning and injects a block into --help.

    Args:
        removal_date: Date when group will be removed (YYYY-MM-DD)
        alternative: Suggested replacement
        deprecated_date: Date when deprecation started (YYYY-MM-DD)
        version: Version where deprecation was introduced
        reason: Explanation for deprecation
        enforce_removal: If True, raises error after removal_date passes
        warn_on_subcommands: If True (default), shows warning when any
                            subcommand is executed (not when viewing
                            subcommand help)

    Example:
        @deprecated_group(
            removal_date='2027-01-01',
            deprecated_date='2025-06-01',
            reason='Integration being removed',
        )
        @cli.group()
        def old_group():
            pass
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

        if enforce_removal and days_left < 0:
            click.secho("=" * 69, fg="red", bold=True, err=True)
            click.secho(
                message="  ERROR: This command group has been REMOVED!",
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
            click.secho("=" * 69, fg="red", bold=True, err=True)
            raise click.UsageError(
                f"Command group removed on {removal_d.isoformat()}. Use: "
                f"{alternative if alternative else 'See documentation for alternatives'}"
            )

        color = "yellow" if days_left > 30 else "red"
        for line in _format_block(base_info, entity_type="command group"):
            click.secho(message=line, fg=color, bold=True, err=True)

    def decorator(grp: G) -> G:
        if not isinstance(grp, click.MultiCommand):
            raise TypeError(
                f"@deprecated_group expects click.Group/MultiCommand, "
                f"got {type(grp)!r}. "
                f"Use @deprecated_command for commands/functions."
            )

        # Store deprecation info on the group object for meta generation
        grp._deprecation_info = {
            'removal_date': removal_d.isoformat(),
            'deprecated_date': deprecated_d.isoformat() if deprecated_d else None,
            'alternative': alternative,
            'version': version,
            'reason': reason,
            'enforce_removal': enforce_removal,
        }
        # Remove None values
        grp._deprecation_info = {
            k: v for k, v in grp._deprecation_info.items() if v is not None
        }

        orig_invoke = grp.invoke

        @functools.wraps(orig_invoke)
        def wrapped_invoke(ctx: click.Context) -> Any:
            subcommand = ctx.invoked_subcommand
            has_subcommand = subcommand is not None or bool(ctx.protected_args)
            help_requested = '--help' in ctx.args or '-h' in ctx.args

            should_warn = False
            if has_subcommand and help_requested:
                should_warn = False
            elif not has_subcommand:
                should_warn = True
            elif warn_on_subcommands:
                should_warn = True

            if should_warn:
                _emit_warning()

            return orig_invoke(ctx)

        grp.invoke = wrapped_invoke

        def format_help(
                ctx: click.Context,
                formatter: click.HelpFormatter,
        ) -> None:
            grp.format_usage(ctx, formatter)

            days_left = _days_until(base_info["removal_date"])
            color = "yellow" if days_left > 30 else "red"

            formatter.write_paragraph()
            for line in _format_block(base_info, entity_type="command group"):
                styled_line = click.style(line, fg=color, bold=True)
                formatter.write(styled_line)
                formatter.write('\n')

            grp.format_help_text(ctx, formatter)
            grp.format_options(ctx, formatter)
            grp.format_epilog(ctx, formatter)

        grp.format_help = format_help
        return grp

    return decorator
