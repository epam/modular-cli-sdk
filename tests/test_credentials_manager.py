"""
Functional tests for CredentialsManager implementations.
"""

import json
import os
import pytest
import tempfile
import shutil
from unittest.mock import MagicMock, patch, PropertyMock

from modular_cli_sdk.services.credentials_manager import (
    CredentialsProvider,
    FileSystemCredentialsManager,
    SSMCredentialsManager,
)
from modular_cli_sdk.commons.exception import ModularCliSdkConfigurationException


class TestFileSystemCredentialsManager:
    """Tests for FileSystemCredentialsManager"""

    @pytest.fixture
    def temp_home(self, tmp_path, monkeypatch):
        """Create a temporary home directory for testing"""
        # Patch Path.home() to return our temp directory
        monkeypatch.setattr('pathlib.Path.home', lambda: tmp_path)
        yield tmp_path

    @pytest.fixture
    def fs_manager(self, temp_home):
        """Create FileSystemCredentialsManager with temp directory"""
        return FileSystemCredentialsManager(module_name="test_module")

    def test_store_creates_config_file(self, fs_manager):
        """Test that store() creates the configuration file"""
        config = {"api_key": "test_key", "endpoint": "https://example.com"}

        result = fs_manager.store(config)

        assert os.path.exists(fs_manager.config_file_path)
        assert "successfully" in result.lower()

        with open(fs_manager.config_file_path, 'r') as f:
            saved_config = json.load(f)
        assert saved_config == config

    def test_extract_returns_stored_config(self, fs_manager):
        """Test that extract() returns the stored configuration"""
        config = {"api_key": "test_key", "endpoint": "https://example.com"}
        fs_manager.store(config)

        result = fs_manager.extract()

        assert result == config

    def test_extract_raises_when_no_config(self, fs_manager):
        """Test that extract() raises exception when no config exists"""
        with pytest.raises(ModularCliSdkConfigurationException):
            fs_manager.extract()

    def test_clean_up_removes_config(self, fs_manager):
        """Test that clean_up() removes the configuration"""
        config = {"api_key": "test_key"}
        fs_manager.store(config)

        assert os.path.exists(fs_manager.creds_folder_path)

        result = fs_manager.clean_up()

        assert not os.path.exists(fs_manager.creds_folder_path)
        assert "deleted" in result.lower()

    def test_clean_up_handles_missing_config(self, fs_manager):
        """Test that clean_up() handles missing configuration gracefully"""
        result = fs_manager.clean_up()

        assert "not found" in result.lower()

    def test_exists_returns_true_when_config_exists(self, fs_manager):
        """Test exists() returns True when configuration exists"""
        config = {"api_key": "test_key"}
        fs_manager.store(config)

        assert fs_manager.exists() is True

    def test_exists_returns_false_when_no_config(self, fs_manager):
        """Test exists() returns False when no configuration exists"""
        assert fs_manager.exists() is False

    def test_store_raises_on_permission_error(self, fs_manager, monkeypatch):
        """Test that store raises exception on permission error"""
        from pathlib import Path

        def mock_mkdir(self, *args, **kwargs):
            raise OSError("Permission denied")

        monkeypatch.setattr(Path, 'mkdir', mock_mkdir)

        with pytest.raises(
                ModularCliSdkConfigurationException,
                match="Unable to create",
        ):
            fs_manager.store({"key": "value"})

    def test_store_overwrites_existing_config(self, fs_manager):
        """Test that store() overwrites existing configuration"""
        old_config = {"api_key": "old_key"}
        new_config = {"api_key": "new_key", "extra": "value"}

        fs_manager.store(old_config)
        fs_manager.store(new_config)

        result = fs_manager.extract()
        assert result == new_config

    def test_clean_up_handles_os_error(self, fs_manager, monkeypatch):
        """Test clean_up handles OSError gracefully"""
        config = {"api_key": "test_key"}
        fs_manager.store(config)

        # Only mock rmtree for this specific test, save original
        original_rmtree = shutil.rmtree
        call_count = [0]

        def mock_rmtree(path, *args, **kwargs):
            call_count[0] += 1
            # Only raise on first call (the actual test), not on fixture cleanup
            if call_count[0] == 1:
                raise OSError("Cannot remove")
            return original_rmtree(path, *args, **kwargs)

        monkeypatch.setattr(shutil, 'rmtree', mock_rmtree)

        # Should not raise, just return message
        result = fs_manager.clean_up()
        assert isinstance(result, str)


