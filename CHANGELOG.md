# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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