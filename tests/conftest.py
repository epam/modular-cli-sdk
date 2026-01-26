import pytest
from unittest.mock import MagicMock, patch
from click import Context


@pytest.fixture
def mock_click_context():
    """Create a mock Click context for standalone mode"""
    ctx = MagicMock(spec=Context)
    ctx.obj = {}  # Empty dict = standalone mode
    return ctx


@pytest.fixture
def mock_click_context_modular():
    """Create a mock Click context for modular-admin mode"""
    ctx = MagicMock(spec=Context)
    ctx.obj = {"modular_admin_username": "test_user"}
    return ctx


@pytest.fixture
def mock_ssm_client():
    """Mock boto3 SSM client"""
    with patch("boto3.client") as mock:
        yield mock.return_value


@pytest.fixture
def mock_vault_client():
    """Mock hvac client"""
    with patch("hvac.Client") as mock:
        yield mock.return_value


@pytest.fixture
def clean_vault_env(monkeypatch):
    """Remove all Vault-related environment variables"""
    env_vars = [
        # New env var names (recommended)
        "MODULAR_CLI_SDK_VAULT_ADDR",
        "MODULAR_CLI_SDK_VAULT_TOKEN",
        "MODULAR_CLI_SDK_VAULT_MOUNT_POINT",
        "MODULAR_CLI_SDK_VAULT_PATH_PREFIX",
        # Old env var names (deprecated, backward compatible)
        "MODULAR_CLI_VAULT_ADDR",
        "MODULAR_CLI_VAULT_TOKEN",
    ]
    for var in env_vars:
        monkeypatch.delenv(var, raising=False)
    return monkeypatch
