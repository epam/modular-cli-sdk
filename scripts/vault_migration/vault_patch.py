#!/usr/bin/env python3
"""
Vault Secret Migration Patch

Migrates secrets from incorrect location (introduced in v3.1.1-v3.1.3)
back to the correct location (original behavior).

Background:
    Vault KV v2 stores secrets at:
        API:  /v1/{mount_point}/data/{secret_path}
        Body: { "{key}": { ...values... } }

    The old (correct) code used:
        mount_point = 'kv'
        key         = 'data'

    Buggy versions (v3.1.1-v3.1.3) used:
        mount_point = 'secret'  (wrong — this is Vault's default mount)
        key         = 'kv'      (wrong — swapped with mount_point value)

    This resulted in two failure scenarios:

    Scenario 1 — Wrong key, correct mount:
        Some environments had mount_point overridden back to 'kv',
        but the key was still wrong ('kv' instead of 'data').

        BEFORE (broken):
            Mount: kv    Path: my-app.config
            Stored: { "kv": {"api_url": "...", "token": "..."} }
                      ^^^^
                      wrong key (should be "data")

        AFTER (fixed):
            Mount: kv    Path: my-app.config
            Stored: { "data": {"api_url": "...", "token": "..."} }
                      ^^^^^^
                      correct key

    Scenario 2 — Wrong mount + wrong key:
        Both mount_point and key were wrong.

        BEFORE (broken):
            Mount: secret    Path: my-app.config
            Stored: { "kv": {"api_url": "...", "token": "..."} }
                      ^^^^
                      wrong key at wrong mount point

        AFTER (fixed):
            Mount: kv        Path: my-app.config
            Stored: { "data": {"api_url": "...", "token": "..."} }
                      ^^^^^^
                      correct key at correct mount point

    Note: The "data" in the API path /v1/kv/data/... is a fixed
    Vault KV v2 API route segment. It is NOT related to the secret
    key "data" used inside the JSON body. They just happen to share
    the same name, which can be confusing.

    Full Vault KV v2 read response structure:
        response
          └─ "data"              ← Vault API envelope (always "data")
              ├─ "data"          ← Vault KV v2 versioning (always "data")
              │   └─ "{key}"     ← YOUR key ("data" correct, "kv" buggy)
              │       └─ {...}   ← your actual secret values
              └─ "metadata"
                  └─ version, created_time, etc.

Usage:
    # List and fix everything in one command:
    python vault_patch.py --list_incorrect --fix_incorrect \\
        --scan_all_mounts --delete_source --dry_run

    # List only (same mount, wrong key):
    python vault_patch.py --list_incorrect

    # List only (wrong mount + wrong key):
    python vault_patch.py --list_incorrect --source_mount_point secret

    # Fix same mount only:
    python vault_patch.py --fix_incorrect

    # Fix cross mount only:
    python vault_patch.py --fix_incorrect --source_mount_point secret

    # Fix everything:
    python vault_patch.py --fix_incorrect --scan_all_mounts --delete_source
"""

import argparse
import os
import sys
from typing import Any, Dict, List, Tuple

try:
    import hvac
except ImportError:
    print('Error: hvac is required. Install with: pip install hvac==2.1.0')
    sys.exit(1)


# ─────────────────────────────────────────────────────────────────────
#  Scenario descriptions (used in output messages)
# ─────────────────────────────────────────────────────────────────────

SCENARIO_1_TITLE = 'Scenario 1: Wrong key at correct mount point'
SCENARIO_1_DESC = (
    'Secrets stored at the correct mount point but with the wrong\n'
    '  key inside the JSON body.\n'
    '\n'
    '  Example:\n'
    '    Mount: kv    Path: my-app.config\n'
    '    BEFORE: {{ "kv":   {{"token": "..."}} }}  ← wrong key\n'
    '    AFTER:  {{ "data": {{"token": "..."}} }}  ← correct key\n'
    '\n'
    '  Fix: Rename key "{incorrect}" → "{correct}" '
    'within the same mount point.'
)

