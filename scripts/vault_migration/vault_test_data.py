#!/usr/bin/env python3
"""
Vault Test Data Generator

Creates test secrets in Vault for testing vault_patch.py.

This simulates three states that exist after the v3.1.1-v3.1.3 bug:

  1. Correct secrets (10):
     Mount: kv     Key: data
     These were created by the old (correct) code or already fixed.
     The patch should NOT touch these.

  2. Scenario 1 — Wrong key, correct mount (8):
     Mount: kv     Key: kv  (wrong!)
     The mount_point was overridden back to 'kv' in some environments,
     but the key was still wrong ('kv' instead of 'data').

     Vault stores:
       API:  /v1/kv/data/{path}
       Body: { "kv": { ...values... } }    ← wrong key in body
                ^^^^
                should be "data"

  3. Scenario 2 — Wrong mount + wrong key (6):
     Mount: secret  Key: kv  (both wrong!)
     Both mount_point and key were affected by the bug.

     Vault stores:
       API:  /v1/secret/data/{path}
       Body: { "kv": { ...values... } }    ← wrong key + wrong mount
              ^^^^
              should be at /v1/kv/data/{path} with key "data"

  Note: The "data" in the API path /v1/kv/data/... is a fixed Vault
  KV v2 route segment. It is NOT the same as the key "data" inside
  the JSON body. They share the same name by coincidence.

Usage:
    python vault_test_data.py                  # Create test data
    python vault_test_data.py --cleanup        # Delete all test data
"""

import argparse
import os
import sys

try:
    import hvac
except ImportError:
    print('Error: hvac is required. Install with: pip install hvac==2.1.0')
    sys.exit(1)


CORRECT_MOUNT = 'kv'
INCORRECT_MOUNT = 'secret'
CORRECT_KEY = 'data'
INCORRECT_KEY = 'kv'

# ─────────────────────────────────────────────────────────────────────
#  10 correct secrets: mount='kv', key='data'
#
#  These simulate secrets created by the old (correct) code.
#  The patch should NOT modify these.
#
#  Vault structure:
#    API:  PUT /v1/kv/data/{path}
#    Body: { "data": { "api_url": "...", ... } }
#                      ^^^^^^
#                      correct key
# ─────────────────────────────────────────────────────────────────────
CORRECT_SECRETS = [
    {
        'path': 'modular-api.tool-alpha.admin.configuration',
        'value': {'api_url': 'https://alpha.example.com', 'port': 8443},
    },
    {
        'path': 'modular-api.tool-alpha.user1.configuration',
        'value': {'api_url': 'https://alpha.example.com', 'token': 'abc123'},
    },
    {
        'path': 'modular-api.tool-beta.admin.configuration',
        'value': {'api_url': 'https://beta.example.com', 'port': 9443},
    },
    {
        'path': 'modular-api.tool-beta.operator.configuration',
        'value': {'api_url': 'https://beta.example.com', 'role': 'operator'},
    },
    {
        'path': 'modular-api.tool-gamma.admin.configuration',
        'value': {'api_url': 'https://gamma.example.com', 'version': '2.0'},
    },
    {
        'path': 'modular-api.tool-delta.admin.configuration',
        'value': {'region': 'us-east-1', 'account': '123456789012'},
    },
    {
        'path': 'modular-api.tool-delta.readonly.configuration',
        'value': {'region': 'us-east-1', 'access': 'readonly'},
    },
    {
        'path': 'modular-api.tool-epsilon.admin.configuration',
        'value': {'endpoint': 'https://eps.internal', 'timeout': 30},
    },
    {
        'path': 'modular-api.tool-zeta.admin.configuration',
        'value': {'cluster': 'prod-01', 'namespace': 'default'},
    },
    {
        'path': 'modular-api.tool-zeta.deployer.configuration',
        'value': {'cluster': 'prod-01', 'namespace': 'deploy', 'role': 'admin'},
    },
]

