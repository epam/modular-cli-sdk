"""
Tests for secrets manager implementations.
"""

import pytest
from unittest.mock import patch

from modular_cli_sdk.client.ssm_client import (
    OnPremSecretsManager,
    VaultSecretsManager,
    SSMSecretsManager,
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


class TestVaultSecretsManager:
    """Tests for VaultSecretsManager"""

    def test_mount_point_from_constructor(self):
        """Test mount_point from constructor takes priority"""
        manager = VaultSecretsManager(mount_point="custom_mount")

        assert manager.mount_point == "custom_mount"

    def test_mount_point_from_env(self, monkeypatch):
        """Test mount_point from environment variable"""
        monkeypatch.setenv("MODULAR_CLI_SDK_VAULT_MOUNT_POINT", "env_mount")

        manager = VaultSecretsManager()

        assert manager.mount_point == "env_mount"

    def test_path_prefix_from_constructor(self):
        """Test path_prefix from constructor takes priority"""
        manager = VaultSecretsManager(path_prefix="custom/prefix")

        assert manager.path_prefix == "custom/prefix"

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
    ) -> None:
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