SCENARIO_2_TITLE = 'Scenario 2: Wrong mount point + wrong key'
SCENARIO_2_DESC = (
    'Secrets stored at the wrong mount point AND with the wrong\n'
    '  key inside the JSON body.\n'
    '\n'
    '  Example:\n'
    '    BEFORE: Mount: secret  Path: my-app.config\n'
    '            {{ "kv":   {{"token": "..."}} }}  ← wrong key + mount\n'
    '    AFTER:  Mount: kv      Path: my-app.config\n'
    '            {{ "data": {{"token": "..."}} }}  ← correct key + mount\n'
    '\n'
    '  Fix: Move secret from "{source}" → "{target}" mount point\n'
    '       and rename key "{incorrect}" → "{correct}".'
)


def format_scenario_desc(
        template: str,
        incorrect: str,
        correct: str,
        source: str = '',
        target: str = '',
) -> str:
    """Format a scenario description with actual key/mount values."""
    return template.format(
        incorrect=incorrect,
        correct=correct,
        source=source,
        target=target,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            'Vault Secret Migration Patch\n'
            '\n'
            'Migrates secrets from incorrect location (v3.1.1-v3.1.3 bug)\n'
            'to the correct location.\n'
            '\n'
            'Two scenarios are handled:\n'
            '\n'
            '  Scenario 1 — Wrong key, correct mount:\n'
            '    Mount: kv (correct)\n'
            '    Key:   "kv" (wrong) → "data" (correct)\n'
            '    Fix:   Rename key within the same mount point.\n'
            '\n'
            '  Scenario 2 — Wrong mount + wrong key:\n'
            '    Mount: "secret" (wrong) → "kv" (correct)\n'
            '    Key:   "kv" (wrong) → "data" (correct)\n'
            '    Fix:   Move to correct mount + rename key.\n'
            '\n'
            'Note: "data" in the Vault API path /v1/kv/data/... is a\n'
            'fixed KV v2 route segment, NOT the secret key. The key\n'
            '"data" lives inside the JSON body. They share the same\n'
            'name by coincidence.'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            'Examples:\n'
            '\n'
            '  # Fix everything in one command (dry run first):\n'
            '  python vault_patch.py --list_incorrect --fix_incorrect \\\n'
            '      --scan_all_mounts --delete_source --dry_run\n'
            '\n'
            '  # Then apply:\n'
            '  python vault_patch.py --list_incorrect --fix_incorrect \\\n'
            '      --scan_all_mounts --delete_source\n'
            '\n'
            '  # Scenario 1 only (wrong key at mount "kv"):\n'
            '  python vault_patch.py --list_incorrect --fix_incorrect\n'
            '\n'
            '  # Scenario 2 only (wrong mount "secret" + wrong key):\n'
            '  python vault_patch.py --list_incorrect --fix_incorrect \\\n'
            '      --source_mount_point secret --delete_source\n'
        ),
    )

    parser.add_argument(
        '--list_incorrect',
        action='store_true',
        help='List all secrets that need migration',
    )
    parser.add_argument(
        '--fix_incorrect',
        action='store_true',
        help='Migrate all incorrect secrets to correct location',
    )
    parser.add_argument(
        '--dry_run',
        action='store_true',
        help='Show what would be fixed without making changes',
    )

    vault_group = parser.add_argument_group('Vault connection')
    vault_group.add_argument(
        '--vault_addr',
        default=(
            os.getenv('MODULAR_CLI_SDK_VAULT_ADDR')
            or os.getenv('MODULAR_CLI_VAULT_ADDR')
            or 'http://127.0.0.1:8200'
        ),
        help='Vault server URL (default: from environment)',
    )
    vault_group.add_argument(
        '--vault_token',
        default=(
            os.getenv('MODULAR_CLI_SDK_VAULT_TOKEN')
            or os.getenv('MODULAR_CLI_VAULT_TOKEN')
            or 'root'
        ),
        help='Vault token (default: from environment)',
    )

    scan_group = parser.add_argument_group('Migration configuration')
    scan_group.add_argument(
        '--source_mount_point',
        default=None,
        help=(
            'Source mount point to scan for incorrect secrets. '
            'If different from --target_mount_point, triggers '
            'Scenario 2 (cross-mount migration). '
            '(default: same as target for Scenario 1, '
            'or "secret" with --scan_all_mounts)'
        ),
    )
    scan_group.add_argument(
        '--target_mount_point',
        default=os.getenv('MODULAR_CLI_SDK_VAULT_MOUNT_POINT', 'kv'),
        help='Target (correct) mount point (default: kv)',
    )
    scan_group.add_argument(
        '--scan_all_mounts',
        action='store_true',
        help=(
            'Scan both scenarios in a single run: '
            'Scenario 1 (wrong key at target mount) and '
            'Scenario 2 (wrong mount + wrong key at source mount). '
            'Source mount defaults to "secret" or set via '
            '--source_mount_point.'
        ),
    )
    scan_group.add_argument(
        '--path_prefix',
        default=os.getenv('MODULAR_CLI_SDK_VAULT_PATH_PREFIX', ''),
        help='Path prefix to scan (default: root level)',
    )
    scan_group.add_argument(
        '--incorrect_key',
        default='kv',
        help=(
            'The incorrect secret key to look for inside the JSON body '
            '(default: kv)'
        ),
    )
    scan_group.add_argument(
        '--correct_key',
        default='data',
        help=(
            'The correct secret key to migrate to inside the JSON body '
            '(default: data)'
        ),
    )
    scan_group.add_argument(
        '--delete_source',
        action='store_true',
        help=(
            'Delete source secret after Scenario 2 (cross-mount) migration. '
            'Only applies when source != target mount point. '
            '(default: keep source as backup)'
        ),
    )

    args = parser.parse_args()

    # Default source = target (same mount point migration)
    if args.source_mount_point is None:
        if args.scan_all_mounts:
            args.source_mount_point = 'secret'
        else:
            args.source_mount_point = args.target_mount_point

    if not args.list_incorrect and not args.fix_incorrect:
        parser.error(
            'At least one of --list_incorrect or --fix_incorrect is required'
        )
    if not args.vault_addr:
        parser.error(
            'Vault address not configured. '
            'Use --vault_addr or set MODULAR_CLI_SDK_VAULT_ADDR'
        )
    if not args.vault_token:
        parser.error(
            'Vault token not configured. '
            'Use --vault_token or set MODULAR_CLI_SDK_VAULT_TOKEN'
        )
    if (not args.scan_all_mounts
            and args.incorrect_key == args.correct_key
            and args.source_mount_point == args.target_mount_point):
        parser.error(
            'Nothing to migrate: source and target mount points are the same '
            'and incorrect/correct keys are the same.'
        )

    return args


