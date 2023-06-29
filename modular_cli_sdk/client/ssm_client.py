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

from modular_cli_sdk.commons.constants import ENV_VAULT_ADDR, ENV_VAULT_TOKEN
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
    path = os.path.expanduser(os.path.join('~', '.modular_cli', 'on-prem', 'ssm'))

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
    mount_point = 'kv'
    key = 'data'

    def __init__(self):
        self._client = None  # hvac.Client

    def _init_client(self):
        try:
            import hvac
        except ImportError:
            raise RuntimeError('Install hvac to use Vault client. '
                               '"pip install hvac==0.11.2"')
        _LOG.debug('Initializing hvac client')
        self._client = hvac.Client(
            url=os.getenv(ENV_VAULT_ADDR),
            token=os.getenv(ENV_VAULT_TOKEN)
        )
        _LOG.debug('Hvac client was initialized')

    @property
    def client(self):
        if not self._client:
            self._init_client()
        return self._client

    def get_parameter(self, name: str) -> Optional[SecretValue]:
        try:
            response = self.client.secrets.kv.v2.read_secret_version(
                path=name, mount_point=self.mount_point) or {}
        except Exception:  # hvac.InvalidPath
            return
        return response.get('data', {}).get('data', {}).get(self.key)

    def put_parameter(self, name: str, value: SecretValue,
                      _type='SecureString') -> bool:
        self.client.secrets.kv.v2.create_or_update_secret(
            path=name,
            secret={self.key: value},
            mount_point=self.mount_point
        )
        return True

    def delete_parameter(self, name: str) -> bool:
        return bool(self.client.secrets.kv.v2.delete_metadata_and_all_versions(
            path=name, mount_point=self.mount_point))

    def enable_secrets_engine(self, mount_point=None) -> bool:
        try:
            self.client.sys.enable_secrets_engine(
                backend_type='kv',
                path=(mount_point or self.mount_point),
                options={'version': 2}
            )
            return True
        except Exception:  # hvac.exceptions.InvalidRequest
            return False  # already exists

    def is_secrets_engine_enabled(self, mount_point=None) -> bool:
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
            raise ValueError('No aws region could be found. Set AWS_DEFAULT_REGION environment')

    def get_parameter(self, name: str) -> Optional[SecretValue]:
        try:
            response = self.client.get_parameter(
                Name=name,
                WithDecryption=True
            )
            value_str = response['Parameter']['Value']
            _LOG.debug(f'Configuration \'{name}\' from SSM received')
            try:
                return json.loads(value_str)
            except json.JSONDecodeError:
                _LOG.warning('Could not load json from SSM value. '
                             'Returning raw string')
                return value_str
        except ClientError as e:
            error_code = e.response['Error']['Code']
            _LOG.error(f'Can\'t get secret for name \'{name}\', '
                       f'error code: \'{error_code}\'')
            return

    def put_parameter(self, name: str, value: SecretValue,
                      _type='SecureString') -> bool:
        try:
            if isinstance(value, (list, dict)):
                value = json.dumps(value)
            _LOG.debug(f'Saving \'{name}\' to SSM')
            self.client.put_parameter(
                Name=name,
                Value=value,
                Overwrite=True,
                Type=_type)
            return True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            _LOG.error(f'Can\'t put secret for name \'{name}\', '
                       f'error code: \'{error_code}\'')
            return False

    def delete_parameter(self, name: str) -> bool:
        try:
            _LOG.info(f'Removing {name} from SSM')
            self.client.delete_parameter(Name=name)
        except ClientError as e:
            error_code = e.response['Error']['Code']
            _LOG.error(f'Can\'t delete secret name \'{name}\', '
                       f'error code: \'{error_code}\'')
            return False
        return True
