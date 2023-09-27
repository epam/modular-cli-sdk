import json
import os
import shutil
from abc import ABC, abstractmethod
from functools import cached_property
from pathlib import Path

from modular_cli_sdk.client.ssm_client import SSMSecretsManager, \
    AbstractSecretsManager, VaultSecretsManager
from modular_cli_sdk.commons.constants import CONTEXT_MODULAR_ADMIN_USERNAME, \
    ENV_VAULT_TOKEN, ENV_VAULT_ADDR
from modular_cli_sdk.commons.exception import \
    ModularCliSdkConfigurationException
from modular_cli_sdk.commons.logger import get_logger

_LOG = get_logger(__name__)


class AbstractCredentialsManager(ABC):

    @abstractmethod
    def store(self, config: dict) -> str:
        """
        Store credentials. Works with file system in standalone installation or
        with AWS Parameter Store if module is a part of Modular-API
        """
        ...

    @abstractmethod
    def extract(self) -> dict:
        """
        Extract credentials. Works with file system in standalone installation or
        with AWS Parameter Store if module is a part of Modular-API
        """
        ...

    @abstractmethod
    def clean_up(self) -> str:
        """
        Delete credentials. Remove records from file system in case of standalone
        installation or remove parameter from AWS Parameter Store if module is a
        part of Modular-API
        """


class CredentialsProvider:
    def __init__(self, module_name, context):
        self.module_name = module_name
        self.context = context

    def is_modular_mode(self) -> bool:
        """
        Tells whether this instance is in m3-modular-admin mode
        :return:
        """
        obj = self.context.obj
        if not isinstance(obj, dict):
            return False
        return bool(obj.get(CONTEXT_MODULAR_ADMIN_USERNAME))

    @property
    def credentials_manager(self):
        if self.is_modular_mode():
            instance = SSMCredentialsManager(self.module_name, self.context)
        else:
            instance = FileSystemCredentialsManager(self.module_name)
        return instance


class FileSystemCredentialsManager(AbstractCredentialsManager):

    def __init__(self, module_name: str):
        home = str(Path.home())
        self.module_name = module_name
        self.creds_folder_path = os.path.join(home, f'.{module_name}')
        self.config_file_path = os.path.join(self.creds_folder_path,
                                             'credentials')

    def store(self, config: dict) -> str:
        try:
            Path(self.creds_folder_path).mkdir(exist_ok=True, parents=True)
        except OSError as e:
            _LOG.error(
                f'Unable to create configuration folder '
                f'{self.creds_folder_path}. Reason: {str(e)}')
            raise ModularCliSdkConfigurationException(
                f'Unable to create configuration folder {self.creds_folder_path}'
            )

        with open(self.config_file_path, 'w+') as config_file:
            json.dump(config, config_file)
        _LOG.debug(
            f'Configuration created successfully. Stored by path: '
            f'{self.config_file_path}')
        # todo review:fix
        # TODO, I think it's bad to return these obviously human strings here.
        #  We should return bool or None or smt, and the user of this class
        #  must decide what string to output based on the result.
        #  But no - we simply imply our string which may or may not be
        #  appropriate.
        #  Also, it's not easily readable for PC: clean_up returns different
        #  strings in case the config was or wasn't cleaned. And how is the
        #  programmers supposed to know, whether the config was cleaned?
        #  By using regex?
        return f'The configuration for {self.module_name} tool was ' \
               f'successfully saved locally'

    def extract(self) -> dict:
        if not os.path.exists(self.config_file_path):
            _LOG.error(
                f'Can not find configuration file by path: '
                f'{self.config_file_path}')
            raise ModularCliSdkConfigurationException(
                f'The {self.module_name} tool is not configured. '
                f'Please execute the configuration command')
        with open(self.config_file_path, 'r') as config_file:
            config_dict = json.load(config_file)
        _LOG.debug('Configuration successfully loaded')
        return config_dict

    def clean_up(self) -> str:
        try:
            shutil.rmtree(self.creds_folder_path)
        except FileNotFoundError:
            return f'Configuration for {self.module_name} tool not found. ' \
                   f'Nothing to delete'
        except OSError:
            _LOG.error(
                f'Error occurred while cleaning {self.module_name} '
                f'configuration by path: {self.creds_folder_path}.')
        return f'The {self.module_name} tool configuration has been deleted.'


class SSMCredentialsManager(AbstractCredentialsManager):

    def __init__(self, module_name: str, context):
        """
        :param module_name: str
        :param context: click.Context
        """
        self.context = context
        user_name = context.obj[CONTEXT_MODULAR_ADMIN_USERNAME]
        user_name = AbstractSecretsManager.allowed_name(user_name)
        self.module_name = module_name
        self.ssm_secret_name = self.build_ssm_secret_name(
            module_name=module_name,
            user_name=user_name
        )

    @staticmethod
    def build_ssm_secret_name(module_name: str, user_name: str) -> str:
        return f'modular-api.{module_name}.{user_name}.configuration'

    @cached_property
    def ssm_client(self) -> AbstractSecretsManager:
        """
        Can possibly return any implemented client
        :return:
        """
        if os.environ.get(ENV_VAULT_TOKEN) and os.environ.get(ENV_VAULT_ADDR):
            _LOG.debug('Returning vault secrets manager')
            return VaultSecretsManager()
        _LOG.debug('Returning SSM secrets manager')
        return SSMSecretsManager()

    def store(self, config: dict) -> str:
        saved = self.ssm_client.put_parameter(
            name=self.ssm_secret_name,
            value=config
        )
        if saved:
            return f'The configuration for {self.module_name} tool was ' \
                   f'successfully saved remotely. Parameter name: ' \
                   f'{self.ssm_secret_name}'
        raise ModularCliSdkConfigurationException(
            f'Unable to save configuration for {self.module_name} to SSM'
        )

    def extract(self) -> dict:
        result = self.ssm_client.get_parameter(name=self.ssm_secret_name)
        if not result:
            raise ModularCliSdkConfigurationException(
                f'The {self.module_name} tool is not configured. '
                f'Please execute the configuration command')
        if isinstance(result, str):
            raise ModularCliSdkConfigurationException(
                'Can not load configuration. For more information '
                'please check logs')
        # isinstance(result, (dict, list))
        return result

    def clean_up(self) -> str:
        removed = self.ssm_client.delete_parameter(name=self.ssm_secret_name)
        if not removed:
            return f'Configuration for {self.module_name} tool not found. ' \
                   f'Nothing to delete'
        return f'Configuration for {self.module_name} tool was successfully ' \
               f'deleted'
