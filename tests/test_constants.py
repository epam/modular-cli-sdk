"""
Tests for constants module - environment variable helpers
"""
from modular_cli_sdk.commons.constants import (
    get_vault_token,
    get_vault_addr,
    CONTEXT_MODULAR_ADMIN_USERNAME,
    ENV_VAULT_ADDR,
    ENV_VAULT_TOKEN,
    ENV_VAULT_PATH_PREFIX,
    ENV_VAULT_MOUNT_POINT,
    ENV_VAULT_ADDR_OLD,
    ENV_VAULT_TOKEN_OLD,
    DEFAULT_VAULT_MOUNT_POINT,
    DEFAULT_VAULT_PATH_PREFIX,
)


class TestVaultEnvHelpers:
    """Tests for Vault environment variable helpers"""

    def test_get_vault_token_from_new_env(self, monkeypatch):
        """Test getting Vault token from new env var"""
        monkeypatch.delenv("MODULAR_CLI_VAULT_TOKEN", raising=False)
        monkeypatch.setenv("MODULAR_CLI_SDK_VAULT_TOKEN", "new-token")

        assert get_vault_token() == "new-token"

    def test_get_vault_token_from_old_env_fallback(self, monkeypatch):
        """Test getting Vault token from old env var (backward compat)"""
        monkeypatch.delenv("MODULAR_CLI_SDK_VAULT_TOKEN", raising=False)
        monkeypatch.setenv("MODULAR_CLI_VAULT_TOKEN", "old-token")

        assert get_vault_token() == "old-token"

    def test_get_vault_token_new_takes_priority(self, monkeypatch):
        """Test that new env var takes priority over old"""
        monkeypatch.setenv("MODULAR_CLI_SDK_VAULT_TOKEN", "new-token")
        monkeypatch.setenv("MODULAR_CLI_VAULT_TOKEN", "old-token")

        assert get_vault_token() == "new-token"

    def test_get_vault_token_returns_none_when_not_set(self, monkeypatch):
        """Test that None is returned when no env var is set"""
        monkeypatch.delenv("MODULAR_CLI_SDK_VAULT_TOKEN", raising=False)
        monkeypatch.delenv("MODULAR_CLI_VAULT_TOKEN", raising=False)

        assert get_vault_token() is None

    def test_get_vault_addr_from_new_env(self, monkeypatch):
        """Test getting Vault address from new env var"""
        monkeypatch.delenv("MODULAR_CLI_VAULT_ADDR", raising=False)
        monkeypatch.setenv("MODULAR_CLI_SDK_VAULT_ADDR", "http://new:8200")

        assert get_vault_addr() == "http://new:8200"

    def test_get_vault_addr_from_old_env_fallback(self, monkeypatch):
        """Test getting Vault address from old env var (backward compat)"""
        monkeypatch.delenv("MODULAR_CLI_SDK_VAULT_ADDR", raising=False)
        monkeypatch.setenv("MODULAR_CLI_VAULT_ADDR", "http://old:8200")

        assert get_vault_addr() == "http://old:8200"

    def test_get_vault_addr_new_takes_priority(self, monkeypatch):
        """Test that new env var takes priority over old"""
        monkeypatch.setenv("MODULAR_CLI_SDK_VAULT_ADDR", "http://new:8200")
        monkeypatch.setenv("MODULAR_CLI_VAULT_ADDR", "http://old:8200")

        assert get_vault_addr() == "http://new:8200"

    def test_get_vault_addr_returns_none_when_not_set(self, monkeypatch):
        """Test that None is returned when no env var is set"""
        monkeypatch.delenv("MODULAR_CLI_SDK_VAULT_ADDR", raising=False)
        monkeypatch.delenv("MODULAR_CLI_VAULT_ADDR", raising=False)

        assert get_vault_addr() is None


class TestConstants:
    """Tests for constant values"""

    def test_context_modular_admin_username_value(self):
        """Test the constant value for modular admin username context key"""
        assert CONTEXT_MODULAR_ADMIN_USERNAME == "modular_admin_username"

    def test_new_env_var_names(self):
        """Test new environment variable name constants"""
        assert ENV_VAULT_ADDR == "MODULAR_CLI_SDK_VAULT_ADDR"
        assert ENV_VAULT_TOKEN == "MODULAR_CLI_SDK_VAULT_TOKEN"
        assert ENV_VAULT_PATH_PREFIX == "MODULAR_CLI_SDK_VAULT_PATH_PREFIX"
        assert ENV_VAULT_MOUNT_POINT == "MODULAR_CLI_SDK_VAULT_MOUNT_POINT"

    def test_old_env_var_names(self):
        """Test old (deprecated) environment variable name constants"""
        assert ENV_VAULT_ADDR_OLD == "MODULAR_CLI_VAULT_ADDR"
        assert ENV_VAULT_TOKEN_OLD == "MODULAR_CLI_VAULT_TOKEN"

    def test_default_values(self):
        """Test default value constants"""
        assert DEFAULT_VAULT_MOUNT_POINT == "secret"
        assert DEFAULT_VAULT_PATH_PREFIX == ""
