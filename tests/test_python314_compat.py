import datetime
import sys
import threading
import pytest
from functools import cached_property
from unittest.mock import patch, MagicMock

from modular_cli_sdk.client.ssm_client import (
    SSMSecretsManager,
)
from modular_cli_sdk.commons.logger import SensitiveFormatter, LOG_FORMAT


class TestPythonVersion:
    """Sanity checks that we're actually testing the target version."""

    def test_running_on_python_3_14_or_higher(self):
        assert sys.version_info >= (3, 14)

    def test_no_removed_stdlib_imports(self):
        """
        Ensure we don't rely on modules removed in 3.12/3.13/3.14
        (e.g. distutils removed in 3.12, several deprecated aliases).
        """
        # If any of our modules imported a removed module, importing
        # them would already fail. This just re-imports to be explicit.
        import modular_cli_sdk.client.ssm_client  # noqa
        import modular_cli_sdk.services.credentials_manager  # noqa
        import modular_cli_sdk.commons.logger  # noqa
        import modular_cli_sdk.utils.view_utils  # noqa
        import modular_cli_sdk.commons.constants  # noqa


class TestCachedPropertyBehavior:
    """
    cached_property changed in 3.12 (the per-instance lock was removed).
    Verify our usages still cache correctly and are thread-safe enough
    for our use-cases.
    """

    def test_ssm_client_is_cached(self):
        with patch('boto3.client') as mock_boto:
            mock_boto.return_value = MagicMock()
            manager = SSMSecretsManager()

            client1 = manager.client
            client2 = manager.client

            assert client1 is client2
            # boto3.client should be called only once thanks to caching
            mock_boto.assert_called_once()

    def test_cached_property_concurrent_access(self):
        """
        After 3.12 cached_property no longer locks. boto3.client could
        in theory be called more than once under concurrency. We ensure
        the final cached value is consistent.
        """
        with patch('boto3.client') as mock_boto:
            mock_boto.return_value = MagicMock()
            manager = SSMSecretsManager()

            results = []

            def access():
                results.append(manager.client)

            threads = [threading.Thread(target=access) for _ in range(10)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            # All threads must observe the same final cached object
            assert all(r is manager.client for r in results)

    def test_secured_params_cached_property_thread_safe(self):
        """SensitiveFormatter.secured_params must be stable across threads."""
        formatter = SensitiveFormatter(LOG_FORMAT)
        results = []

        def access():
            results.append(formatter.secured_params)

        threads = [threading.Thread(target=access) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        first = formatter.secured_params
        assert all(r is first for r in results)

    def test_ssm_client_uses_cached_property_descriptor(self):
        """Ensure 'client' is actually a cached_property descriptor."""
        descriptor = type(SSMSecretsManager).__dict__.get('client') \
            or SSMSecretsManager.__dict__.get('client')
        assert isinstance(descriptor, cached_property)


class TestDatetimeBehavior:
    """
    Python 3.12+ deprecated some datetime behaviors. We only use
    date.today() and date.fromisoformat(), both stable - verify them.
    """

    def test_date_fromisoformat_basic(self):
        from modular_cli_sdk.utils.view_utils import _parse_date
        assert _parse_date("2027-01-01") == datetime.date(2027, 1, 1)

    def test_date_fromisoformat_extended_3_11_plus(self):
        """
        3.11+ fromisoformat accepts more formats. Our code only feeds
        YYYY-MM-DD, but verify it still rejects garbage consistently.
        """
        from modular_cli_sdk.utils.view_utils import _parse_date
        with pytest.raises(ValueError):
            _parse_date("2027-13-99")

    def test_days_until_uses_date_today(self):
        from modular_cli_sdk.utils.view_utils import _days_until
        result = _days_until(datetime.date.today() + datetime.timedelta(days=1))
        assert result == 1


class TestRegexBehavior:
    """
    The 're' module and pattern compilation are stable, but verify the
    SSM_NOT_AVAILABLE pattern and SensitiveFormatter regexes behave
    identically on the new interpreter.
    """

    def test_ssm_not_available_pattern(self):
        from modular_cli_sdk.client.ssm_client import (
            AbstractSecretsManager,
        )
        # unicode chars must be replaced too
        result = AbstractSecretsManager.allowed_name("üser@nâme")
        assert "@" not in result
        # only allowed chars remain
        import re
        assert re.fullmatch(r'[a-zA-Z0-9\/_.\-]+', result)

    def test_sensitive_formatter_regex_unicode(self):
        formatter = SensitiveFormatter(LOG_FORMAT)
        import logging
        record = logging.LogRecord(
            name="t", level=logging.INFO, pathname="", lineno=0,
            msg='{"password": "пароль123"}', args=(), exc_info=None,
        )
        result = formatter.format(record)
        assert "пароль123" not in result
        assert "****" in result


class TestImportlibReloadStability:
    """
    test_logger.py reloads the logger module a lot. On 3.14 reload
    semantics are the same, but repeated reload can duplicate handlers.
    Verify reload does not break logging or accumulate handlers.
    """

    def test_reload_does_not_duplicate_handlers(self, monkeypatch):
        """
        logging.getLogger returns a cached singleton, so re-running the module
        body on reload must NOT keep appending handlers. With the `if not
        logger.handlers` guard, handler count stays constant across reloads.
        """
        import importlib
        from modular_cli_sdk.commons import logger as logger_module

        monkeypatch.delenv("log_level", raising=False)
        importlib.reload(logger_module)
        handlers_after_first = len(logger_module.logger.handlers)

        importlib.reload(logger_module)
        handlers_after_second = len(logger_module.logger.handlers)

        # Must be stable (no leak) AND the handler must still exist (not zero).
        assert handlers_after_second == handlers_after_first
        assert handlers_after_first >= 1


class TestTypeAnnotationEvaluation:
    """
    view_utils uses `from __future__ import annotations`.
    Verify annotations are still resolvable on 3.14.
    """

    def test_view_utils_annotations_are_strings(self):
        import modular_cli_sdk.utils.view_utils as vu
        # With future annotations, __annotations__ values are strings
        ann = vu._parse_date.__annotations__
        assert ann  # has annotations
        # They should be strings (lazy) under future annotations
        assert all(isinstance(v, str) for v in ann.values())

    def test_get_type_hints_resolves(self):
        import typing
        import modular_cli_sdk.utils.view_utils as vu
        # get_type_hints must resolve forward refs without error
        hints = typing.get_type_hints(vu._parse_date)
        assert "value" in hints
