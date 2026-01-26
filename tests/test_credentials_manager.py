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


class TestFileSystemCredentialsManager:
    """Tests for FileSystemCredentialsManager"""

    @pytest.fixture
    def temp_home(self, monkeypatch):
        """Create a temporary home directory for testing"""
        temp_dir = tempfile.mkdtemp()
        monkeypatch.setattr('pathlib.Path.home', lambda: type('Path', (), {
            '__str__': lambda s: temp_dir})())

        # Also patch os.path.join to use forward slashes consistently
        original_join = os.path.join
        monkeypatch.setattr(
            'os.path.join',
            lambda *args: original_join(*args).replace('\\', '/')
        )

        yield temp_dir

        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def fs_manager(self, temp_home):
        """Create FileSystemCredentialsManager with temp directory"""
        with patch('pathlib.Path.home', return_value=type('Path', (), {
            '__str__': lambda s: temp_home})()):
            with patch.object(
                    FileSystemCredentialsManager,
                    '__init__',
                    lambda self, module_name: setattr(self, 'module_name', module_name) or setattr(self, 'creds_folder_path', os.path.join(temp_home, f'.{module_name}')) or setattr(self, 'config_file_path', os.path.join(temp_home, f'.{module_name}', 'credentials'))
            ):
                manager = FileSystemCredentialsManager("test_module")
                manager.module_name = "test_module"
                manager.creds_folder_path = \
                    os.path.join(temp_home, '.test_module')
                manager.config_file_path = \
                    os.path.join(temp_home, '.test_module', 'credentials')
                return manager

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
        from modular_cli_sdk.commons.exception import \
            ModularCliSdkConfigurationException

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
        """Test that store() calls SSM put_parameter."""
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
            type(ssm_manager_new).ssm_client = PropertyMock(return_value=mock_ssm)

            config = {"api_key": "test_key"}
            result = ssm_manager_new.store(config)

            mock_ssm.put_parameter.assert_called_once()
            assert "successfully" in result.lower()

    def test_extract_returns_config_from_ssm(self, mock_context):
        """Test that extract() returns configuration from SSM."""
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
        """Test exists() returns True when SSM parameter exists."""
        mock_ssm = MagicMock()
        mock_ssm.get_parameter.return_value = {"api_key": "test"}

        manager = SSMCredentialsManager(
            module_name="test_module",
            context=mock_context,
        )
        manager.__dict__['ssm_client'] = mock_ssm

        assert manager.exists() is True

    def test_exists_returns_false_when_parameter_missing(self, mock_context):
        """Test exists() returns False when SSM parameter doesn't exist."""
        mock_ssm = MagicMock()
        mock_ssm.get_parameter.return_value = None

        manager = SSMCredentialsManager(
            module_name="test_module",
            context=mock_context,
        )
        manager.__dict__['ssm_client'] = mock_ssm

        assert manager.exists() is False


class TestCredentialsProvider:
    """Tests for CredentialsProvider factory."""

    def test_returns_filesystem_manager_in_standalone_mode(self):
        """Test that standalone mode returns FileSystemCredentialsManager."""
        ctx = MagicMock()
        ctx.obj = {}  # Empty = standalone

        provider = CredentialsProvider(module_name="test_module", context=ctx)

        assert provider.is_modular_mode() is False
        assert isinstance(provider.credentials_manager,
                          FileSystemCredentialsManager)

    def test_returns_ssm_manager_in_modular_mode(self):
        """Test that modular mode returns SSMCredentialsManager."""
        ctx = MagicMock()
        ctx.obj = {"modular_admin_username": "test_user"}

        provider = CredentialsProvider(module_name="test_module", context=ctx)

        assert provider.is_modular_mode() is True
        assert isinstance(provider.credentials_manager, SSMCredentialsManager)

    def test_handles_non_dict_context_obj(self):
        """Test that non-dict context.obj is handled as standalone mode."""
        ctx = MagicMock()
        ctx.obj = None

        provider = CredentialsProvider(module_name="test_module", context=ctx)

        assert provider.is_modular_mode() is False