class TestSSMCredentialsManager:
    """Tests for SSMCredentialsManager"""

    @pytest.fixture
    def mock_context(self):
        """Create mock Click context"""
        ctx = MagicMock()
        ctx.obj = {"modular_admin_username": "test_user"}
        return ctx

    @pytest.fixture
    def ssm_manager(self, mock_context):
        """Create SSMCredentialsManager with mocked SSM client"""
        with patch.object(SSMCredentialsManager, 'ssm_client',
                          new_callable=PropertyMock) as mock_client:
            manager = SSMCredentialsManager(
                module_name="test_module",
                context=mock_context,
            )
            manager._mock_ssm_client = mock_client
            yield manager

    def test_builds_correct_ssm_secret_name(self, mock_context):
        """Test that SSM secret name is built correctly"""
        manager = SSMCredentialsManager(
            module_name="test_module",
            context=mock_context,
        )

        assert "modular-api.test_module.test_user.configuration" == manager.ssm_secret_name

    def test_store_calls_ssm_put_parameter(self, ssm_manager):
        """Test that store() calls SSM put_parameter"""
        mock_ssm = MagicMock()
        mock_ssm.put_parameter.return_value = True

        with patch.object(
                SSMCredentialsManager, 'ssm_client',
                new_callable=PropertyMock,
                return_value=mock_ssm
        ):
            ssm_manager_new = SSMCredentialsManager(
                module_name="test_module",
                context=ssm_manager.context,
            )
            # Directly set the ssm_client
            type(ssm_manager_new).ssm_client = \
                PropertyMock(return_value=mock_ssm)

            config = {"api_key": "test_key"}
            result = ssm_manager_new.store(config)

            mock_ssm.put_parameter.assert_called_once()
            assert "successfully" in result.lower()

    def test_extract_returns_config_from_ssm(self, mock_context):
        """Test that extract() returns configuration from SSM"""
        config = {"api_key": "test_key"}
        mock_ssm = MagicMock()
        mock_ssm.get_parameter.return_value = config

        with patch.object(
                SSMCredentialsManager, 'ssm_client',
                new_callable=PropertyMock,
                return_value=mock_ssm
        ):
            manager = SSMCredentialsManager(
                module_name="test_module",
                context=mock_context,
            )
            # Force the cached property
            manager.__dict__['ssm_client'] = mock_ssm

            result = manager.extract()

            assert result == config

    def test_exists_returns_true_when_parameter_exists(self, mock_context):
        """Test exists() returns True when SSM parameter exists"""
        mock_ssm = MagicMock()
        mock_ssm.get_parameter.return_value = {"api_key": "test"}

        manager = SSMCredentialsManager(
            module_name="test_module",
            context=mock_context,
        )
        manager.__dict__['ssm_client'] = mock_ssm

        assert manager.exists() is True

    def test_exists_returns_false_when_parameter_missing(self, mock_context):
        """Test exists() returns False when SSM parameter doesn't exist"""
        mock_ssm = MagicMock()
        mock_ssm.get_parameter.return_value = None

        manager = SSMCredentialsManager(
            module_name="test_module",
            context=mock_context,
        )
        manager.__dict__['ssm_client'] = mock_ssm

        assert manager.exists() is False

    def test_store_raises_on_failure(self, mock_context):
        """Test store raises exception when SSM put fails"""
        mock_ssm = MagicMock()
        mock_ssm.put_parameter.return_value = False

        manager = SSMCredentialsManager(
            module_name="test_module",
            context=mock_context,
        )
        manager.__dict__['ssm_client'] = mock_ssm

        with pytest.raises(ModularCliSdkConfigurationException,
                           match="Unable to save"):
            manager.store({"key": "value"})

    def test_extract_raises_on_string_result(self, mock_context):
        """Test extract raises when SSM returns string (invalid config)"""
        mock_ssm = MagicMock()
        mock_ssm.get_parameter.return_value = "invalid string result"

        manager = SSMCredentialsManager(
            module_name="test_module",
            context=mock_context,
        )
        manager.__dict__['ssm_client'] = mock_ssm

        with pytest.raises(ModularCliSdkConfigurationException,
                           match="Can not load"):
            manager.extract()

    def test_extract_raises_when_not_configured(self, mock_context):
        """Test extract raises when no configuration exists"""
        mock_ssm = MagicMock()
        mock_ssm.get_parameter.return_value = None

        manager = SSMCredentialsManager(
            module_name="test_module",
            context=mock_context,
        )
        manager.__dict__['ssm_client'] = mock_ssm

        with pytest.raises(ModularCliSdkConfigurationException,
                           match="not configured"):
            manager.extract()

    def test_clean_up_returns_not_found_message(self, mock_context):
        """Test clean_up returns appropriate message when parameter doesn't exist"""
        mock_ssm = MagicMock()
        mock_ssm.delete_parameter.return_value = False

        manager = SSMCredentialsManager(
            module_name="test_module",
            context=mock_context,
        )
        manager.__dict__['ssm_client'] = mock_ssm

        result = manager.clean_up()

        assert "not found" in result.lower()

    def test_clean_up_returns_success_message(self, mock_context):
        """Test clean_up returns success message when parameter is deleted"""
        mock_ssm = MagicMock()
        mock_ssm.delete_parameter.return_value = True

        manager = SSMCredentialsManager(
            module_name="test_module",
            context=mock_context,
        )
        manager.__dict__['ssm_client'] = mock_ssm

        result = manager.clean_up()

        assert "successfully deleted" in result.lower()

    def test_exists_returns_false_on_exception(self, mock_context):
        """Test exists returns False when SSM raises exception"""
        mock_ssm = MagicMock()
        mock_ssm.get_parameter.side_effect = Exception("Connection error")

        manager = SSMCredentialsManager(
            module_name="test_module",
            context=mock_context,
        )
        manager.__dict__['ssm_client'] = mock_ssm

        assert manager.exists() is False

    def test_ssm_client_returns_vault_when_configured(
            self,
            mock_context,
            monkeypatch,
    ) -> None:
        """Test ssm_client property returns Vault when env vars are set"""
        monkeypatch.setenv("MODULAR_CLI_SDK_VAULT_ADDR", "http://vault:8200")
        monkeypatch.setenv("MODULAR_CLI_SDK_VAULT_TOKEN", "test-token")

        manager = SSMCredentialsManager(
            module_name="test_module",
            context=mock_context,
        )

        # Access the property (will use cached_property)
        client = manager.ssm_client

        from modular_cli_sdk.client.ssm_client import VaultSecretsManager
        assert isinstance(client, VaultSecretsManager)

    def test_ssm_client_returns_ssm_when_vault_not_configured(
            self,
            mock_context,
            clean_vault_env,
    ) -> None:
        """Test ssm_client property returns SSM when Vault not configured"""
        manager = SSMCredentialsManager(
            module_name="test_module",
            context=mock_context,
        )

        with patch('boto3.client') as mock_boto:
            mock_boto.return_value = MagicMock()
            client = manager.ssm_client

            from modular_cli_sdk.client.ssm_client import SSMSecretsManager
            assert isinstance(client, SSMSecretsManager)

    def test_username_sanitization(self, mock_context):
        """Test that special characters in username are sanitized"""
        mock_context.obj = {"modular_admin_username": "user@domain.com"}

        manager = SSMCredentialsManager(
            module_name="test_module",
            context=mock_context,
        )

        # @ should be replaced with -
        assert "@" not in manager.ssm_secret_name
        assert "user-domain.com" in manager.ssm_secret_name

    def test_username_with_special_chars(self, mock_context):
        """Test username with various special characters"""
        mock_context.obj = {"modular_admin_username": "user!@#$%test"}

        manager = SSMCredentialsManager(
            module_name="test_module",
            context=mock_context,
        )

        # All special chars should be replaced
        assert "!" not in manager.ssm_secret_name
        assert "@" not in manager.ssm_secret_name
        assert "#" not in manager.ssm_secret_name
        assert "$" not in manager.ssm_secret_name
        assert "%" not in manager.ssm_secret_name

    def test_vault_path_prefix_passed_to_vault_manager(
            self,
            mock_context,
            monkeypatch,
    ) -> None:
        """Test that vault_path_prefix is passed to VaultSecretsManager"""
        monkeypatch.setenv("MODULAR_CLI_SDK_VAULT_ADDR", "http://vault:8200")
        monkeypatch.setenv("MODULAR_CLI_SDK_VAULT_TOKEN", "test-token")

        manager = SSMCredentialsManager(
            module_name="test_module",
            context=mock_context,
            vault_path_prefix="custom/prefix",
            vault_mount_point="custom_mount",
        )

        client = manager.ssm_client

        from modular_cli_sdk.client.ssm_client import VaultSecretsManager
        assert isinstance(client, VaultSecretsManager)
        assert client.path_prefix == "custom/prefix"
        assert client.mount_point == "custom_mount"