def create_client(addr: str, token: str) -> hvac.Client:
    client = hvac.Client(url=addr, token=token)
    if not client.is_authenticated():
        print('Error: Vault authentication failed. Check address and token.')
        sys.exit(1)
    return client


def mount_point_exists(client: hvac.Client, mount_point: str) -> bool:
    """Check if a mount point is enabled."""
    try:
        mounted = client.sys.list_mounted_secrets_engines()
        return f'{mount_point}/' in mounted
    except Exception:
        return False


def list_all_secrets(
        client: hvac.Client,
        mount_point: str,
        path: str = '',
) -> List[str]:
    """Recursively list all secret paths under the given path."""
    secrets = []
    try:
        response = client.secrets.kv.v2.list_secrets(
            path=path,
            mount_point=mount_point,
        )
        keys = response.get('data', {}).get('keys', [])
    except Exception:
        return secrets

    for key in keys:
        full_path = f'{path}{key}' if path else key
        if key.endswith('/'):
            secrets.extend(
                list_all_secrets(client, mount_point, full_path)
            )
        else:
            secrets.append(full_path)

    return secrets


def read_secret_data(
        client: hvac.Client,
        mount_point: str,
        path: str,
) -> Dict[str, Any]:
    """
    Read secret data from Vault.

    Returns the inner data dict (the JSON body keys), or empty dict.

    Vault KV v2 response structure:
        response['data']['data'] = { "{your_key}": { ...values... } }
                  ^^^^^^  ^^^^^^
                  Vault    Vault
                  API      versioning
                  envelope wrapper
    """
    try:
        response = client.secrets.kv.v2.read_secret_version(
            path=path,
            mount_point=mount_point,
        )
        return response.get('data', {}).get('data', {})
    except Exception:
        return {}


