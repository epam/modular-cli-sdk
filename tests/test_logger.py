"""
Tests for logger module - SensitiveFormatter and logging configuration.
"""

import logging
import pytest

from modular_cli_sdk.commons.logger import (
    SensitiveFormatter,
    get_logger,
    LOG_FORMAT,
    _name_to_level,
)


class TestSensitiveFormatter:
    """Tests for SensitiveFormatter class"""

    @pytest.fixture
    def formatter(self):
        """Create a SensitiveFormatter instance"""
        return SensitiveFormatter(LOG_FORMAT)

    @pytest.fixture
    def logger_with_formatter(self, formatter):
        """Create a logger with SensitiveFormatter for testing"""
        logger = logging.getLogger("test_sensitive")
        logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        yield logger
        # Cleanup
        logger.handlers.clear()

    def test_formatter_masks_password(self, formatter):
        """Test that password values are masked"""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg='{"password": "secret123"}',
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        assert "secret123" not in result
        assert "****" in result

    def test_formatter_masks_api_key(self, formatter):
        """Test that api_key values are masked"""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg='{"api_key": "my-secret-key"}',
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        assert "my-secret-key" not in result
        assert "****" in result

    def test_formatter_masks_access_token(self, formatter):
        """Test that access_token values are masked"""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg='{"access_token": "bearer-token-123"}',
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        assert "bearer-token-123" not in result
        assert "****" in result

    def test_formatter_masks_refresh_token(self, formatter):
        """Test that refresh_token values are masked"""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg='{"refresh_token": "refresh-abc"}',
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        assert "refresh-abc" not in result

    def test_formatter_masks_id_token(self, formatter):
        """Test that id_token values are masked"""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg='{"id_token": "id-token-xyz"}',
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        assert "id-token-xyz" not in result

    def test_formatter_masks_authorization(self, formatter):
        """Test that authorization values are masked"""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg='{"authorization": "Bearer xyz123"}',
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        assert "Bearer xyz123" not in result

    def test_formatter_masks_secret(self, formatter):
        """Test that secret values are masked"""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg='{"secret": "top-secret"}',
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        assert "top-secret" not in result

    def test_formatter_masks_aws_secret_access_key(self, formatter):
        """Test that AWS_SECRET_ACCESS_KEY values are masked"""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg='{"AWS_SECRET_ACCESS_KEY": "aws-secret-key"}',
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        assert "aws-secret-key" not in result

    def test_formatter_masks_aws_session_token(self, formatter):
        """Test that AWS_SESSION_TOKEN values are masked"""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg='{"AWS_SESSION_TOKEN": "session-token"}',
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        assert "session-token" not in result

    def test_formatter_masks_git_access_secret(self, formatter):
        """Test that git_access_secret values are masked"""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg='{"git_access_secret": "git-secret"}',
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        assert "git-secret" not in result

    def test_formatter_masks_azure_client_id(self, formatter):
        """Test that AZURE_CLIENT_ID values are masked"""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg='{"AZURE_CLIENT_ID": "azure-id"}',
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        assert "azure-id" not in result

    def test_formatter_masks_azure_client_secret(self, formatter):
        """Test that AZURE_CLIENT_SECRET values are masked"""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg='{"AZURE_CLIENT_SECRET": "azure-secret"}',
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        assert "azure-secret" not in result

    def test_formatter_masks_google_application_credentials(self, formatter):
        """Test that GOOGLE_APPLICATION_CREDENTIALS values are masked"""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg='{"GOOGLE_APPLICATION_CREDENTIALS": "google-creds"}',
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        assert "google-creds" not in result

    def test_formatter_masks_private_key(self, formatter):
        """Test that private_key values are masked"""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg='{"private_key": "-----BEGIN PRIVATE KEY-----"}',
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        assert "-----BEGIN PRIVATE KEY-----" not in result

    def test_formatter_masks_private_key_id(self, formatter):
        """Test that private_key_id values are masked"""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg='{"private_key_id": "key-id-123"}',
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        assert "key-id-123" not in result

    def test_formatter_masks_authorization_header(self, formatter):
        """Test that Authorization (capitalized) values are masked"""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg='{"Authorization": "Bearer token"}',
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        assert "Bearer token" not in result

    def test_formatter_masks_authentication(self, formatter):
        """Test that Authentication values are masked"""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg='{"Authentication": "auth-value"}',
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        assert "auth-value" not in result

    def test_formatter_masks_api_link(self, formatter):
        """Test that api_link values are masked"""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg='{"api_link": "https://secret.api.com"}',
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        assert "https://secret.api.com" not in result

    def test_formatter_masks_sign_key(self, formatter):
        """Test that sign_key values are masked"""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg='{"sign_key": "signing-key-value"}',
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        assert "signing-key-value" not in result

    def test_formatter_preserves_non_sensitive_data(self, formatter):
        """Test that non-sensitive data is preserved"""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg='{"username": "john", "email": "john@example.com"}',
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        assert "john" in result
        assert "john@example.com" in result

    def test_formatter_handles_single_quotes(self, formatter):
        """Test that formatter handles single quotes"""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="{'password': 'secret123'}",
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        assert "secret123" not in result
        assert "****" in result

    def test_formatter_handles_spaces_after_colon(self, formatter):
        """Test that formatter handles varying spaces after colon"""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg='{"password":    "secret123"}',
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        assert "secret123" not in result

    def test_formatter_masks_multiple_sensitive_fields(self, formatter):
        """Test that multiple sensitive fields are all masked"""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg='{"password": "pass1", "api_key": "key1", "secret": "sec1"}',
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        assert "pass1" not in result
        assert "key1" not in result
        assert "sec1" not in result

    def test_formatter_regex_caching(self, formatter):
        """Test that regex patterns are cached"""
        # First call - creates regex
        regex1 = formatter.get_param_regex("password")
        # Second call - should return cached
        regex2 = formatter.get_param_regex("password")

        assert regex1 is regex2
        assert "password" in formatter._param_to_regex

    def test_secured_params_is_cached_property(self, formatter):
        """Test that secured_params is a cached property"""
        params1 = formatter.secured_params
        params2 = formatter.secured_params

        # Should be the same object (cached)
        assert params1 is params2
        assert isinstance(params1, set)

    def test_secured_params_contains_expected_values(self, formatter):
        """Test that secured_params contains all expected sensitive parameters"""
        expected = {
            'refresh_token', 'id_token', 'password', 'authorization', 'secret',
            'AWS_SECRET_ACCESS_KEY', 'AWS_SESSION_TOKEN', 'git_access_secret',
            'api_key', 'AZURE_CLIENT_ID', 'AZURE_CLIENT_SECRET',
            'GOOGLE_APPLICATION_CREDENTIALS', 'private_key', 'private_key_id',
            'Authorization', 'Authentication', 'api_link', 'access_token',
            'sign_key'
        }
        assert formatter.secured_params == expected

    def test_compile_param_regex_returns_pattern(self):
        """Test _compile_param_regex returns a compiled pattern"""
        pattern = SensitiveFormatter._compile_param_regex("test_param")

        assert hasattr(pattern, 'match')
        assert hasattr(pattern, 'sub')

    def test_formatter_with_empty_message(self, formatter):
        """Test formatter handles empty message"""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="",
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        assert result is not None