# ─────────────────────────────────────────────────────────────────────
#  8 incorrect secrets: mount='kv', key='kv' (Scenario 1)
#
#  Wrong key only. The mount was overridden back to 'kv' but the
#  key was still wrong ('kv' instead of 'data').
#
#  Vault structure:
#    API:  PUT /v1/kv/data/{path}
#    Body: { "kv": { "token": "...", ... } }
#             ^^^^
#             wrong key (should be "data")
#
#  Patch fix: rename key "kv" → "data" at mount 'kv'
# ─────────────────────────────────────────────────────────────────────
INCORRECT_SAME_MOUNT = [
    {
        'path': 'modular-api.tool-alpha.user2.configuration',
        'value': {'api_url': 'https://alpha.example.com', 'token': 'def456'},
    },
    {
        'path': 'modular-api.tool-alpha.user3.configuration',
        'value': {'api_url': 'https://alpha.example.com', 'token': 'ghi789'},
    },
    {
        'path': 'modular-api.tool-beta.user1.configuration',
        'value': {'api_url': 'https://beta.example.com', 'token': 'beta-t1'},
    },
    {
        'path': 'modular-api.tool-beta.user2.configuration',
        'value': {'api_url': 'https://beta.example.com', 'token': 'beta-t2'},
    },
    {
        'path': 'modular-api.tool-gamma.user1.configuration',
        'value': {'api_url': 'https://gamma.example.com', 'key': 'gamma-k1'},
    },
    {
        'path': 'modular-api.tool-delta.user1.configuration',
        'value': {'region': 'eu-west-1', 'account': '987654321098'},
    },
    {
        'path': 'modular-api.tool-epsilon.user1.configuration',
        'value': {'endpoint': 'https://eps.internal', 'key': 'eps-u1'},
    },
    {
        'path': 'modular-api.tool-zeta.user1.configuration',
        'value': {'cluster': 'prod-01', 'token': 'zeta-u1'},
    },
]

