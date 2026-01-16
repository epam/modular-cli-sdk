import json
import os
import re
from abc import abstractmethod, ABC
from functools import cached_property
from typing import Optional, Union, List, Dict

import boto3
from botocore.client import ClientError
from botocore.credentials import JSONFileCache
from botocore.exceptions import NoCredentialsError, NoRegionError

from modular_cli_sdk.commons.constants import (
    ENV_VAULT_ADDR,
    ENV_VAULT_TOKEN,
    ENV_VAULT_PATH_PREFIX,
    ENV_VAULT_MOUNT_POINT,
    DEFAULT_VAULT_MOUNT_POINT,
    DEFAULT_VAULT_PATH_PREFIX,
    get_vault_token,
    get_vault_addr,
)
from modular_cli_sdk.commons.logger import get_logger

_LOG = get_logger(__name__)

SSM_NOT_AVAILABLE = re.compile(r'[^a-zA-Z0-9\/_.-]')
SecretValue = Union[Dict, List, str]


class AbstractSecretsManager(ABC):

    @staticmethod
    def allowed_name(name: str) -> str:
        """
        Keeps only allowed symbols
        """
        return str(re.sub(SSM_NOT_AVAILABLE, '-', name))

    @abstractmethod
    def get_parameter(self, name: str) -> Optional[SecretValue]:
        ...

    @abstractmethod
    def put_parameter(self, name: str, value: SecretValue,
                      _type='SecureString') -> bool:
        ...

    @abstractmethod
    def delete_parameter(self, name: str) -> bool:
        """
        Returns True in case the parameter was saved successfully
        :param name:
        :return:
        """


class OnPremSecretsManager(AbstractSecretsManager):
    """
    The purpose is only debug and local testing. It must not be used as
    prod environment because it's not secure at all. Here I just
    emulate some parameter store. In case we really need on-prem,
    we must use Vault
    """
    path = os.path.expanduser(
        os.path.join('~', '.modular_cli', 'on-prem', 'ssm')
    )

    def __init__(self):
        self._store = JSONFileCache(self.path)

    def put_parameter(self, name: str, value: SecretValue,
                      _type='SecureString') -> bool:
        self._store[name] = value
        return True

    def get_parameter(self, name: str) -> Optional[SecretValue]:
        if name in self._store:
            return self._store[name]

    def delete_parameter(self, name: str) -> bool:
        if name in self._store:
            del self._store[name]
            return True
        return False