class TestGetLogger:
    """Tests for get_logger function"""

    def test_get_logger_returns_logger(self):
        """Test that get_logger returns a logger instance"""
        logger = get_logger("test_module")

        assert isinstance(logger, logging.Logger)
        assert "test_module" in logger.name

    def test_get_logger_with_custom_level(self):
        """Test get_logger with custom log level"""
        logger = get_logger("test_custom_level", level=logging.DEBUG)

        assert logger.level == logging.DEBUG

    def test_get_logger_with_none_level(self):
        """Test get_logger with None level (should not set level)"""
        logger = get_logger("test_none_level", level=None)

        # Logger should exist, level may be NOTSET or inherited
        assert isinstance(logger, logging.Logger)

    def test_get_logger_with_zero_level(self):
        """Test get_logger with level=0 (falsy but valid NOTSET)"""
        logger = get_logger("test_zero_level", level=0)

        # Level 0 is falsy, so level should not be set
        assert isinstance(logger, logging.Logger)

    def test_get_logger_creates_child_logger(self):
        """Test that get_logger creates a child of the module logger"""
        logger = get_logger("child_logger")

        # Should be a child logger
        assert logger.parent is not None

    def test_get_logger_different_names_different_loggers(self):
        """Test that different names create different loggers"""
        logger1 = get_logger("module1")
        logger2 = get_logger("module2")

        assert logger1 is not logger2
        assert logger1.name != logger2.name

    def test_get_logger_same_name_same_logger(self):
        """Test that same name returns same logger instance"""
        logger1 = get_logger("same_module")
        logger2 = get_logger("same_module")

        assert logger1 is logger2


