import logging
import pytest
from unittest.mock import MagicMock, patch

from modular_cli_sdk.client.ssm_client import (
    OnPremSecretsManager,
    VaultSecretsManager,
    SSMSecretsManager,
)
from modular_cli_sdk.commons.logger import SensitiveFormatter, LOG_FORMAT


class TestOnPremSecretsManagerExtra:

    @pytest.fixture
    def manager(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            OnPremSecretsManager, 'path', str(tmp_path / 'ssm')
        )
        return OnPremSecretsManager()

    def test_persistence_across_instances(self, tmp_path, monkeypatch):
        """Values stored should be readable by a new manager instance."""
        monkeypatch.setattr(
            OnPremSecretsManager, 'path', str(tmp_path / 'ssm')
        )
        m1 = OnPremSecretsManager()
        m1.put_parameter("k", {"a": 1})

        m2 = OnPremSecretsManager()
        assert m2.get_parameter("k") == {"a": 1}

    def test_put_returns_true(self, manager):
        assert manager.put_parameter("k", "v") is True

    def test_empty_string_value(self, manager):
        manager.put_parameter("k", "")
        assert manager.get_parameter("k") == ""

    def test_nested_structure(self, manager):
        value = {"a": {"b": [1, 2, {"c": "d"}]}}
        manager.put_parameter("k", value)
        assert manager.get_parameter("k") == value


class TestVaultSecretsManagerExtra:

    @pytest.fixture
    def vault_manager_with_mock(self, monkeypatch):
        monkeypatch.setenv("MODULAR_CLI_SDK_VAULT_ADDR", "http://vault:8200")
        monkeypatch.setenv("MODULAR_CLI_SDK_VAULT_TOKEN", "test-token")
        manager = VaultSecretsManager()
        mock_client = MagicMock()
        manager._client = mock_client
        return manager, mock_client

    def test_secret_key_from_constructor(self):
        manager = VaultSecretsManager(secret_key="mykey")
        assert manager.secret_key == "mykey"

    def test_secret_key_from_env(self, monkeypatch):
        monkeypatch.setenv("MODULAR_CLI_SDK_VAULT_SECRET_KEY", "envkey")
        manager = VaultSecretsManager()
        assert manager.secret_key == "envkey"

    def test_secret_key_default(self, clean_vault_env):
        monkeypatch = clean_vault_env
        monkeypatch.delenv("MODULAR_CLI_SDK_VAULT_SECRET_KEY", raising=False)
        manager = VaultSecretsManager()
        assert manager.secret_key == "data"

    def test_get_parameter_uses_custom_secret_key(
            self, vault_manager_with_mock, monkeypatch,
    ):
        manager, mock_client = vault_manager_with_mock
        monkeypatch.setenv("MODULAR_CLI_SDK_VAULT_SECRET_KEY", "custom")
        mock_client.secrets.kv.v2.read_secret_version.return_value = {
            'data': {'data': {'custom': 'the-value'}}
        }
        assert manager.get_parameter("x") == "the-value"

    def test_put_parameter_uses_secret_key_in_payload(
            self, vault_manager_with_mock,
    ):
        manager, mock_client = vault_manager_with_mock
        manager.put_parameter("name", {"a": 1})
        call_kwargs = mock_client.secrets.kv.v2 \
            .create_or_update_secret.call_args.kwargs
        assert call_kwargs['secret'] == {"data": {"a": 1}}

    def test_get_parameter_missing_secret_key_returns_none(
            self, vault_manager_with_mock,
    ):
        manager, mock_client = vault_manager_with_mock
        mock_client.secrets.kv.v2.read_secret_version.return_value = {
            'data': {'data': {'other_key': 'value'}}
        }
        assert manager.get_parameter("x") is None

    def test_client_property_lazy_init(self, vault_manager_with_mock):
        manager, mock_client = vault_manager_with_mock
        assert manager.client is mock_client

    def test_normalize_path_empty(self):
        manager = VaultSecretsManager()
        assert manager._normalize_path("") == ""
        assert manager._normalize_path(None) == ""

    def test_build_full_path_with_only_prefix_slashes(self):
        manager = VaultSecretsManager(path_prefix="///")
        assert manager._build_full_path("name") == "name"

    def test_delete_parameter_falsy_result_returns_false(
            self, vault_manager_with_mock,
    ):
        manager, mock_client = vault_manager_with_mock
        mock_client.secrets.kv.v2 \
            .delete_metadata_and_all_versions.return_value = None
        assert manager.delete_parameter("x") is False


class TestSSMSecretsManagerExtra:

    @pytest.fixture
    def mock_boto3_client(self):
        with patch('boto3.client') as mock:
            yield mock.return_value

    def test_get_parameter_passes_with_decryption(self, mock_boto3_client):
        mock_boto3_client.get_parameter.return_value = {
            'Parameter': {'Value': '{"k": "v"}'}
        }
        manager = SSMSecretsManager()
        manager.__dict__['client'] = mock_boto3_client
        manager.get_parameter("p")
        call_kwargs = mock_boto3_client.get_parameter.call_args.kwargs
        assert call_kwargs['WithDecryption'] is True

    def test_put_parameter_custom_type(self, mock_boto3_client):
        manager = SSMSecretsManager()
        manager.__dict__['client'] = mock_boto3_client
        manager.put_parameter("p", "v", _type="String")
        call_kwargs = mock_boto3_client.put_parameter.call_args.kwargs
        assert call_kwargs['Type'] == "String"

    def test_put_parameter_overwrite_true(self, mock_boto3_client):
        manager = SSMSecretsManager()
        manager.__dict__['client'] = mock_boto3_client
        manager.put_parameter("p", "v")
        call_kwargs = mock_boto3_client.put_parameter.call_args.kwargs
        assert call_kwargs['Overwrite'] is True

    def test_get_parameter_returns_list_when_json_array(
            self, mock_boto3_client,
    ):
        mock_boto3_client.get_parameter.return_value = {
            'Parameter': {'Value': '[1, 2, 3]'}
        }
        manager = SSMSecretsManager()
        manager.__dict__['client'] = mock_boto3_client
        assert manager.get_parameter("p") == [1, 2, 3]


class TestSensitiveFormatterExtra:

    @pytest.fixture
    def formatter(self):
        return SensitiveFormatter(LOG_FORMAT)

    def test_no_sensitive_data_unchanged(self, formatter):
        record = logging.LogRecord(
            name="t", level=logging.INFO, pathname="", lineno=0,
            msg="just a normal log message with no secrets",
            args=(), exc_info=None,
        )
        result = formatter.format(record)
        assert "just a normal log message with no secrets" in result

    def test_format_with_args(self, formatter):
        """LogRecord with args should be merged before filtering."""
        record = logging.LogRecord(
            name="t", level=logging.INFO, pathname="", lineno=0,
            msg='{"password": "%s"}', args=("secret_val",), exc_info=None,
        )
        result = formatter.format(record)
        assert "secret_val" not in result

    def test_nested_json_masking(self, formatter):
        record = logging.LogRecord(
            name="t", level=logging.INFO, pathname="", lineno=0,
            msg='{"outer": {"password": "deep_secret"}}',
            args=(), exc_info=None,
        )
        result = formatter.format(record)
        assert "deep_secret" not in result

    def test_multiple_same_key_all_masked(self, formatter):
        record = logging.LogRecord(
            name="t", level=logging.INFO, pathname="", lineno=0,
            msg='{"secret": "one"} and {"secret": "two"}',
            args=(), exc_info=None,
        )
        result = formatter.format(record)
        assert "one" not in result
        assert "two" not in result