def find_incorrect_secrets(
        client: hvac.Client,
        source_mount_point: str,
        target_mount_point: str,
        path_prefix: str,
        incorrect_key: str,
        correct_key: str,
        scenario_label: str = '',
) -> List[Dict[str, Any]]:
    """
    Find secrets that need migration.

    Scenario 1 — Same mount point (source == target):
        Finds secrets that have the incorrect_key but NOT the correct_key
        in their JSON body. These need a key rename only.

        Example of what we look for:
            Mount: kv    Path: my-app.config
            Body: { "kv": {"token": "..."} }
                    ^^^^
                    has incorrect_key="kv", missing correct_key="data"

    Scenario 2 — Cross mount point (source != target):
        Finds secrets at the source mount point that have the
        incorrect_key. These need to be moved to the target mount
        point with the correct_key.

        Skips secrets that already exist at the target mount point
        with the correct_key (already migrated or correct).

        Example of what we look for:
            Source mount: secret    Path: my-app.config
            Body: { "kv": {"token": "..."} }
                    ^^^^
                    has incorrect_key="kv" at wrong mount
    """
    cross_mount = source_mount_point != target_mount_point

    all_paths = list_all_secrets(client, source_mount_point, path_prefix)
    print(f'  Secrets scanned at {source_mount_point!r}: {len(all_paths)}')

    incorrect = []
    skipped_both = []
    skipped_target_exists = []

    for path in all_paths:
        try:
            response = client.secrets.kv.v2.read_secret_version(
                path=path,
                mount_point=source_mount_point,
            )
            secret_data = response.get('data', {}).get('data', {})
        except Exception as e:
            print(f'  WARNING: could not read {path}: {e}')
            continue

        has_incorrect = incorrect_key in secret_data
        has_correct = correct_key in secret_data

        if cross_mount:
            # Scenario 2: looking for incorrect_key at wrong mount
            if not has_incorrect:
                continue

            # Check if target already has this secret with correct key
            target_data = read_secret_data(
                client, target_mount_point, path,
            )
            if correct_key in target_data:
                skipped_target_exists.append(path)
                continue

            incorrect.append({
                'path': path,
                'value': secret_data[incorrect_key],
                'all_keys': list(secret_data.keys()),
                'source_mount': source_mount_point,
                'cross_mount': True,
                'scenario': 'Scenario 2',
            })
        else:
            # Scenario 1: looking for incorrect_key without correct_key
            if has_incorrect and not has_correct:
                incorrect.append({
                    'path': path,
                    'value': secret_data[incorrect_key],
                    'all_keys': list(secret_data.keys()),
                    'source_mount': source_mount_point,
                    'cross_mount': False,
                    'scenario': 'Scenario 1',
                })
            elif has_incorrect and has_correct:
                skipped_both.append(path)

    if skipped_both:
        print()
        print(
            f'  WARNING: {len(skipped_both)} secret(s) have BOTH '
            f'{incorrect_key!r} and {correct_key!r} keys in their '
            f'JSON body (skipped — ambiguous, manual review needed):'
        )
        for path in skipped_both:
            print(f'    - {path}')

    if skipped_target_exists:
        print()
        print(
            f'  INFO: {len(skipped_target_exists)} secret(s) already exist '
            f'at target mount {target_mount_point!r} with {correct_key!r} '
            f'key (skipped — already migrated or correct):'
        )
        for path in skipped_target_exists:
            print(f'    - {path}')

    return incorrect


