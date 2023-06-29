# This is a temporary repository used to remap projects before push to Github

# Modular CLI SDK


### [Building distribution archives](https://packaging.python.org/en/latest/tutorials/packaging-projects/#generating-distribution-archives)
- Make sure you have the latest version of PyPA’s build installed: `python3 -m pip install --upgrade build`
- Run the command form the same directory where `pyptoject.toml` is located: `python3 -m build`
- This command should output a lot of text and once completed should generate two files in the dist directory:
```
dist/
    modular_cli_sdk-{version}.tar.gz
    modular_cli_sdk-{version}-py3-none-any.whl
```

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
  * config (dict) [Required] - takes a dictionary with tool configuration data  
  Return type:
  * str  

* extract() # retrieve saved configuration  
  Parameters:
  * None  
  Return type:
  * dict

* clean_up() # delete saved configuration 
  Parameters:
  * None  
  Return type:
  * str  
  