class TestCredentialsProvider:
    """Tests for CredentialsProvider factory"""

    def test_returns_filesystem_manager_in_standalone_mode(self):
        """Test that standalone mode returns FileSystemCredentialsManager"""
        ctx = MagicMock()
        ctx.obj = {}  # Empty = standalone

        provider = CredentialsProvider(module_name="test_module", context=ctx)

        assert provider.is_modular_mode() is False
        assert isinstance(
            provider.credentials_manager, FileSystemCredentialsManager,
        )

    def test_returns_ssm_manager_in_modular_mode(self):
        """Test that modular mode returns SSMCredentialsManager"""
        ctx = MagicMock()
        ctx.obj = {"modular_admin_username": "test_user"}

        provider = CredentialsProvider(module_name="test_module", context=ctx)

        assert provider.is_modular_mode() is True
        assert isinstance(provider.credentials_manager, SSMCredentialsManager)

    def test_handles_non_dict_context_obj(self):
        """Test that non-dict context.obj is handled as standalone mode"""
        ctx = MagicMock()
        ctx.obj = None

        provider = CredentialsProvider(module_name="test_module", context=ctx)

        assert provider.is_modular_mode() is False

    def test_handles_list_context_obj(self):
        """Test that list context.obj is handled as standalone mode"""
        ctx = MagicMock()
        ctx.obj = ["some", "list"]

        provider = CredentialsProvider(module_name="test_module", context=ctx)

        assert provider.is_modular_mode() is False

    def test_handles_string_context_obj(self):
        """Test that string context.obj is handled as standalone mode"""
        ctx = MagicMock()
        ctx.obj = "some string"

        provider = CredentialsProvider(module_name="test_module", context=ctx)

        assert provider.is_modular_mode() is False

    def test_modular_mode_with_empty_username(self):
        """Test that empty username is treated as standalone mode"""
        ctx = MagicMock()
        ctx.obj = {"modular_admin_username": ""}

        provider = CredentialsProvider(module_name="test_module", context=ctx)

        assert provider.is_modular_mode() is False

    def test_modular_mode_with_none_username(self):
        """Test that None username is treated as standalone mode"""
        ctx = MagicMock()
        ctx.obj = {"modular_admin_username": None}

        provider = CredentialsProvider(module_name="test_module", context=ctx)

        assert provider.is_modular_mode() is False

    def test_vault_params_passed_to_ssm_manager(self):
        """Test that vault params are passed to SSMCredentialsManager"""
        ctx = MagicMock()
        ctx.obj = {"modular_admin_username": "test_user"}

        provider = CredentialsProvider(
            module_name="test_module",
            context=ctx,
            vault_path_prefix="my/prefix",
            vault_mount_point="my_mount",
        )

        manager = provider.credentials_manager
        assert isinstance(manager, SSMCredentialsManager)
        assert manager._vault_path_prefix == "my/prefix"
        assert manager._vault_mount_point == "my_mount"
