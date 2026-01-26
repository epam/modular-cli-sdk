import pytest
from unittest.mock import MagicMock, patch
from click import Context


@pytest.fixture
def mock_click_context():
    """Create a mock Click context for standalone mode."""
    ctx = MagicMock(spec=Context)
    ctx.obj = {}  # Empty dict = standalone mode
    return ctx


@pytest.fixture
def mock_click_context_modular():
    """Create a mock Click context for modular-admin mode."""
    ctx = MagicMock(spec=Context)
    ctx.obj = {"modular_admin_username": "test_user"}
    return ctx


@pytest.fixture
def mock_ssm_client():
    """Mock boto3 SSM client."""
    with patch("boto3.client") as mock:
        yield mock.return_value


@pytest.fixture
def mock_vault_client():
    """Mock hvac client."""
    with patch("hvac.Client") as mock:
        yield mock.return_value
