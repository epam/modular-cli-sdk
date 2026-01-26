"""
Tests for secrets manager implementations
"""

import pytest
from unittest.mock import MagicMock, patch

from modular_cli_sdk.client.ssm_client import (
    AbstractSecretsManager,
    OnPremSecretsManager,
    VaultSecretsManager,
    SSMSecretsManager,
)


class TestAbstractSecretsManager:
    """Tests for AbstractSecretsManager static methods"""

    def test_allowed_name_replaces_special_chars(self):
        """Test that special characters are replaced with dashes"""
        result = AbstractSecretsManager.allowed_name("user@domain.com")
        assert result == "user-domain.com"

    def test_allowed_name_keeps_allowed_chars(self):
        """Test that allowed characters are preserved"""
        result = AbstractSecretsManager.allowed_name("valid_name-123.test/path")
        assert result == "valid_name-123.test/path"

    def test_allowed_name_replaces_multiple_special_chars(self):
        """Test multiple special characters are all replaced"""
        result = AbstractSecretsManager.allowed_name("user!@#$%^&*()name")
        assert "!" not in result
        assert "@" not in result
        assert "#" not in result
        assert "^" not in result
        assert "&" not in result
        assert "*" not in result

    def test_url_new_env_takes_priority(self, monkeypatch):
        """Test that new env var takes priority over old"""
        monkeypatch.setenv("MODULAR_CLI_SDK_VAULT_ADDR", "http://new:8200")
        monkeypatch.setenv("MODULAR_CLI_VAULT_ADDR", "http://old:8200")

        manager = VaultSecretsManager()

        assert manager.url == "http://new:8200"

    def test_token_from_old_env_fallback(self, monkeypatch):
        """Test token from old environment variable (backward compat)"""
        monkeypatch.delenv("MODULAR_CLI_SDK_VAULT_TOKEN", raising=False)
        monkeypatch.setenv("MODULAR_CLI_VAULT_TOKEN", "old-token")

        manager = VaultSecretsManager()

        assert manager.token == "old-token"

    def test_token_new_env_takes_priority(self, monkeypatch):
        """Test that new env var takes priority over old"""
        monkeypatch.setenv("MODULAR_CLI_SDK_VAULT_TOKEN", "new-token")
        monkeypatch.setenv("MODULAR_CLI_VAULT_TOKEN", "old-token")

        manager = VaultSecretsManager()

        assert manager.token == "new-token"

    def test_init_client_with_old_env_vars(self, monkeypatch):
        """Test client initialization with old env vars (backward compat)"""
        monkeypatch.delenv("MODULAR_CLI_SDK_VAULT_ADDR", raising=False)
        monkeypatch.delenv("MODULAR_CLI_SDK_VAULT_TOKEN", raising=False)
        monkeypatch.setenv("MODULAR_CLI_VAULT_ADDR", "http://old:8200")
        monkeypatch.setenv("MODULAR_CLI_VAULT_TOKEN", "old-token")

        manager = VaultSecretsManager()

        # Should not raise - old env vars should work
        with patch('hvac.Client') as mock_hvac:
            _ = manager.client
            mock_hvac.assert_called_once_with(
                url="http://old:8200",
                token="old-token"
            )


class TestOnPremSecretsManager:
    """Tests for OnPremSecretsManager"""

    @pytest.fixture
    def manager(self, tmp_path, monkeypatch):
        """Create manager with temporary storage path"""
        monkeypatch.setattr(OnPremSecretsManager, 'path', str(tmp_path / 'ssm'))
        return OnPremSecretsManager()

    def test_put_and_get_parameter(self, manager):
        """Test storing and retrieving a parameter"""
        manager.put_parameter("test.key", {"value": "test"})

        result = manager.get_parameter("test.key")

        assert result == {"value": "test"}

    def test_get_nonexistent_parameter_returns_none(self, manager):
        """Test that getting nonexistent parameter returns None"""
        result = manager.get_parameter("nonexistent.key")

        assert result is None

    def test_delete_parameter(self, manager):
        """Test deleting a parameter"""
        manager.put_parameter("test.key", {"value": "test"})

        result = manager.delete_parameter("test.key")

        assert result is True
        assert manager.get_parameter("test.key") is None

    def test_delete_nonexistent_parameter_returns_false(self, manager):
        """Test deleting nonexistent parameter returns False"""
        result = manager.delete_parameter("nonexistent.key")

        assert result is False

    def test_put_parameter_with_string_value(self, manager):
        """Test storing string value"""
        manager.put_parameter("test.key", "simple string")

        result = manager.get_parameter("test.key")

        assert result == "simple string"

    def test_put_parameter_with_list_value(self, manager):
        """Test storing list value"""
        manager.put_parameter("test.key", ["item1", "item2", "item3"])

        result = manager.get_parameter("test.key")

        assert result == ["item1", "item2", "item3"]

    def test_put_parameter_overwrites_existing(self, manager):
        """Test that put_parameter overwrites existing value"""
        manager.put_parameter("test.key", {"old": "value"})
        manager.put_parameter("test.key", {"new": "value"})

        result = manager.get_parameter("test.key")

        assert result == {"new": "value"}