class TestLogLevelConfiguration:
    """Tests for log level configuration from environment"""

    def test_log_level_from_env_debug(self, monkeypatch):
        """Test log_level set to DEBUG from environment"""
        monkeypatch.setenv("log_level", "DEBUG")

        # Re-import to pick up new env var
        import importlib
        from modular_cli_sdk.commons import logger as logger_module
        importlib.reload(logger_module)

        assert logger_module.log_level == logging.DEBUG

        # Cleanup - reload with original env
        monkeypatch.delenv("log_level", raising=False)
        importlib.reload(logger_module)

    def test_log_level_from_env_error(self, monkeypatch):
        """Test log_level set to ERROR from environment"""
        monkeypatch.setenv("log_level", "ERROR")

        import importlib
        from modular_cli_sdk.commons import logger as logger_module
        importlib.reload(logger_module)

        assert logger_module.log_level == logging.ERROR

        monkeypatch.delenv("log_level", raising=False)
        importlib.reload(logger_module)

    def test_log_level_from_env_warning(self, monkeypatch):
        """Test log_level set to WARNING from environment"""
        monkeypatch.setenv("log_level", "WARNING")

        import importlib
        from modular_cli_sdk.commons import logger as logger_module
        importlib.reload(logger_module)

        assert logger_module.log_level == logging.WARNING

        monkeypatch.delenv("log_level", raising=False)
        importlib.reload(logger_module)

    def test_log_level_from_env_info(self, monkeypatch):
        """Test log_level set to INFO from environment"""
        monkeypatch.setenv("log_level", "INFO")

        import importlib
        from modular_cli_sdk.commons import logger as logger_module
        importlib.reload(logger_module)

        assert logger_module.log_level == logging.INFO

        monkeypatch.delenv("log_level", raising=False)
        importlib.reload(logger_module)

    def test_log_level_from_env_critical(self, monkeypatch):
        """Test log_level set to CRITICAL from environment"""
        monkeypatch.setenv("log_level", "CRITICAL")

        import importlib
        from modular_cli_sdk.commons import logger as logger_module
        importlib.reload(logger_module)

        assert logger_module.log_level == logging.CRITICAL

        monkeypatch.delenv("log_level", raising=False)
        importlib.reload(logger_module)

    def test_log_level_from_env_fatal(self, monkeypatch):
        """Test log_level set to FATAL from environment"""
        monkeypatch.setenv("log_level", "FATAL")

        import importlib
        from modular_cli_sdk.commons import logger as logger_module
        importlib.reload(logger_module)

        assert logger_module.log_level == logging.FATAL

        monkeypatch.delenv("log_level", raising=False)
        importlib.reload(logger_module)

    def test_log_level_invalid_defaults_to_info(self, monkeypatch):
        """Test invalid log_level defaults to INFO"""
        monkeypatch.setenv("log_level", "INVALID_LEVEL")

        import importlib
        from modular_cli_sdk.commons import logger as logger_module
        importlib.reload(logger_module)

        assert logger_module.log_level == logging.INFO

        monkeypatch.delenv("log_level", raising=False)
        importlib.reload(logger_module)

    def test_log_level_not_set_defaults_to_info(self, monkeypatch):
        """Test missing log_level defaults to INFO"""
        monkeypatch.delenv("log_level", raising=False)

        import importlib
        from modular_cli_sdk.commons import logger as logger_module
        importlib.reload(logger_module)

        assert logger_module.log_level == logging.INFO


class TestNameToLevelMapping:
    """Tests for _name_to_level mapping"""

    def test_name_to_level_contains_all_levels(self):
        """Test that _name_to_level contains all expected log levels"""
        assert _name_to_level['CRITICAL'] == logging.CRITICAL
        assert _name_to_level['FATAL'] == logging.FATAL
        assert _name_to_level['ERROR'] == logging.ERROR
        assert _name_to_level['WARNING'] == logging.WARNING
        assert _name_to_level['INFO'] == logging.INFO
        assert _name_to_level['DEBUG'] == logging.DEBUG

    def test_name_to_level_length(self):
        """Test _name_to_level has expected number of entries"""
        assert len(_name_to_level) == 6


class TestLogFormatConstant:
    """Tests for LOG_FORMAT constant"""

    def test_log_format_contains_required_fields(self):
        """Test LOG_FORMAT contains all required format fields"""
        assert "%(asctime)s" in LOG_FORMAT
        assert "%(levelname)s" in LOG_FORMAT
        assert "%(name)s" in LOG_FORMAT
        assert "%(message)s" in LOG_FORMAT