def fix_secrets(
        client: hvac.Client,
        target_mount_point: str,
        incorrect_secrets: List[Dict[str, Any]],
        incorrect_key: str,
        correct_key: str,
        delete_source: bool = False,
        dry_run: bool = False,
) -> Tuple[int, int, int]:
    """
    Fix secrets by migrating to the correct location.

    Scenario 1 — Same mount point (cross_mount=False):
        Reads the secret, renames the key in the JSON body, writes back.

        BEFORE: mount=kv  body={ "kv":   {"token": "..."} }
        AFTER:  mount=kv  body={ "data": {"token": "..."} }

    Scenario 2 — Cross mount point (cross_mount=True):
        Creates a new secret at the target mount point with the correct
        key, optionally deletes the source.

        BEFORE: mount=secret  body={ "kv":   {"token": "..."} }
        AFTER:  mount=kv      body={ "data": {"token": "..."} }
                (source at mount=secret deleted if --delete_source)

    Returns (fixed_count, failed_count, skipped_count).
    """
    fixed = 0
    failed = 0
    skipped = 0

    for secret_info in incorrect_secrets:
        path = secret_info['path']
        value = secret_info['value']
        source_mount = secret_info['source_mount']
        cross_mount = secret_info['cross_mount']
        scenario = secret_info['scenario']

        if dry_run:
            if cross_mount:
                action = (
                    f'[{scenario}] '
                    f'{source_mount}:{path} -> '
                    f'{target_mount_point}:{path}'
                )
                action += (
                    f'\n           body: {{ {incorrect_key!r}: ... }} -> '
                    f'{{ {correct_key!r}: ... }}'
                )
                if delete_source:
                    action += '\n           + delete source'
            else:
                action = (
                    f'[{scenario}] '
                    f'[{source_mount}] {path}'
                    f'\n           body: {{ {incorrect_key!r}: ... }} -> '
                    f'{{ {correct_key!r}: ... }}'
                )
            print(f'  [DRY RUN] {action}')
            fixed += 1
            continue

        try:
            if cross_mount:
                # Scenario 2: cross-mount migration

                # Double-check target doesn't exist (race condition guard)
                target_data = read_secret_data(
                    client, target_mount_point, path,
                )
                if correct_key in target_data:
                    print(
                        f'  SKIPPED: [{scenario}] '
                        f'{target_mount_point}:{path} '
                        f'already has {correct_key!r} key in body'
                    )
                    skipped += 1
                    continue

                # Write to target mount point with correct key
                # BEFORE: [secret] body={ "kv": {...} }
                # AFTER:  [kv]     body={ "data": {...} }
                client.secrets.kv.v2.create_or_update_secret(
                    path=path,
                    secret={correct_key: value},
                    mount_point=target_mount_point,
                )

                if delete_source:
                    client.secrets.kv.v2.delete_metadata_and_all_versions(
                        path=path,
                        mount_point=source_mount,
                    )
                    print(
                        f'  MOVED:  [{scenario}] '
                        f'{source_mount}:{path} -> '
                        f'{target_mount_point}:{path} '
                        f'(key {incorrect_key!r} -> {correct_key!r})'
                    )
                else:
                    print(
                        f'  COPIED: [{scenario}] '
                        f'{source_mount}:{path} -> '
                        f'{target_mount_point}:{path} '
                        f'(key {incorrect_key!r} -> {correct_key!r}, '
                        f'source kept)'
                    )
            else:
                # Scenario 1: same-mount key rename

                # Re-read to get current state
                response = client.secrets.kv.v2.read_secret_version(
                    path=path,
                    mount_point=source_mount,
                )
                secret_data = response.get('data', {}).get('data', {})

                # Guard: if correct key appeared since scan
                if correct_key in secret_data:
                    print(
                        f'  SKIPPED: [{scenario}] [{source_mount}] {path} '
                        f'already has {correct_key!r} key in body'
                    )
                    skipped += 1
                    continue

                # Rename key in JSON body
                # BEFORE: body={ "kv": {...} }
                # AFTER:  body={ "data": {...} }
                secret_data[correct_key] = secret_data.pop(incorrect_key)

                client.secrets.kv.v2.create_or_update_secret(
                    path=path,
                    secret=secret_data,
                    mount_point=source_mount,
                )
                print(
                    f'  FIXED:  [{scenario}] [{source_mount}] {path} '
                    f'(key {incorrect_key!r} -> {correct_key!r})'
                )

            fixed += 1
        except Exception as e:
            print(f'  FAILED: [{scenario}] {path}: {e}')
            failed += 1

    return fixed, failed, skipped


def run_scan(
        client: hvac.Client,
        source_mount_point: str,
        target_mount_point: str,
        path_prefix: str,
        incorrect_key: str,
        correct_key: str,
        scenario_title: str,
        scenario_desc: str,
) -> List[Dict[str, Any]]:
    """
    Run a single scan pass and return found incorrect secrets.
    Prints scenario description for context.
    """
    print(f'\n  --- {scenario_title} ---')
    print(f'  {scenario_desc}')
    print()

    if not mount_point_exists(client, source_mount_point):
        print(f'  Mount point {source_mount_point!r} is not enabled. '
              f'Skipping.')
        return []

    return find_incorrect_secrets(
        client=client,
        source_mount_point=source_mount_point,
        target_mount_point=target_mount_point,
        path_prefix=path_prefix,
        incorrect_key=incorrect_key,
        correct_key=correct_key,
        scenario_label=scenario_title,
    )


