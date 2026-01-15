import os
from typing import Optional

# =============================================================================
# NEW Environment variable names (recommended)
# =============================================================================
ENV_VAULT_TOKEN = 'MODULAR_CLI_SDK_VAULT_TOKEN'
ENV_VAULT_ADDR = 'MODULAR_CLI_SDK_VAULT_ADDR'
ENV_VAULT_PATH_PREFIX = 'MODULAR_CLI_SDK_VAULT_PATH_PREFIX'
ENV_VAULT_MOUNT_POINT = 'MODULAR_CLI_SDK_VAULT_MOUNT_POINT'

# =============================================================================
# OLD Environment variable names (deprecated, kept for backward compatibility)
# =============================================================================
ENV_VAULT_TOKEN_OLD = 'MODULAR_CLI_VAULT_TOKEN'
ENV_VAULT_ADDR_OLD = 'MODULAR_CLI_VAULT_ADDR'

# =============================================================================
# Default values
# =============================================================================
DEFAULT_VAULT_MOUNT_POINT = 'secret'
DEFAULT_VAULT_PATH_PREFIX = ''  # Empty = root level (old behavior)

# =============================================================================
# Context keys
# =============================================================================
CONTEXT_MODULAR_ADMIN_USERNAME = 'modular_admin_username'


# =============================================================================
# Helper functions (evaluated at runtime, with backward compatibility)
# =============================================================================
def get_vault_token() -> Optional[str]:
    """
    Get Vault token with backward compatibility.
    Priority: new env var > old env var
    """
    return os.environ.get(ENV_VAULT_TOKEN) or os.environ.get(ENV_VAULT_TOKEN_OLD)


def get_vault_addr() -> Optional[str]:
    """
    Get Vault address with backward compatibility.
    Priority: new env var > old env var
    """
    return os.environ.get(ENV_VAULT_ADDR) or os.environ.get(ENV_VAULT_ADDR_OLD)
