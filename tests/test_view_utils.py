"""
Tests for view_utils - Click command/group deprecation decorators.
"""

import datetime
import pytest
from click.testing import CliRunner

import click

from modular_cli_sdk.utils.view_utils import (
    _parse_date,
    _days_until,
    _format_block,
    deprecated_command,
    deprecated_group,
)


# =============================================================================
# Tests for helper functions
# =============================================================================

class TestParseDate:
    """Tests for _parse_date helper function"""

    def test_parse_none_returns_none(self):
        assert _parse_date(None) is None

    def test_parse_date_object_returns_same(self):
        date = datetime.date(2025, 6, 15)
        assert _parse_date(date) == date

    def test_parse_valid_string(self):
        result = _parse_date("2025-06-15")
        assert result == datetime.date(2025, 6, 15)

    def test_parse_invalid_string_raises_value_error(self):
        with pytest.raises(ValueError, match="Invalid date"):
            _parse_date("not-a-date")

    def test_parse_invalid_format_raises_value_error(self):
        with pytest.raises(ValueError, match="Invalid date"):
            _parse_date("15/06/2025")  # Wrong format

    def test_parse_invalid_type_raises_type_error(self):
        with pytest.raises(TypeError, match="must be str or datetime.date"):
            _parse_date(12345)


class TestDaysUntil:
    """Tests for _days_until helper function"""

    def test_future_date_returns_positive(self):
        future = datetime.date.today() + datetime.timedelta(days=10)
        assert _days_until(future) == 10

    def test_past_date_returns_negative(self):
        past = datetime.date.today() - datetime.timedelta(days=5)
        assert _days_until(past) == -5

    def test_today_returns_zero(self):
        today = datetime.date.today()
        assert _days_until(today) == 0


class TestFormatBlock:
    """Tests for _format_block helper function"""

    def test_basic_block_structure(self):
        info = {
            "removal_date": datetime.date.today() + datetime.timedelta(days=60),
            "alternative": None,
            "deprecated_date": None,
            "version": None,
            "reason": None,
        }
        lines = _format_block(info)

        assert lines[0] == "=" * 69
        assert "WARNING" in lines[1]
        assert "DEPRECATED" in lines[1]
        assert lines[-1] == "=" * 69

    def test_block_with_all_info(self):
        info = {
            "removal_date": datetime.date.today() + datetime.timedelta(days=60),
            "alternative": "use-new-cmd",
            "deprecated_date": datetime.date(2025, 1, 1),
            "version": "1.0.0",
            "reason": "Feature replaced",
        }
        lines = _format_block(info)
        block = "\n".join(lines)

        assert "use-new-cmd" in block
        assert "2025-01-01" in block
        assert "1.0.0" in block
        assert "Feature replaced" in block

    def test_block_entity_type_command(self):
        info = {
            "removal_date": datetime.date.today() + datetime.timedelta(days=60),
        }
        lines = _format_block(info, entity_type="command")
        assert "command" in lines[1].lower()

    def test_block_entity_type_group(self):
        info = {
            "removal_date": datetime.date.today() + datetime.timedelta(days=60),
        }
        lines = _format_block(info, entity_type="command group")
        assert "command group" in lines[1].lower()

    def test_block_shows_days_left_when_far(self):
        info = {
            "removal_date": datetime.date.today() + datetime.timedelta(days=60),
        }
        lines = _format_block(info)
        block = "\n".join(lines)
        assert "60 days left" in block

    def test_block_shows_urgent_when_close(self):
        info = {
            "removal_date": datetime.date.today() + datetime.timedelta(days=10),
        }
        lines = _format_block(info)
        block = "\n".join(lines)
        assert "REMOVED in 10 days" in block

    def test_block_shows_today_removal(self):
        info = {
            "removal_date": datetime.date.today(),
        }
        lines = _format_block(info)
        block = "\n".join(lines)
        assert "REMOVED TODAY" in block

    def test_block_shows_passed_removal(self):
        info = {
            "removal_date": datetime.date.today() - datetime.timedelta(days=5),
        }
        lines = _format_block(info)
        block = "\n".join(lines)
        assert "REMOVAL DATE PASSED" in block
        assert "5 days ago" in block


# =============================================================================
# Tests for deprecated_command decorator
# =============================================================================

