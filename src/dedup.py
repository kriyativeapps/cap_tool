"""
Detect duplicate Conditional Access Policies across JSON dump files.

Normalizes each file (recursive key sort, optional array sort, volatile field
removal) then groups by SHA-256 hash.
"""

import hashlib
import json
from collections import defaultdict
from pathlib import Path

import yaml


def load_dedup_config(config_path: str | Path) -> dict:
    with open(config_path) as f:
        config = yaml.safe_load(f)
    return {
        "volatile_fields": set(config.get("volatile_fields", [])),
        "sort_arrays": config.get("sort_arrays", True),
        "modes": config.get("modes", ["content"]),
        "compare_fields": config.get("compare_fields", []),
    }


def _remove_volatile(data, volatile_fields: set, prefix: str = ""):
    """Recursively remove volatile fields from a nested dict."""
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if full_key in volatile_fields:
                continue
            result[key] = _remove_volatile(value, volatile_fields, full_key)
        return result
    if isinstance(data, list):
        return [_remove_volatile(item, volatile_fields, prefix) for item in data]
    return data


def _extract_fields(data: dict, field_paths: list[str]) -> dict:
    """Extract only the specified dot-notation paths from a nested dict."""
    result = {}
    for path in field_paths:
        parts = path.split(".")
        value = data
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                value = None
                break
        result[path] = value
    return result


def _normalize(data, sort_arrays: bool = True):
    """Recursively sort dict keys and optionally sort primitive arrays."""
    if isinstance(data, dict):
        return {k: _normalize(v, sort_arrays) for k, v in sorted(data.items())}
    if isinstance(data, list):
        normalized = [_normalize(item, sort_arrays) for item in data]
        if sort_arrays and normalized and not isinstance(normalized[0], dict):
            try:
                normalized = sorted(normalized, key=lambda x: json.dumps(x, sort_keys=True))
            except TypeError:
                pass  # mixed types, keep original order
        return normalized
    return data


def _hash_data(data) -> str:
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def find_duplicates(input_dir: str | Path, config_path: str | Path):
    """Main entry point: load config, process files, report duplicates."""
    config = load_dedup_config(config_path)
    input_dir = Path(input_dir)
    json_files = sorted(input_dir.glob("*.json"))
    json_files = [f for f in json_files if "schema" not in f.name.lower()]

    if not json_files:
        print(f"No JSON files found in {input_dir}")
        return

    # Load all files
    policies = {}
    for json_file in json_files:
        try:
            with open(json_file) as f:
                policies[json_file.name] = json.load(f)
        except json.JSONDecodeError as e:
            print(f"  Skipping {json_file.name}: {e}")

    print(f"Loaded {len(policies)} policy files\n")

    for mode in config["modes"]:
        if mode == "content":
            _report_content_duplicates(policies, config)
        elif mode == "id":
            _report_id_duplicates(policies)
        elif mode == "fields":
            _report_fields_duplicates(policies, config)
        else:
            print(f"Unknown mode: {mode}")


def _report_content_duplicates(policies: dict, config: dict):
    """Group files by normalized content hash."""
    print("=" * 60)
    print("CONTENT DUPLICATES")
    print(f"  Volatile fields excluded: {sorted(config['volatile_fields'])}")
    print(f"  Array sorting: {'on' if config['sort_arrays'] else 'off'}")
    print("=" * 60)

    hash_groups = defaultdict(list)
    for filename, data in policies.items():
        cleaned = _remove_volatile(data, config["volatile_fields"])
        normalized = _normalize(cleaned, config["sort_arrays"])
        h = _hash_data(normalized)
        hash_groups[h].append(filename)

    dup_count = 0
    for h, files in hash_groups.items():
        if len(files) > 1:
            dup_count += 1
            print(f"\n  Duplicate group (hash: {h[:12]}...):")
            for f in files:
                policy_id = policies[f].get("id", "?")
                display_name = policies[f].get("displayName", "?")
                print(f"    - {f}")
                print(f"      id={policy_id}  name=\"{display_name}\"")

    if dup_count == 0:
        print("\n  No content duplicates found.")
    else:
        print(f"\n  {dup_count} duplicate group(s) found.")
    print()


def _report_id_duplicates(policies: dict):
    """Group files by the id field."""
    print("=" * 60)
    print("ID DUPLICATES (same policy ID in multiple files)")
    print("=" * 60)

    id_groups = defaultdict(list)
    for filename, data in policies.items():
        policy_id = data.get("id", None)
        if policy_id:
            id_groups[policy_id].append(filename)

    dup_count = 0
    for policy_id, files in id_groups.items():
        if len(files) > 1:
            dup_count += 1
            print(f"\n  Policy ID: {policy_id}")
            for f in files:
                mod_time = policies[f].get("modifiedDateTime", "?")
                print(f"    - {f}  (modified: {mod_time})")

    if dup_count == 0:
        print("\n  No ID duplicates found.")
    else:
        print(f"\n  {dup_count} duplicate group(s) found.")
    print()


def _report_fields_duplicates(policies: dict, config: dict):
    """Group files by a specific subset of fields."""
    compare_fields = config.get("compare_fields", [])
    if not compare_fields:
        print("=" * 60)
        print("FIELDS DUPLICATES — skipped (no compare_fields configured)")
        print("=" * 60)
        print()
        return

    print("=" * 60)
    print("FIELDS DUPLICATES")
    print(f"  Comparing on: {compare_fields}")
    print("=" * 60)

    hash_groups = defaultdict(list)
    for filename, data in policies.items():
        extracted = _extract_fields(data, compare_fields)
        normalized = _normalize(extracted, config["sort_arrays"])
        h = _hash_data(normalized)
        hash_groups[h].append(filename)

    dup_count = 0
    for h, files in hash_groups.items():
        if len(files) > 1:
            dup_count += 1
            print(f"\n  Duplicate group (hash: {h[:12]}...):")
            for f in files:
                display_name = policies[f].get("displayName", "?")
                print(f"    - {f}  name=\"{display_name}\"")

    if dup_count == 0:
        print("\n  No field-based duplicates found.")
    else:
        print(f"\n  {dup_count} duplicate group(s) found.")
    print()