class TestVaultSecretsManager:
    """Tests for VaultSecretsManager"""

    def test_init_client_raises_when_hvac_not_installed(self, monkeypatch):
        """Test that missing hvac library raises RuntimeError"""
        monkeypatch.setenv("MODULAR_CLI_SDK_VAULT_ADDR", "http://vault:8200")
        monkeypatch.setenv("MODULAR_CLI_SDK_VAULT_TOKEN", "test-token")

        manager = VaultSecretsManager()

        # Mock the import to fail
        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == 'hvac':
                raise ImportError("No module named 'hvac'")
            return original_import(name, *args, **kwargs)

        with patch.object(builtins, '__import__', side_effect=mock_import):
            # Force re-initialization
            manager._client = None
            with pytest.raises(RuntimeError, match="Install hvac"):
                manager._init_client()

    def test_url_from_old_env_fallback(self, monkeypatch):
        """Test URL from old environment variable (backward compat)"""
        monkeypatch.delenv("MODULAR_CLI_SDK_VAULT_ADDR", raising=False)
        monkeypatch.setenv("MODULAR_CLI_VAULT_ADDR", "http://old:8200")
        manager = VaultSecretsManager()
        assert manager.url == "http://old:8200"

    def test_mount_point_from_constructor(self):
        """Test mount_point from constructor takes priority"""
        manager = VaultSecretsManager(mount_point="custom_mount")

        assert manager.mount_point == "custom_mount"

    def test_mount_point_from_env(self, monkeypatch):
        """Test mount_point from environment variable"""
        monkeypatch.setenv("MODULAR_CLI_SDK_VAULT_MOUNT_POINT", "env_mount")

        manager = VaultSecretsManager()

        assert manager.mount_point == "env_mount"

    def test_mount_point_default(self, clean_vault_env):
        """Test mount_point default value"""
        manager = VaultSecretsManager()

        assert manager.mount_point == "secret"

    def test_path_prefix_from_constructor(self):
        """Test path_prefix from constructor takes priority"""
        manager = VaultSecretsManager(path_prefix="custom/prefix")

        assert manager.path_prefix == "custom/prefix"

    def test_path_prefix_from_env(self, monkeypatch):
        """Test path_prefix from environment variable"""
        monkeypatch.setenv("MODULAR_CLI_SDK_VAULT_PATH_PREFIX", "env/prefix")

        manager = VaultSecretsManager()

        assert manager.path_prefix == "env/prefix"

    def test_path_prefix_default(self, clean_vault_env):
        """Test path_prefix default value (empty string)"""
        manager = VaultSecretsManager()

        assert manager.path_prefix == ""

    def test_build_full_path_without_prefix(self):
        """Test path building without prefix"""
        manager = VaultSecretsManager(path_prefix="")

        result = manager._build_full_path("secret.name")

        assert result == "secret.name"

    def test_build_full_path_with_prefix(self):
        """Test path building with prefix"""
        manager = VaultSecretsManager(path_prefix="modular")

        result = manager._build_full_path("secret.name")

        assert result == "modular/secret.name"

    def test_build_full_path_normalizes_slashes(self):
        """Test that path building normalizes slashes"""
        manager = VaultSecretsManager(path_prefix="/modular/")

        result = manager._build_full_path("/secret.name/")

        assert result == "modular/secret.name"

    def test_url_from_constructor(self):
        """Test URL from constructor takes priority"""
        manager = VaultSecretsManager(url="http://custom:8200")

        assert manager.url == "http://custom:8200"

    def test_url_from_new_env(self, monkeypatch):
        """Test URL from new environment variable"""
        monkeypatch.setenv("MODULAR_CLI_SDK_VAULT_ADDR", "http://new:8200")

        manager = VaultSecretsManager()

        assert manager.url == "http://new:8200"

    def test_token_from_constructor(self):
        """Test token from constructor takes priority"""
        manager = VaultSecretsManager(token="custom-token")

        assert manager.token == "custom-token"

    def test_token_from_new_env(self, monkeypatch):
        """Test token from new environment variable"""
        monkeypatch.setenv("MODULAR_CLI_SDK_VAULT_TOKEN", "new-token")

        manager = VaultSecretsManager()

        assert manager.token == "new-token"

    @pytest.fixture
    def vault_manager_with_mock(self, monkeypatch):
        """Create VaultSecretsManager with mocked hvac client"""
        monkeypatch.setenv("MODULAR_CLI_SDK_VAULT_ADDR", "http://vault:8200")
        monkeypatch.setenv("MODULAR_CLI_SDK_VAULT_TOKEN", "test-token")

        manager = VaultSecretsManager()
        mock_client = MagicMock()
        manager._client = mock_client
        return manager, mock_client

    def test_get_parameter_success(self, vault_manager_with_mock):
        """Test successful parameter retrieval from Vault"""
        manager, mock_client = vault_manager_with_mock

        mock_client.secrets.kv.v2.read_secret_version.return_value = {
            'data': {'data': {'kv': {'api_key': 'secret'}}}
        }

        result = manager.get_parameter("test.secret")

        assert result == {'api_key': 'secret'}
        mock_client.secrets.kv.v2.read_secret_version.assert_called_once()

    def test_get_parameter_not_found(self, vault_manager_with_mock):
        """Test parameter not found returns None"""
        manager, mock_client = vault_manager_with_mock

        mock_client.secrets.kv.v2.read_secret_version.side_effect = Exception(
            "Not found")

        result = manager.get_parameter("nonexistent")

        assert result is None

    def test_get_parameter_empty_response(self, vault_manager_with_mock):
        """Test empty response returns None"""
        manager, mock_client = vault_manager_with_mock

        mock_client.secrets.kv.v2.read_secret_version.return_value = {}

        result = manager.get_parameter("test.secret")

        assert result is None

    def test_put_parameter_success(self, vault_manager_with_mock):
        """Test successful parameter storage in Vault"""
        manager, mock_client = vault_manager_with_mock

        result = manager.put_parameter("test.secret", {"key": "value"})

        assert result is True
        mock_client.secrets.kv.v2.create_or_update_secret.assert_called_once()

    def test_put_parameter_failure(self, vault_manager_with_mock):
        """Test parameter storage failure"""
        manager, mock_client = vault_manager_with_mock

        mock_client.secrets.kv.v2.create_or_update_secret.side_effect = \
            Exception("Failed")

        result = manager.put_parameter("test.secret", {"key": "value"})

        assert result is False

    def test_delete_parameter_success(self, vault_manager_with_mock):
        """Test successful parameter deletion from Vault"""
        manager, mock_client = vault_manager_with_mock

        mock_client.secrets.kv.v2.delete_metadata_and_all_versions.return_value = True

        result = manager.delete_parameter("test.secret")

        assert result is True

    def test_delete_parameter_failure(self, vault_manager_with_mock):
        """Test parameter deletion failure"""
        manager, mock_client = vault_manager_with_mock

        mock_client.secrets.kv.v2.delete_metadata_and_all_versions.side_effect = Exception(
            "Failed")

        result = manager.delete_parameter("test.secret")

        assert result is False

    def test_init_client_missing_url_raises(self, clean_vault_env):
        """Test that missing Vault URL raises RuntimeError"""
        clean_vault_env.setenv("MODULAR_CLI_SDK_VAULT_TOKEN", "token")

        manager = VaultSecretsManager()

        with pytest.raises(RuntimeError, match="Vault URL not configured"):
            _ = manager.client

    def test_init_client_missing_token_raises(self, clean_vault_env):
        """Test that missing Vault token raises RuntimeError"""
        clean_vault_env.setenv("MODULAR_CLI_SDK_VAULT_ADDR", "http://vault:8200")

        manager = VaultSecretsManager()

        with pytest.raises(RuntimeError, match="Vault token not configured"):
            _ = manager.client

    def test_enable_secrets_engine_success(self, vault_manager_with_mock):
        """Test enabling secrets engine"""
        manager, mock_client = vault_manager_with_mock

        result = manager.enable_secrets_engine()

        assert result is True
        mock_client.sys.enable_secrets_engine.assert_called_once()

    def test_enable_secrets_engine_failure(self, vault_manager_with_mock):
        """Test enabling secrets engine failure"""
        manager, mock_client = vault_manager_with_mock

        mock_client.sys.enable_secrets_engine.side_effect = Exception("Failed")

        result = manager.enable_secrets_engine()

        assert result is False

    def test_enable_secrets_engine_custom_mount(self, vault_manager_with_mock):
        """Test enabling secrets engine with custom mount point"""
        manager, mock_client = vault_manager_with_mock

        manager.enable_secrets_engine(mount_point="custom")

        call_kwargs = mock_client.sys.enable_secrets_engine.call_args[1]
        assert call_kwargs['path'] == "custom"

    def test_is_secrets_engine_enabled_true(self, vault_manager_with_mock):
        """Test checking if secrets engine is enabled - True case"""
        manager, mock_client = vault_manager_with_mock

        mock_client.sys.list_mounted_secrets_engines.return_value = {
            'secret/': {},
            'other/': {}
        }

        assert manager.is_secrets_engine_enabled() is True

    def test_is_secrets_engine_enabled_false(self, vault_manager_with_mock):
        """Test checking if secrets engine is enabled - False case"""
        manager, mock_client = vault_manager_with_mock

        mock_client.sys.list_mounted_secrets_engines.return_value = {
            'other/': {}
        }

        assert manager.is_secrets_engine_enabled() is False

    def test_is_secrets_engine_enabled_custom_mount(self, vault_manager_with_mock):
        """Test checking custom mount point"""
        manager, mock_client = vault_manager_with_mock

        mock_client.sys.list_mounted_secrets_engines.return_value = {
            'secret/': {},
            'custom/': {},
        }

        assert manager.is_secrets_engine_enabled("custom") is True
        assert manager.is_secrets_engine_enabled("nonexistent") is False