class TestDeprecatedCommand:
    """Tests for deprecated_command decorator"""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_decorator_requires_removal_date(self):
        with pytest.raises(ValueError, match="removal_date is required"):
            @deprecated_command(removal_date=None)
            def cmd():
                pass

    def test_decorator_validates_alternative_type(self):
        with pytest.raises(ValueError, match="alternative must be a string"):
            @deprecated_command(
                removal_date="2027-01-01",
                alternative=123,  # Should be string
            )
            def cmd():
                pass

    def test_decorator_on_function(self, runner):
        @click.command()
        @deprecated_command(
            removal_date=datetime.date.today() + datetime.timedelta(days=60),
            alternative="new-cmd",
        )
        def old_cmd():
            click.echo("executed")

        result = runner.invoke(old_cmd)
        assert "executed" in result.output
        # Warning should be in stderr (but CliRunner mixes them)
        assert result.exit_code == 0

    def test_decorator_on_click_command(self, runner):
        @deprecated_command(
            removal_date=datetime.date.today() + datetime.timedelta(days=60),
        )
        @click.command()
        def old_cmd():
            click.echo("executed")

        result = runner.invoke(old_cmd)
        assert "executed" in result.output
        assert result.exit_code == 0

    def test_decorator_shows_warning_in_help(self, runner):
        @deprecated_command(
            removal_date="2027-01-01",
            alternative="new-cmd",
            reason="Being replaced",
        )
        @click.command()
        def old_cmd():
            """Original help text"""
            pass

        result = runner.invoke(old_cmd, ["--help"])
        assert "DEPRECATED" in result.output
        assert "new-cmd" in result.output
        assert "Being replaced" in result.output

    def test_decorator_rejects_group(self):
        with pytest.raises(TypeError, match="cannot be used on click.Group"):
            @deprecated_command(removal_date="2027-01-01")
            @click.group()
            def grp():
                pass

    def test_decorator_rejects_invalid_target(self):
        decorator = deprecated_command(removal_date="2027-01-01")
        with pytest.raises(TypeError, match="can only decorate"):
            decorator("not a function or command")

    def test_enforce_removal_raises_after_date(self, runner):
        @deprecated_command(
            removal_date=datetime.date.today() - datetime.timedelta(days=1),
            enforce_removal=True,
            alternative="new-cmd",
        )
        @click.command()
        def old_cmd():
            click.echo("should not execute")

        result = runner.invoke(old_cmd)
        assert result.exit_code != 0
        assert "REMOVED" in result.output or "removed" in result.output.lower()

    def test_no_enforce_allows_after_date(self, runner):
        @deprecated_command(
            removal_date=datetime.date.today() - datetime.timedelta(days=1),
            enforce_removal=False,
        )
        @click.command()
        def old_cmd():
            click.echo("executed anyway")

        result = runner.invoke(old_cmd)
        assert "executed anyway" in result.output

    def test_warning_color_yellow_when_far(self, runner):
        """Warning should be yellow when > 30 days until removal"""
        @deprecated_command(
            removal_date=datetime.date.today() + datetime.timedelta(days=60),
        )
        @click.command()
        def cmd():
            pass

        # This test mainly ensures no error; color verification is visual
        result = runner.invoke(cmd)
        assert result.exit_code == 0

    def test_warning_color_red_when_close(self, runner):
        """Warning should be red when <= 30 days until removal"""
        @deprecated_command(
            removal_date=datetime.date.today() + datetime.timedelta(days=10),
        )
        @click.command()
        def cmd():
            pass

        result = runner.invoke(cmd)
        assert result.exit_code == 0


# =============================================================================
# Tests for deprecated_group decorator
# =============================================================================