def print_header(args: argparse.Namespace) -> None:
    """Print the tool header with configuration summary."""
    cross_mount = args.source_mount_point != args.target_mount_point

    print('=' * 64)
    print('  Vault Secret Migration Patch')
    print('=' * 64)
    print()
    print(f'  Vault address:      {args.vault_addr}')
    print(f'  Target mount point: {args.target_mount_point}')

    if args.scan_all_mounts:
        print(f'  Scan mode:          ALL SCENARIOS')
        print(f'  Source mount point: {args.source_mount_point} '
              f'(for Scenario 2)')
        print(f'  Delete source:      {args.delete_source}')
    elif cross_mount:
        print(f'  Scan mode:          Scenario 2 only (cross-mount)')
        print(f'  Source mount point: {args.source_mount_point}')
        print(f'  Delete source:      {args.delete_source}')
    else:
        print(f'  Scan mode:          Scenario 1 only (same mount)')

    print(f'  Path prefix:        {args.path_prefix or "(root)"}')
    print(f'  Incorrect key:      {args.incorrect_key!r} (in JSON body)')
    print(f'  Correct key:        {args.correct_key!r} (in JSON body)')

    if args.dry_run:
        print(f'  Mode:               DRY RUN (no changes)')

    print()
    print('  Vault KV v2 reminder:')
    print('    API path:  /v1/{mount}/data/{secret_path}')
    print('                           ^^^^')
    print('                           fixed API route, NOT your key')
    print('    JSON body: { "{your_key}": { ...values... } }')
    print(f'                 {args.correct_key!r} = correct, '
          f'{args.incorrect_key!r} = buggy')
    print()