class TestSSMSecretsManager:
    """Tests for SSMSecretsManager (AWS SSM)"""

    @pytest.fixture
    def mock_boto3_client(self):
        """Mock boto3 SSM client"""
        with patch('boto3.client') as mock:
            yield mock.return_value

    def test_get_parameter_returns_dict(self, mock_boto3_client):
        """Test get_parameter returns parsed JSON dict"""
        mock_boto3_client.get_parameter.return_value = {
            'Parameter': {'Value': '{"key": "value"}'}
        }

        with patch('boto3.client', return_value=mock_boto3_client):
            manager = SSMSecretsManager()
            manager.__dict__['client'] = mock_boto3_client

            result = manager.get_parameter("test.param")

            assert result == {"key": "value"}

    def test_get_parameter_returns_string_on_invalid_json(
            self,
            mock_boto3_client,
    ):
        """Test get_parameter returns raw string if JSON parsing fails"""
        mock_boto3_client.get_parameter.return_value = {
            'Parameter': {'Value': 'not-json-string'}
        }

        with patch('boto3.client', return_value=mock_boto3_client):
            manager = SSMSecretsManager()
            manager.__dict__['client'] = mock_boto3_client

            result = manager.get_parameter("test.param")

            assert result == "not-json-string"

    def test_put_parameter_serializes_dict(self, mock_boto3_client):
        """Test put_parameter serializes dict to JSON"""
        with patch('boto3.client', return_value=mock_boto3_client):
            manager = SSMSecretsManager()
            manager.__dict__['client'] = mock_boto3_client

            manager.put_parameter("test.param", {"key": "value"})

            mock_boto3_client.put_parameter.assert_called_once()
            call_args = mock_boto3_client.put_parameter.call_args
            assert '"key": "value"' in call_args[1]['Value']

    def test_put_parameter_serializes_list(self, mock_boto3_client):
        """Test put_parameter serializes list to JSON"""
        with patch('boto3.client', return_value=mock_boto3_client):
            manager = SSMSecretsManager()
            manager.__dict__['client'] = mock_boto3_client

            manager.put_parameter("test.param", ["item1", "item2"])

            call_args = mock_boto3_client.put_parameter.call_args
            assert '["item1", "item2"]' in call_args[1]['Value']

    def test_put_parameter_string_value(self, mock_boto3_client):
        """Test put_parameter handles string value directly"""
        with patch('boto3.client', return_value=mock_boto3_client):
            manager = SSMSecretsManager()
            manager.__dict__['client'] = mock_boto3_client

            manager.put_parameter("test.param", "simple string")

            call_args = mock_boto3_client.put_parameter.call_args
            assert call_args[1]['Value'] == "simple string"

    def test_get_parameter_client_error_returns_none(self, mock_boto3_client):
        """Test that ClientError returns None"""
        from botocore.exceptions import ClientError

        mock_boto3_client.get_parameter.side_effect = ClientError(
            {'Error': {'Code': 'ParameterNotFound', 'Message': 'Not found'}},
            'GetParameter'
        )

        with patch('boto3.client', return_value=mock_boto3_client):
            manager = SSMSecretsManager()
            manager.__dict__['client'] = mock_boto3_client

            result = manager.get_parameter("nonexistent")

            assert result is None

    def test_put_parameter_client_error_returns_false(self, mock_boto3_client):
        """Test that ClientError on put returns False"""
        from botocore.exceptions import ClientError

        mock_boto3_client.put_parameter.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}},
            'PutParameter'
        )

        with patch('boto3.client', return_value=mock_boto3_client):
            manager = SSMSecretsManager()
            manager.__dict__['client'] = mock_boto3_client

            result = manager.put_parameter("test", {"key": "value"})

            assert result is False

    def test_delete_parameter_success(self, mock_boto3_client):
        """Test successful parameter deletion"""
        with patch('boto3.client', return_value=mock_boto3_client):
            manager = SSMSecretsManager()
            manager.__dict__['client'] = mock_boto3_client

            result = manager.delete_parameter("test.param")

            assert result is True
            mock_boto3_client.delete_parameter \
                .assert_called_once_with(Name="test.param")

    def test_delete_parameter_client_error_returns_false(self, mock_boto3_client):
        """Test that ClientError on delete returns False"""
        from botocore.exceptions import ClientError

        mock_boto3_client.delete_parameter.side_effect = ClientError(
            {'Error': {'Code': 'ParameterNotFound', 'Message': 'Not found'}},
            'DeleteParameter'
        )

        with patch('boto3.client', return_value=mock_boto3_client):
            manager = SSMSecretsManager()
            manager.__dict__['client'] = mock_boto3_client

            result = manager.delete_parameter("nonexistent")

            assert result is False

    def test_client_initialization_with_region(self):
        """Test client initialization with specific region"""
        with patch('boto3.client') as mock_boto:
            manager = SSMSecretsManager(region="eu-west-1")
            _ = manager.client

            mock_boto.assert_called_once_with('ssm', region_name="eu-west-1")

    def test_client_initialization_without_region(self):
        """Test client initialization without region"""
        with patch('boto3.client') as mock_boto:
            manager = SSMSecretsManager()
            _ = manager.client

            mock_boto.assert_called_once_with('ssm', region_name=None)

    def test_client_raises_on_no_credentials(self):
        """Test that NoCredentialsError is properly handled"""
        from botocore.exceptions import NoCredentialsError

        with patch('boto3.client', side_effect=NoCredentialsError()):
            manager = SSMSecretsManager()

            with pytest.raises(ValueError, match="No aws credentials"):
                _ = manager.client

    def test_client_raises_on_no_region(self):
        """Test that NoRegionError is properly handled"""
        from botocore.exceptions import NoRegionError

        with patch('boto3.client', side_effect=NoRegionError()):
            manager = SSMSecretsManager()

            with pytest.raises(ValueError, match="No aws region"):
                _ = manager.client