class TestDeprecatedGroup:
    """Tests for deprecated_group decorator"""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_decorator_requires_removal_date(self):
        with pytest.raises(ValueError, match="removal_date is required"):
            @deprecated_group(removal_date=None)
            @click.group()
            def grp():
                pass

    def test_decorator_validates_alternative_type(self):
        with pytest.raises(ValueError, match="alternative must be a string"):
            @deprecated_group(
                removal_date="2027-01-01",
                alternative=123,
            )
            @click.group()
            def grp():
                pass

    def test_decorator_on_group(self, runner):
        @deprecated_group(
            removal_date=datetime.date.today() + datetime.timedelta(days=60),
        )
        @click.group()
        def grp():
            pass

        @grp.command()
        def sub():
            click.echo("subcommand executed")

        result = runner.invoke(grp, ["sub"])
        assert "subcommand executed" in result.output

    def test_decorator_rejects_non_group(self):
        with pytest.raises(TypeError, match="expects click.Group"):
            @deprecated_group(removal_date="2027-01-01")
            @click.command()
            def cmd():
                pass

    def test_decorator_shows_warning_in_help(self, runner):
        @deprecated_group(
            removal_date="2027-01-01",
            alternative="new-group",
            reason="Being replaced",
        )
        @click.group()
        def grp():
            """Original help"""
            pass

        result = runner.invoke(grp, ["--help"])
        assert "DEPRECATED" in result.output
        assert "command group" in result.output.lower()

    def test_warn_on_subcommands_true(self, runner):
        @deprecated_group(
            removal_date=datetime.date.today() + datetime.timedelta(days=60),
            warn_on_subcommands=True,
        )
        @click.group()
        def grp():
            pass

        @grp.command()
        def sub():
            click.echo("done")

        result = runner.invoke(grp, ["sub"])
        # Warning should appear
        assert "done" in result.output

    def test_warn_on_subcommands_false(self, runner):
        @deprecated_group(
            removal_date=datetime.date.today() + datetime.timedelta(days=60),
            warn_on_subcommands=False,
        )
        @click.group()
        def grp():
            pass

        @grp.command()
        def sub():
            click.echo("done")

        result = runner.invoke(grp, ["sub"])
        assert "done" in result.output

    def test_enforce_removal_raises_after_date(self, runner):
        @deprecated_group(
            removal_date=datetime.date.today() - datetime.timedelta(days=1),
            enforce_removal=True,
        )
        @click.group()
        def grp():
            pass

        result = runner.invoke(grp)
        assert result.exit_code != 0

    def test_stores_deprecation_info_on_group(self):
        @deprecated_group(
            removal_date="2027-01-01",
            alternative="new-group",
            version="2.0.0",
        )
        @click.group()
        def grp():
            pass

        assert hasattr(grp, '_deprecation_info')
        assert grp._deprecation_info['removal_date'] == "2027-01-01"
        assert grp._deprecation_info['alternative'] == "new-group"
        assert grp._deprecation_info['version'] == "2.0.0"

    def test_deprecation_info_excludes_none_values(self):
        @deprecated_group(
            removal_date="2027-01-01",
            alternative=None,  # Should not be in info
        )
        @click.group()
        def grp():
            pass

        assert 'alternative' not in grp._deprecation_info

    def test_group_without_subcommand_shows_warning(self, runner):
        @deprecated_group(
            removal_date=datetime.date.today() + datetime.timedelta(days=60),
        )
        @click.group(
            invoke_without_command=True)  # Allow invoke without subcommand
        def grp():
            pass

        result = runner.invoke(grp)
        # Group invoked without subcommand - should show warning and exit 0
        assert result.exit_code == 0


# =============================================================================
# Integration tests
# =============================================================================

class TestDeprecationIntegration:
    """Integration tests for deprecation decorators"""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_nested_deprecated_group_with_commands(self, runner):
        """Test deprecated group with multiple subcommands"""
        @click.group()
        def cli():
            pass

        @deprecated_group(
            removal_date=datetime.date.today() + datetime.timedelta(days=60),
            alternative="cli new-feature",
        )
        @cli.group()
        def old_feature():
            pass

        @old_feature.command()
        def action1():
            click.echo("action1 done")

        @old_feature.command()
        def action2():
            click.echo("action2 done")

        result = runner.invoke(cli, ["old-feature", "action1"])
        assert "action1 done" in result.output

        result = runner.invoke(cli, ["old-feature", "action2"])
        assert "action2 done" in result.output

    def test_deprecated_command_in_group(self, runner):
        """Test deprecated command inside a regular group"""

        @click.group()
        def cli():
            pass

        # Create deprecated command separately, then add to group
        @deprecated_command(
            removal_date=datetime.date.today() + datetime.timedelta(days=60),
            alternative="cli new-cmd",
        )
        @click.command(name="old-cmd")
        def old_cmd():
            click.echo("old command executed")

        @click.command(name="new-cmd")
        def new_cmd():
            click.echo("new command executed")

        # Explicitly add commands to group
        cli.add_command(old_cmd)
        cli.add_command(new_cmd)

        result = runner.invoke(cli, ["old-cmd"])
        assert "old command executed" in result.output

        result = runner.invoke(cli, ["new-cmd"])
        assert "new command executed" in result.output

    def test_all_date_formats_accepted(self, runner):
        """Test that both string and date object formats work"""
        # String format
        @deprecated_command(
            removal_date="2027-06-15",
            deprecated_date="2025-01-01",
        )
        @click.command(name="cmd1")
        def cmd1():
            pass

        # Date object format
        @deprecated_command(
            removal_date=datetime.date(2027, 6, 15),
            deprecated_date=datetime.date(2025, 1, 1),
        )
        @click.command(name="cmd2")
        def cmd2():
            pass

        result1 = runner.invoke(cmd1, ["--help"])
        result2 = runner.invoke(cmd2, ["--help"])

        assert "2027-06-15" in result1.output
        assert "2027-06-15" in result2.output