class VaultSecretsManager(AbstractSecretsManager):
    """
    Vault KV v2 secrets manager.

    Supports configurable mount point and path prefix via:
    - Constructor parameters (highest priority)
    - Environment variables - new names (recommended)
    - Environment variables - old names (deprecated, backward compatible)
    - Default values (lowest priority)

    Environment variable precedence:
    - MODULAR_CLI_SDK_VAULT_* (new, recommended)
    - MODULAR_CLI_VAULT_* (old, deprecated but supported)
    """

    KEY = 'kv'

    def __init__(
            self,
            mount_point: Optional[str] = None,
            path_prefix: Optional[str] = None,
            url: Optional[str] = None,
            token: Optional[str] = None,
    ) -> None:
        """
        Initialize VaultSecretsManager.

        :param mount_point: Vault KV mount point (default: 'secret' or from env)
        :param path_prefix: Path prefix for secrets (default: '' or from env)
        :param url: Vault server URL (default: from env)
        :param token: Vault token (default: from env)
        """
        self._client = None
        self._mount_point = mount_point
        self._path_prefix = path_prefix
        self._url = url
        self._token = token

    @property
    def mount_point(self) -> str:
        """Get mount point from constructor, env var, or default."""
        if self._mount_point is not None:
            return self._mount_point
        return os.getenv(ENV_VAULT_MOUNT_POINT, DEFAULT_VAULT_MOUNT_POINT)

    @property
    def path_prefix(self) -> str:
        """Get path prefix from constructor, env var, or default."""
        if self._path_prefix is not None:
            return self._path_prefix
        return os.getenv(ENV_VAULT_PATH_PREFIX, DEFAULT_VAULT_PATH_PREFIX)

    @property
    def url(self) -> Optional[str]:
        """
        Get Vault URL with backward compatibility.
        Priority: constructor > new env var > old env var
        """
        if self._url:
            return self._url
        return get_vault_addr()

    @property
    def token(self) -> Optional[str]:
        """
        Get Vault token with backward compatibility.
        Priority: constructor > new env var > old env var
        """
        if self._token:
            return self._token
        return get_vault_token()

    @staticmethod
    def _normalize_path(path: str) -> str:
        """Normalize path by removing leading/trailing slashes."""
        return path.strip('/') if path else ''

    def _build_full_path(self, name: str) -> str:
        """
        Build full path with optional prefix.

        Examples:
            - name='secret.name', prefix='' -> 'secret.name'
            - name='secret.name', prefix='modular' -> 'modular/secret.name'
        """
        prefix = self._normalize_path(self.path_prefix)
        name = self._normalize_path(name)

        if prefix:
            return f'{prefix}/{name}'
        return name

    def _init_client(self):
        try:
            import hvac
        except ImportError:
            raise RuntimeError(
                'Install hvac to use Vault client. "pip install hvac==0.11.2"'
            )

        url = self.url
        token = self.token

        if not url:
            raise RuntimeError(
                f'Vault URL not configured. Set {ENV_VAULT_ADDR} environment '
                f'variable or pass url parameter.'
            )
        if not token:
            raise RuntimeError(
                f'Vault token not configured. Set {ENV_VAULT_TOKEN} environment'
                f' variable or pass token parameter.'
            )

        _LOG.debug(f'Initializing hvac client for URL: {url}')
        self._client = hvac.Client(url=url, token=token)
        _LOG.debug('Hvac client was initialized')

    @property
    def client(self):
        if not self._client:
            self._init_client()
        return self._client

    def get_parameter(self, name: str) -> Optional[SecretValue]:
        full_path = self._build_full_path(name)
        _LOG.debug(f'Getting parameter from path: {full_path}')
        try:
            response = self.client.secrets.kv.v2.read_secret_version(
                path=full_path,
                mount_point=self.mount_point,
            ) or {}
        except Exception as e:
            _LOG.debug(f'Failed to get parameter {full_path}: {e}')
            return None
        return response.get('data', {}).get('data', {}).get(self.KEY)

    def put_parameter(
            self,
            name: str,
            value: SecretValue,
            _type='SecureString',
    ) -> bool:
        full_path = self._build_full_path(name)
        _LOG.debug(f'Putting parameter to path: {full_path}')
        try:
            self.client.secrets.kv.v2.create_or_update_secret(
                path=full_path,
                secret={self.KEY: value},
                mount_point=self.mount_point,
            )
            return True
        except Exception as e:
            _LOG.error(f'Failed to put parameter {full_path}: {e}')
            return False

    def delete_parameter(self, name: str) -> bool:
        full_path = self._build_full_path(name)
        _LOG.debug(f'Deleting parameter from path: {full_path}')
        try:
            result = self.client.secrets.kv.v2.delete_metadata_and_all_versions(
                path=full_path,
                mount_point=self.mount_point,
            )
            return bool(result)
        except Exception as e:
            _LOG.error(f'Failed to delete parameter {full_path}: {e}')
            return False

    def enable_secrets_engine(self, mount_point: Optional[str] = None) -> bool:
        target_mount = mount_point or self.mount_point
        try:
            self.client.sys.enable_secrets_engine(
                backend_type='kv',
                path=target_mount,
                options={'version': 2}
            )
            return True
        except Exception as e:
            _LOG.debug(f'Failed to enable secrets engine: {e}')
            return False

    def is_secrets_engine_enabled(
            self,
            mount_point: Optional[str] = None,
    ) -> bool:
        mount_points = self.client.sys.list_mounted_secrets_engines()
        target_point = mount_point or self.mount_point
        return f'{target_point}/' in mount_points


class SSMSecretsManager(AbstractSecretsManager):
    def __init__(self, region: Optional[str] = None):
        self._region = region

    @cached_property
    def client(self):
        _LOG.info('Initializing ssm boto3 client')
        try:
            return boto3.client('ssm', region_name=self._region)
        except NoCredentialsError:
            raise ValueError('No aws credentials could be found')
        except NoRegionError:
            raise ValueError(
                'No aws region could be found. Set AWS_DEFAULT_REGION environment'
            )

    def get_parameter(self, name: str) -> Optional[SecretValue]:
        try:
            response = self.client.get_parameter(
                Name=name,
                WithDecryption=True,
            )
            value_str = response['Parameter']['Value']
            _LOG.debug(f"Configuration '{name}' from SSM received")
            try:
                return json.loads(value_str)
            except json.JSONDecodeError:
                _LOG.warning(
                    'Could not load json from SSM value. Returning raw string'
                )
                return value_str
        except ClientError as e:
            error_code = e.response['Error']['Code']
            _LOG.error(
                f"Can't get secret for name '{name}', error code: '{error_code}'"
            )
            return None

    def put_parameter(
            self,
            name: str,
            value: SecretValue,
            _type='SecureString',
    ) -> bool:
        try:
            if isinstance(value, (list, dict)):
                value = json.dumps(value)
            _LOG.debug(f"Saving '{name}' to SSM")
            self.client.put_parameter(
                Name=name,
                Value=value,
                Overwrite=True,
                Type=_type,
            )
            return True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            _LOG.error(
                f"Can't put secret for name '{name}', error code: '{error_code}'"
            )
            return False

    def delete_parameter(self, name: str) -> bool:
        try:
            _LOG.info(f'Removing {name} from SSM')
            self.client.delete_parameter(Name=name)
        except ClientError as e:
            error_code = e.response['Error']['Code']
            _LOG.error(
                f"Can't delete secret name '{name}', error code: '{error_code}'"
            )
            return False
        return True
