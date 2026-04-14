# Describe Vault secrets
```bash
# List secrets in 'secret/' mount
vault kv list secret/

# List secrets in 'kv/' mount
vault kv list kv/

# List secrets in 'secret/' mount under modular prefix path
vault kv list secret/modular/

Keys
----
modular-api.stm.***_***-epam.com.configuration
...

echo $MODULAR_CLI_SDK_VAULT_PATH_PREFIX

MODULAR_CLI_SDK_VAULT_PATH_PREFIX='modular'
```



# DEV env
```bash
export VAULT_ADDR=
export VAULT_TOKEN=
# Dry run
python vault_patch.py --list_incorrect --fix_incorrect --scan_all_mounts --delete_source --dry_run --vault_addr $VAULT_ADDR --vault_token $VAULT_TOKEN --path_prefix modular
# Apply patch but do not remove old
python vault_patch.py --list_incorrect --fix_incorrect --scan_all_mounts --vault_addr $VAULT_ADDR --vault_token $VAULT_TOKEN --path_prefix modular
# Apply patch and remove old
python vault_patch.py --list_incorrect --fix_incorrect --scan_all_mounts --delete_source --vault_addr $VAULT_ADDR --vault_token $VAULT_TOKEN --path_prefix modular
```
# QA env
```bash
export VAULT_ADDR=
export VAULT_TOKEN=
# Dry run
python vault_patch.py --list_incorrect --fix_incorrect --scan_all_mounts --delete_source --dry_run --vault_addr $VAULT_ADDR --vault_token $VAULT_TOKEN --path_prefix modular
# Apply patch but do not remove old
python vault_patch.py --list_incorrect --fix_incorrect --scan_all_mounts --vault_addr $VAULT_ADDR --vault_token $VAULT_TOKEN --path_prefix modular
# Apply patch and remove old
python vault_patch.py --list_incorrect --fix_incorrect --scan_all_mounts --delete_source --vault_addr $VAULT_ADDR --vault_token $VAULT_TOKEN --path_prefix modular
```
# PROD env
```bash
export VAULT_ADDR=
export VAULT_TOKEN=
# Dry run
python vault_patch.py --list_incorrect --fix_incorrect --scan_all_mounts --delete_source --dry_run --vault_addr $VAULT_ADDR --vault_token $VAULT_TOKEN --path_prefix modular
# Apply patch but do not remove old
python vault_patch.py --list_incorrect --fix_incorrect --scan_all_mounts --vault_addr $VAULT_ADDR --vault_token $VAULT_TOKEN --path_prefix modular
# Apply patch and remove old
python vault_patch.py --list_incorrect --fix_incorrect --scan_all_mounts --delete_source --vault_addr $VAULT_ADDR --vault_token $VAULT_TOKEN --path_prefix modular
```