# ─────────────────────────────────────────────────────────────────────
#  6 incorrect secrets: mount='secret', key='kv' (Scenario 2)
#
#  Both mount and key are wrong. This is the full v3.1.1 bug where
#  mount_point became 'secret' and key became 'kv'.
#
#  Vault structure:
#    API:  PUT /v1/secret/data/{path}
#    Body: { "kv": { "token": "...", ... } }
#             ^^^^
#             wrong key at wrong mount
#
#  Patch fix: move from mount 'secret' → 'kv'
#             and rename key "kv" → "data"
# ─────────────────────────────────────────────────────────────────────
INCORRECT_CROSS_MOUNT = [
    {
        'path': 'modular-api.tool-beta.user3.configuration',
        'value': {'api_url': 'https://beta.example.com', 'token': 'beta-t3'},
    },
    {
        'path': 'modular-api.tool-gamma.user2.configuration',
        'value': {'api_url': 'https://gamma.example.com', 'key': 'gamma-k2'},
    },
    {
        'path': 'modular-api.tool-delta.user2.configuration',
        'value': {'region': 'ap-south-1', 'account': '111222333444'},
    },
    {
        'path': 'modular-api.tool-epsilon.user2.configuration',
        'value': {'endpoint': 'https://eps.internal', 'key': 'eps-u2'},
    },
    {
        'path': 'modular-api.tool-epsilon.user3.configuration',
        'value': {'endpoint': 'https://eps.internal', 'key': 'eps-u3'},
    },
    {
        'path': 'modular-api.tool-zeta.user2.configuration',
        'value': {'cluster': 'prod-01', 'token': 'zeta-u2'},
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            'Vault Test Data Generator\n'
            '\n'
            'Creates test secrets to simulate the v3.1.1-v3.1.3 bug:\n'
            f'  - {len(CORRECT_SECRETS)} correct secrets   '
            f'(mount={CORRECT_MOUNT!r}, key={CORRECT_KEY!r})\n'
            f'  - {len(INCORRECT_SAME_MOUNT)} Scenario 1     '
            f'(mount={CORRECT_MOUNT!r}, key={INCORRECT_KEY!r}) '
            f'← wrong key\n'
            f'  - {len(INCORRECT_CROSS_MOUNT)} Scenario 2     '
            f'(mount={INCORRECT_MOUNT!r}, key={INCORRECT_KEY!r}) '
            f'← wrong mount + key'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        '--vault_addr',
        default=(
            os.getenv('MODULAR_CLI_SDK_VAULT_ADDR')
            or os.getenv('MODULAR_CLI_VAULT_ADDR')
            or 'http://127.0.0.1:8200'
        ),
        help='Vault server URL (default: http://127.0.0.1:8200)',
    )
    parser.add_argument(
        '--vault_token',
        default=(
            os.getenv('MODULAR_CLI_SDK_VAULT_TOKEN')
            or os.getenv('MODULAR_CLI_VAULT_TOKEN')
            or 'root'
        ),
        help='Vault token (default: root)',
    )
    parser.add_argument(
        '--cleanup',
        action='store_true',
        help='Delete all test secrets instead of creating them',
    )
    return parser.parse_args()


def ensure_mount_point(client: hvac.Client, mount_point: str) -> None:
    """Enable KV v2 secrets engine if not already enabled."""
    mounted = client.sys.list_mounted_secrets_engines()
    if f'{mount_point}/' in mounted:
        print(f'  Mount point {mount_point!r} already enabled')
        return

    print(f'  Enabling KV v2 at {mount_point!r}...')
    try:
        client.sys.enable_secrets_engine(
            backend_type='kv',
            path=mount_point,
            options={'version': '2'},
        )
        print(f'  Mount point {mount_point!r} enabled')
    except Exception as e:
        print(f'  Failed to enable {mount_point!r}: {e}')
        sys.exit(1)


def create_secrets(
        client: hvac.Client,
        mount_point: str,
        key: str,
        secrets: list,
        label: str,
) -> None:
    """
    Create secrets at the given mount point with the given key.

    Each secret is stored as:
        API:  PUT /v1/{mount_point}/data/{path}
        Body: { "{key}": { ...values... } }
    """
    print()
    print(
        f'Creating {len(secrets)} {label}...'
    )
    print(
        f'  mount={mount_point!r}  key={key!r}  '
        f'(API: /v1/{mount_point}/data/{{path}})'
    )
    print('-' * 60)

    for secret in secrets:
        path = secret['path']
        try:
            client.secrets.kv.v2.create_or_update_secret(
                path=path,
                secret={key: secret['value']},
                mount_point=mount_point,
            )
            print(
                f'  CREATED: [{mount_point}] {path}'
                f'  body={{ {key!r}: ... }}'
            )
        except Exception as e:
            print(f'  FAILED:  [{mount_point}] {path}: {e}')


def delete_secrets(
        client: hvac.Client,
        mount_point: str,
        secrets: list,
        label: str = '',
) -> None:
    """Delete secrets from the given mount point."""
    if label:
        print(f'\n  {label}')
    for secret in secrets:
        path = secret['path']
        try:
            client.secrets.kv.v2.delete_metadata_and_all_versions(
                path=path,
                mount_point=mount_point,
            )
            print(f'  DELETED: [{mount_point}] {path}')
        except Exception as e:
            print(f'  SKIP:    [{mount_point}] {path}: {e}')


def verify_test_data(client: hvac.Client) -> None:
    """Verify and summarize created secrets."""
    groups = [
        (CORRECT_MOUNT, CORRECT_KEY, CORRECT_SECRETS,
         'correct (should not be touched)'),
        (CORRECT_MOUNT, INCORRECT_KEY, INCORRECT_SAME_MOUNT,
         'Scenario 1 (wrong key)'),
        (INCORRECT_MOUNT, INCORRECT_KEY, INCORRECT_CROSS_MOUNT,
         'Scenario 2 (wrong mount + key)'),
    ]

    print()
    print('Verifying...')
    print('-' * 60)

    total_ok = 0
    total_expected = 0
    total_errors = 0

    for mount, key, secrets, label in groups:
        ok = 0
        for secret in secrets:
            path = secret['path']
            try:
                response = client.secrets.kv.v2.read_secret_version(
                    path=path,
                    mount_point=mount,
                )
                data = response.get('data', {}).get('data', {})
                if key in data:
                    ok += 1
                else:
                    print(
                        f'  UNEXPECTED: [{mount}] {path} '
                        f'missing key {key!r} in body'
                    )
                    total_errors += 1
            except Exception as e:
                print(f'  ERROR: [{mount}] {path}: {e}')
                total_errors += 1

        total_ok += ok
        total_expected += len(secrets)
        print(f'  {label}: {ok}/{len(secrets)}')

    print()
    print('=' * 60)
    print('  Summary')
    print('=' * 60)
    print()
    print('  Vault KV v2 structure reminder:')
    print('    API path:  /v1/{mount}/data/{secret_path}')
    print('                           ^^^^')
    print('                           fixed route, NOT your key')
    print('    JSON body: { "{your_key}": { ...values... } }')
    print()
    print(
        f'  ✅ Correct   [{CORRECT_MOUNT}] '
        f'body key={CORRECT_KEY!r}:     '
        f'{len(CORRECT_SECRETS)} secrets'
    )
    print(
        f'  ❌ Scenario 1 [{CORRECT_MOUNT}] '
        f'body key={INCORRECT_KEY!r}:      '
        f'{len(INCORRECT_SAME_MOUNT)} secrets  '
        f'(wrong key)'
    )
    print(
        f'  ❌ Scenario 2 [{INCORRECT_MOUNT}] '
        f'body key={INCORRECT_KEY!r}:   '
        f'{len(INCORRECT_CROSS_MOUNT)} secrets  '
        f'(wrong mount + key)'
    )
    print(
        f'  Total verified: {total_ok}/{total_expected}'
    )
    if total_errors:
        print(f'  Errors: {total_errors}')

    print()
    print('  What the patch will do:')
    print()
    print(
        f'    Scenario 1: [{CORRECT_MOUNT}] '
        f'body {{ {INCORRECT_KEY!r}: ... }} -> '
        f'body {{ {CORRECT_KEY!r}: ... }}'
    )
    print(f'                (rename key, same mount)')
    print()
    print(
        f'    Scenario 2: [{INCORRECT_MOUNT}] '
        f'body {{ {INCORRECT_KEY!r}: ... }} -> '
        f'[{CORRECT_MOUNT}] '
        f'body {{ {CORRECT_KEY!r}: ... }}'
    )
    print(f'                (move mount + rename key)')


def main():
    args = parse_args()

    print('=' * 60)
    print('  Vault Test Data Generator')
    print('=' * 60)
    print()
    print(f'  Vault address: {args.vault_addr}')
    print(f'  Mode:          {"CLEANUP" if args.cleanup else "CREATE"}')

    client = hvac.Client(url=args.vault_addr, token=args.vault_token)
    if not client.is_authenticated():
        print('\nError: Vault authentication failed')
        sys.exit(1)
    print('  Connected to Vault successfully')

    if args.cleanup:
        print()
        print('Deleting all test secrets...')
        print('-' * 60)

        # Delete from original locations
        delete_secrets(
            client, CORRECT_MOUNT, CORRECT_SECRETS,
            'Correct secrets (original location):',
        )
        delete_secrets(
            client, CORRECT_MOUNT, INCORRECT_SAME_MOUNT,
            'Scenario 1 secrets (original location at wrong key):',
        )
        delete_secrets(
            client, INCORRECT_MOUNT, INCORRECT_CROSS_MOUNT,
            'Scenario 2 secrets (original location at wrong mount):',
        )

        # Delete cross-mount secrets from target mount point
        # (where they end up after migration by vault_patch.py)
        delete_secrets(
            client, CORRECT_MOUNT, INCORRECT_CROSS_MOUNT,
            'Scenario 2 secrets (post-migration location at correct mount):',
        )

        print()
        print('Cleanup complete.')
    else:
        print()
        print('Ensuring mount points...')
        ensure_mount_point(client, CORRECT_MOUNT)
        ensure_mount_point(client, INCORRECT_MOUNT)

        create_secrets(
            client, CORRECT_MOUNT, CORRECT_KEY,
            CORRECT_SECRETS,
            'correct secrets (should not be touched by patch)',
        )
        create_secrets(
            client, CORRECT_MOUNT, INCORRECT_KEY,
            INCORRECT_SAME_MOUNT,
            'Scenario 1 secrets (wrong key at correct mount)',
        )
        create_secrets(
            client, INCORRECT_MOUNT, INCORRECT_KEY,
            INCORRECT_CROSS_MOUNT,
            'Scenario 2 secrets (wrong mount + wrong key)',
        )

        verify_test_data(client)

        addr = args.vault_addr
        token = args.vault_token

        print()
        print('=' * 60)
        print('  Test commands')
        print('=' * 60)
        print()
        print('  ┌─────────────────────────────────────────────────┐')
        print('  │  Option A: Fix everything in one command        │')
        print('  └─────────────────────────────────────────────────┘')
        print()
        print('  # Dry run (preview, no changes):')
        print(f'  python vault_patch.py --list_incorrect --fix_incorrect'
              f' --scan_all_mounts --delete_source --dry_run'
              f' --vault_addr {addr} --vault_token {token}')
        print()
        print('  # Apply (fix all):')
        print(f'  python vault_patch.py --list_incorrect --fix_incorrect'
              f' --scan_all_mounts --delete_source'
              f' --vault_addr {addr} --vault_token {token}')
        print()
        print('  # Verify (should show 0 for both scenarios):')
        print(f'  python vault_patch.py --list_incorrect'
              f' --scan_all_mounts'
              f' --vault_addr {addr} --vault_token {token}')
        print()
        print('  ┌─────────────────────────────────────────────────┐')
        print('  │  Option B: Step-by-step                         │')
        print('  └─────────────────────────────────────────────────┘')
        print()
        print(f'  # B1. List Scenario 1 — wrong key at [{CORRECT_MOUNT}]'
              f' (expect {len(INCORRECT_SAME_MOUNT)})')
        print(f'  python vault_patch.py --list_incorrect'
              f' --vault_addr {addr} --vault_token {token}')
        print()
        print(f'  # B2. List Scenario 2 — wrong mount [{INCORRECT_MOUNT}]'
              f' (expect {len(INCORRECT_CROSS_MOUNT)})')
        print(f'  python vault_patch.py --list_incorrect'
              f' --source_mount_point {INCORRECT_MOUNT}'
              f' --vault_addr {addr} --vault_token {token}')
        print()
        print(f'  # B3. Fix Scenario 1 — rename key at [{CORRECT_MOUNT}]')
        print(f'  python vault_patch.py --list_incorrect --fix_incorrect'
              f' --vault_addr {addr} --vault_token {token}')
        print()
        print(f'  # B4. Verify Scenario 1 — should be 0')
        print(f'  python vault_patch.py --list_incorrect'
              f' --vault_addr {addr} --vault_token {token}')
        print()
        print(f'  # B5. Fix Scenario 2 — move [{INCORRECT_MOUNT}] -> '
              f'[{CORRECT_MOUNT}]')
        print(f'  python vault_patch.py --list_incorrect --fix_incorrect'
              f' --source_mount_point {INCORRECT_MOUNT} --delete_source'
              f' --vault_addr {addr} --vault_token {token}')
        print()
        print(f'  # B6. Verify Scenario 2 — should be 0')
        print(f'  python vault_patch.py --list_incorrect'
              f' --source_mount_point {INCORRECT_MOUNT}'
              f' --vault_addr {addr} --vault_token {token}')
        print()
        print('  ┌─────────────────────────────────────────────────┐')
        print('  │  Cleanup                                        │')
        print('  └─────────────────────────────────────────────────┘')
        print()
        print(f'  python vault_test_data.py --cleanup'
              f' --vault_addr {addr} --vault_token {token}')

    print()
    print('Done.')


if __name__ == '__main__':
    main()
