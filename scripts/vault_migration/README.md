# Vault Secret Migration Patch

Fixes secrets saved with incorrect mount point and/or secret key
by modular-cli-sdk versions v3.1.1–v3.1.3.

## Background: Vault KV v2 Structure

Vault KV v2 stores secrets using this structure:

```
API path:  /v1/{mount_point}/data/{secret_path}
                              ^^^^
                              This "data" is a FIXED API route segment.
                              It is NOT your secret key.

JSON body: { "{your_key}": { ...your actual values... } }
              ^^^^^^^^^^
              THIS is your secret key.
              "data" = correct (old code)
              "kv"   = buggy (v3.1.1-v3.1.3)
```

When you read a secret back, the full response looks like:

```json
{
  "data": {                    // ← Vault API envelope (always "data")
    "data": {                  // ← Vault KV v2 versioning (always "data")
      "data": {                // ← YOUR key (correct) or "kv" (buggy)
        "api_url": "https://example.com",
        "token": "abc123"
      }
    },
    "metadata": {
      "version": 1
    }
  }
}
```

Yes, there are three levels of `"data"` when everything is correct.
The first two are Vault's internal structure. Only the third one is yours.

## What Went Wrong

The old (correct) code used:

```python
mount_point = 'kv'     # ← correct
key         = 'data'   # ← correct
```

Buggy versions (v3.1.1–v3.1.3) swapped them:

```python
mount_point = 'secret'  # ← wrong (Vault's default mount name)
key         = 'kv'      # ← wrong (the old mount_point value leaked here)
```

This created two scenarios depending on the environment:

## Scenario 1: Wrong Key, Correct Mount

Some environments had `mount_point` overridden back to `'kv'`,
but the key was still wrong (`'kv'` instead of `'data'`).

```
BEFORE (broken):
  API:  PUT /v1/kv/data/my-app.config
  Body: { "kv": {"api_url": "...", "token": "..."} }
          ^^^^
          wrong key (should be "data")

AFTER (fixed):
  API:  PUT /v1/kv/data/my-app.config
  Body: { "data": {"api_url": "...", "token": "..."} }
          ^^^^^^
          correct key
```

**Fix:** Rename key `"kv"` → `"data"` within the same mount point.

## Scenario 2: Wrong Mount + Wrong Key

Both `mount_point` and `key` were affected by the bug.

```
BEFORE (broken):
  API:  PUT /v1/secret/data/my-app.config
  Body: { "kv": {"api_url": "...", "token": "..."} }
          ^^^^
          wrong key at wrong mount point

AFTER (fixed):
  API:  PUT /v1/kv/data/my-app.config
  Body: { "data": {"api_url": "...", "token": "..."} }
          ^^^^^^
          correct key at correct mount point
```

**Fix:** Move secret from mount `'secret'` → `'kv'` and rename
key `"kv"` → `"data"`.

## Summary Table

|              | Correct (old code)   | Scenario 1 (partial bug)   | Scenario 2 (full bug)   |
|--------------|----------------------|----------------------------|-------------------------|
| Mount point  | `kv`                 | `kv` ✅                     | `secret` ❌              |
| API path     | `/v1/kv/data/...`    | `/v1/kv/data/...`          | `/v1/secret/data/...`   |
| Key in body  | `"data"`             | `"kv"` ❌                   | `"kv"` ❌                |
| Patch action | None                 | Rename key                 | Move mount + rename key |

## Prerequisites

```bash
pip install hvac==2.1.0
```

## Quick Fix (Single Command)

```bash
# Dry run — see what would change, no modifications
python vault_patch.py --list_incorrect --fix_incorrect --scan_all_mounts --delete_source --dry_run --vault_addr http://127.0.0.1:8200 --vault_token root

# Apply — fix everything (both scenarios)
python vault_patch.py --list_incorrect --fix_incorrect --scan_all_mounts --delete_source --vault_addr http://127.0.0.1:8200 --vault_token root

# Verify — should report 0 for both scenarios
python vault_patch.py --list_incorrect --scan_all_mounts --vault_addr http://127.0.0.1:8200 --vault_token root
```

The `--scan_all_mounts` flag handles both scenarios in one run:
1. **Scenario 1:** Scans mount `kv` for secrets with wrong key (`"kv"` → `"data"`)
2. **Scenario 2:** Scans mount `secret` for secrets to move to `kv` with correct key

## Step-by-Step Fix

If you prefer to review and fix each scenario separately:

```bash
# 1. List Scenario 1 — wrong key at mount 'kv'
python vault_patch.py --list_incorrect --vault_addr http://127.0.0.1:8200 --vault_token root

# 2. List Scenario 2 — wrong mount 'secret'
python vault_patch.py --list_incorrect --source_mount_point secret --vault_addr http://127.0.0.1:8200 --vault_token root

# 3. Fix Scenario 1 — rename key at mount 'kv'
python vault_patch.py --list_incorrect --fix_incorrect --vault_addr http://127.0.0.1:8200 --vault_token root

# 4. Verify Scenario 1 — should be 0
python vault_patch.py --list_incorrect --vault_addr http://127.0.0.1:8200 --vault_token root

# 5. Fix Scenario 2 — move from 'secret' to 'kv'
python vault_patch.py --list_incorrect --fix_incorrect --source_mount_point secret --delete_source --vault_addr http://127.0.0.1:8200 --vault_token root

# 6. Verify Scenario 2 — should be 0
python vault_patch.py --list_incorrect --source_mount_point secret --vault_addr http://127.0.0.1:8200 --vault_token root
```

## Full Test Flow (with test data)

```bash
# 1. Start Vault dev server
vault server -dev -dev-root-token-id=root

# 2. Create test data (10 correct + 8 Scenario 1 + 6 Scenario 2)
python vault_test_data.py --vault_addr http://127.0.0.1:8200 --vault_token root

# 3. Dry run — preview all changes
python vault_patch.py --list_incorrect --fix_incorrect --scan_all_mounts --delete_source --dry_run --vault_addr http://127.0.0.1:8200 --vault_token root

# 4. Apply — fix all 14 incorrect secrets
python vault_patch.py --list_incorrect --fix_incorrect --scan_all_mounts --delete_source --vault_addr http://127.0.0.1:8200 --vault_token root

# 5. Verify — both scenarios should show 0
python vault_patch.py --list_incorrect --scan_all_mounts --vault_addr http://127.0.0.1:8200 --vault_token root

# 6. Cleanup test data
python vault_test_data.py --cleanup --vault_addr http://127.0.0.1:8200 --vault_token root
```

## Safety Features

| Feature        | Description                                                                                    |
|----------------|------------------------------------------------------------------------------------------------|
| `--dry_run`    | Shows what would change without modifying anything                                             |
| Skip existing  | Scenario 2 skips secrets that already exist at target with correct key                         |
| Skip ambiguous | Scenario 1 skips secrets that have BOTH `"kv"` and `"data"` keys                               |
| Keep source    | Scenario 2 keeps source as backup unless `--delete_source` is specified                        |
| Race guard     | Double-checks target before writing (guards against concurrent changes)                        |
| Cleanup aware  | `vault_test_data.py --cleanup` removes secrets from both original and post-migration locations |

## Flags Reference

| Flag                   | Description                                                                          |
|------------------------|--------------------------------------------------------------------------------------|
| `--list_incorrect`     | List all secrets that need migration                                                 |
| `--fix_incorrect`      | Migrate all incorrect secrets to correct location                                    |
| `--scan_all_mounts`    | Handle both Scenario 1 and 2 in one run                                              |
| `--dry_run`            | Preview changes without applying                                                     |
| `--source_mount_point` | Source mount to scan (default: same as target, or `secret` with `--scan_all_mounts`) |
| `--target_mount_point` | Target (correct) mount point (default: `kv`)                                         |
| `--delete_source`      | Delete source after Scenario 2 migration                                             |
| `--incorrect_key`      | The wrong key in JSON body to look for (default: `kv`)                               |
| `--correct_key`        | The correct key in JSON body to migrate to (default: `data`)                         |
| `--path_prefix`        | Only scan secrets under this prefix                                                  |
| `--vault_addr`         | Vault server URL                                                                     |
| `--vault_token`        | Vault authentication token                                                           |

## Environment Variables

| Variable                            | Purpose                            |
|-------------------------------------|------------------------------------|
| `MODULAR_CLI_SDK_VAULT_ADDR`        | Vault URL (preferred)              |
| `MODULAR_CLI_SDK_VAULT_TOKEN`       | Vault token (preferred)            |
| `MODULAR_CLI_VAULT_ADDR`            | Vault URL (deprecated, fallback)   |
| `MODULAR_CLI_VAULT_TOKEN`           | Vault token (deprecated, fallback) |
| `MODULAR_CLI_SDK_VAULT_MOUNT_POINT` | Default target mount point         |
| `MODULAR_CLI_SDK_VAULT_PATH_PREFIX` | Default path prefix                |
