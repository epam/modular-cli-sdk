# Modular CLI SDK
Modular CLI SDK is a core component for CLI tools built atop of Modular Framework

### Installation
To install Modular CLI SDK please use `pip` command:
* standard installation `pip install "modular_cli_sdk"`

### Usage:
#### 1. Credentials Manager
_class CredentialsProvider_  
Used for storing, extracting and deleting credentials. In case if a tool installed in 
standalone mode all operations with credentials are carried out using the user`s 
file system. In case if a tool installed as a part of 
[Modular-API](https://git.epam.com/epmc-eoos/m3-modular-admin) the AWS Parameter 
Store (SSM) will be used instead of file system.  

In standalone installation credentials will be placed by path: 
`~user_home_directory/.<tool_name>/credentials`  
In Modular-API's installation credentials will be placed at SSM by name: 
`modular-api.<tool_name>.<system_username>.configuration`
```
from modular_cli_sdk.services.credentials_manager import CredentialsProvider

configuration = CredentialsProvider(module_name="tool_name", context: Click.Context)
```

To access to the available methods use class property `credentials_manager`:
```
configuration.credentials_manager.store(config=$config_dict)
configuration.credentials_manager.extract()
configuration.credentials_manager.extract()
```

* store(config= ) # saving given configuration  
  Parameters:
  * `config` (dict) [Required] - takes a dictionary with tool configuration data  
  Return type:
  * `str`  

* extract() # retrieve saved configuration  
  Parameters:
  * `None`  
  Return type:
  * `dict`

* clean_up() # delete saved configuration 
  Parameters:
  * `None`  
  Return type:
  * `str`  
  