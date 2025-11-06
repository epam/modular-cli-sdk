# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

# [3.1.0] - 2025-11-05
* Add library `click>=8.0.0,<9.0.0` to `pyproject.toml` dependencies
* Add `deprecated` decorator to mark commands as deprecated
  * Displays a warning message when a deprecated command is used
  * Warning includes deprecation date, removal date, and alternative command
  * Color-coded warnings based on time left until removal (yellow for >30 days, red for ≤30 days)

# [3.0.0] - 2025-07-08
* Remove `setup.py`, `requirements.txt`, and `setup.cfg` files
* Update the `pyproject.toml` file
* Update library dependencies:
  * `boto3` from `==1.26.80` to `>=1.36.11,<2`
  * `botocore` from `==1.29.80` to `>=1.36.11,<2`
  * `hvac` from `==1.2.1` to `~=2.1.0`

# [2.1.0] - 2024-02-13
* Set Python 3.10 as a default version

# [2.0.0] - 2023-09-26
* Added Python 3.10 compatibility
* updated libraries version
* File setup.cfg brought to compatibility with new setuptools syntax

# [1.1.3] - 2023-08-28
* fixed an error with `FileSystemCredentialsManager` clean_up method

# [1.1.2] - 2023-06-30
* Update `README.md`

# [1.1.1] - 2023-06-30
* Update `setup.cfg`

# [1.1.0] - 2023-05-11
* Removed `SSMService` and put its logic to `SSMClient`;
* Created SSM client interface and Vault, SSM, File System implementations;
* minor fixes

# [1.0.1] - 2023-04-27
* `CredentialsManager` class refactoring. New class is `CredentialsProvider`

# [1.0.0] - 2023-04-24
* Initial version