def main():
    args = parse_args()
    cross_mount = args.source_mount_point != args.target_mount_point

    print_header(args)

    client = create_client(args.vault_addr, args.vault_token)
    print('Successfully connected to Vault')

    # Normalize prefix
    path_prefix = args.path_prefix.strip('/')
    if path_prefix:
        path_prefix = f'{path_prefix}/'

    # --- Collect all incorrect secrets ---
    all_incorrect: List[Dict[str, Any]] = []

    if args.scan_all_mounts:
        # Validate target mount exists
        if not mount_point_exists(client, args.target_mount_point):
            if args.fix_incorrect and not args.dry_run:
                print(
                    f'\nError: Target mount point '
                    f'{args.target_mount_point!r} is not enabled.'
                )
                sys.exit(1)
            else:
                print(
                    f'\nWARNING: Target mount point '
                    f'{args.target_mount_point!r} is not enabled.'
                )

        print('\nScanning for incorrect secrets...')

        # Pass 1: Scenario 1 — wrong key at correct mount
        s1_desc = format_scenario_desc(
            SCENARIO_1_DESC,
            incorrect=args.incorrect_key,
            correct=args.correct_key,
        )
        same_mount = run_scan(
            client=client,
            source_mount_point=args.target_mount_point,
            target_mount_point=args.target_mount_point,
            path_prefix=path_prefix,
            incorrect_key=args.incorrect_key,
            correct_key=args.correct_key,
            scenario_title=SCENARIO_1_TITLE,
            scenario_desc=s1_desc,
        )
        all_incorrect.extend(same_mount)

        # Pass 2: Scenario 2 — wrong mount + wrong key
        if args.source_mount_point != args.target_mount_point:
            s2_desc = format_scenario_desc(
                SCENARIO_2_DESC,
                incorrect=args.incorrect_key,
                correct=args.correct_key,
                source=args.source_mount_point,
                target=args.target_mount_point,
            )
            cross = run_scan(
                client=client,
                source_mount_point=args.source_mount_point,
                target_mount_point=args.target_mount_point,
                path_prefix=path_prefix,
                incorrect_key=args.incorrect_key,
                correct_key=args.correct_key,
                scenario_title=SCENARIO_2_TITLE,
                scenario_desc=s2_desc,
            )
            all_incorrect.extend(cross)
        else:
            print(
                f'\n  --- Scenario 2: skipped (source == target: '
                f'{args.source_mount_point!r}) ---'
            )
    else:
        # Single scan mode
        if not mount_point_exists(client, args.source_mount_point):
            print(
                f'\nMount point {args.source_mount_point!r} is not enabled. '
                f'Nothing to migrate.'
            )
            sys.exit(0)

        if cross_mount and not mount_point_exists(
                client, args.target_mount_point):
            if args.fix_incorrect and not args.dry_run:
                print(
                    f'\nError: Target mount point '
                    f'{args.target_mount_point!r} is not enabled. '
                    f'Enable it first.'
                )
                sys.exit(1)
            else:
                print(
                    f'\nWARNING: Target mount point '
                    f'{args.target_mount_point!r} is not enabled.'
                )

        # Print scenario description
        if cross_mount:
            scenario_title = SCENARIO_2_TITLE
            scenario_desc = format_scenario_desc(
                SCENARIO_2_DESC,
                incorrect=args.incorrect_key,
                correct=args.correct_key,
                source=args.source_mount_point,
                target=args.target_mount_point,
            )
        else:
            scenario_title = SCENARIO_1_TITLE
            scenario_desc = format_scenario_desc(
                SCENARIO_1_DESC,
                incorrect=args.incorrect_key,
                correct=args.correct_key,
            )

        print(f'\n  --- {scenario_title} ---')
        print(f'  {scenario_desc}')
        print()
        print('Scanning for incorrect secrets...')

        found = find_incorrect_secrets(
            client=client,
            source_mount_point=args.source_mount_point,
            target_mount_point=args.target_mount_point,
            path_prefix=path_prefix,
            incorrect_key=args.incorrect_key,
            correct_key=args.correct_key,
        )
        all_incorrect.extend(found)

    # --- Summary ---
    s1_count = sum(1 for s in all_incorrect if s['scenario'] == 'Scenario 1')
    s2_count = sum(1 for s in all_incorrect if s['scenario'] == 'Scenario 2')

    print()
    print('-' * 64)
    print('  Scan results')
    print('-' * 64)
    if args.scan_all_mounts or not cross_mount:
        print(
            f'  Scenario 1 (wrong key, correct mount):    {s1_count} secret(s)'
        )
    if args.scan_all_mounts or cross_mount:
        print(
            f'  Scenario 2 (wrong mount + wrong key):     {s2_count} secret(s)'
        )
    print(f'  Total to migrate:                         {len(all_incorrect)}')
    print()

    if not all_incorrect:
        print('Nothing to do. All secrets are at the correct location.')
        return

    # --- List incorrect ---
    if args.list_incorrect:
        print('-' * 64)
        print('  Secrets to migrate')
        print('-' * 64)

        current_scenario = None
        for i, info in enumerate(all_incorrect, 1):
            scenario = info['scenario']
            source = info['source_mount']
            is_cross = info['cross_mount']

            # Print scenario sub-header when it changes
            if scenario != current_scenario:
                current_scenario = scenario
                print()
                if is_cross:
                    print(
                        f'  {scenario}: {source!r} -> '
                        f'{args.target_mount_point!r} '
                        f'(mount move + key rename)'
                    )
                else:
                    print(
                        f'  {scenario}: [{source}] '
                        f'(key {args.incorrect_key!r} -> '
                        f'{args.correct_key!r})'
                    )

            # Print secret details
            if is_cross:
                print(
                    f'  {i:>4}. [{source}] {info["path"]}'
                )
                print(
                    f'        body keys: {info["all_keys"]}'
                    f'  ->  [{args.target_mount_point}] '
                    f'key={args.correct_key!r}'
                )
            else:
                print(
                    f'  {i:>4}. [{source}] {info["path"]}'
                )
                print(
                    f'        body keys: {info["all_keys"]}'
                    f'  ->  key={args.correct_key!r}'
                )
        print()

    # --- Fix incorrect ---
    if args.fix_incorrect:
        print('-' * 64)
        if args.dry_run:
            print('  Migrating secrets (DRY RUN — no changes will be made)')
        else:
            print('  Migrating secrets')
        print('-' * 64)

        fixed, failed, skipped = fix_secrets(
            client=client,
            target_mount_point=args.target_mount_point,
            incorrect_secrets=all_incorrect,
            incorrect_key=args.incorrect_key,
            correct_key=args.correct_key,
            delete_source=args.delete_source,
            dry_run=args.dry_run,
        )

        print()
        print('-' * 64)
        print('  Migration results')
        print('-' * 64)
        print(f'  Migrated: {fixed}')
        if skipped:
            print(f'  Skipped:  {skipped} (already correct at target)')
        if failed:
            print(f'  Failed:   {failed}')
        if args.dry_run:
            print()
            print('  This was a DRY RUN. No changes were made.')
            print('  Remove --dry_run to apply the migration.')

    print()
    print('Done.')


if __name__ == '__main__':
    main()
