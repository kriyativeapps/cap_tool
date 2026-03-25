"""
Find near-duplicate Conditional Access Policies that are merge candidates.

Compares every pair of policy files, counts parameter-level differences,
and ranks pairs from fewest to most differences.
"""

import itertools
import json
from pathlib import Path

import yaml

from .dedup import _normalize, _remove_volatile


def _load_similar_config(config_path: str | Path) -> dict:
    with open(config_path, encoding="utf-8-sig") as f:
        config = yaml.safe_load(f)

    # ignore_fields: accept list (legacy) or dict {path: bool} (new)
    raw_ignore = config.get("ignore_fields", [])
    if isinstance(raw_ignore, dict):
        ignore = {k for k, v in raw_ignore.items() if v}
    else:
        ignore = set(raw_ignore)

    return {
        "ignore_fields": ignore,
        "limit": config.get("limit", 5),
    }


def _flatten_for_diff(data: dict, prefix: str = "") -> dict[str, str]:
    """Flatten a nested dict into dot-notation keys with stringified values."""
    result = {}
    for key, value in data.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            result.update(_flatten_for_diff(value, full_key))
        elif isinstance(value, list):
            result[full_key] = json.dumps(value, sort_keys=True)
        elif value is None:
            result[full_key] = "null"
        else:
            result[full_key] = str(value)
    return result


def _diff_policies(flat_a: dict, flat_b: dict) -> list[tuple[str, str, str]]:
    """Return list of (key, value_a, value_b) for keys that differ."""
    all_keys = sorted(set(flat_a) | set(flat_b))
    diffs = []
    for key in all_keys:
        val_a = flat_a.get(key)
        val_b = flat_b.get(key)
        if val_a != val_b:
            diffs.append((key, val_a if val_a is not None else "<missing>",
                          val_b if val_b is not None else "<missing>"))
    return diffs


def find_similar(input_dir: str | Path, config_path: str | Path):
    """Load config and policy files, rank pairs by fewest differences, and print results."""
    config = _load_similar_config(config_path)
    ignore_fields = config["ignore_fields"]
    limit = config["limit"]

    input_dir = Path(input_dir)
    json_files = sorted(input_dir.glob("*.json"))
    json_files = [f for f in json_files if "schema" not in f.name.lower()]

    if not json_files:
        print(f"No JSON files found in {input_dir}")
        return

    # Load all files
    policies: dict[str, dict] = {}
    for json_file in json_files:
        try:
            with open(json_file, encoding="utf-8-sig") as f:
                policies[json_file.name] = json.load(f)
        except json.JSONDecodeError as e:
            print(f"  Skipping {json_file.name}: {e}")

    print(f"Loaded {len(policies)} policy files")
    print(f"Ignored fields: {sorted(ignore_fields)}")
    print(f"Showing top {limit} pair(s)\n")

    # Flatten and normalize all policies
    flat_policies = {}
    for filename, data in policies.items():
        cleaned = _remove_volatile(data, ignore_fields)
        normalized = _normalize(cleaned, sort_arrays=True)
        flat_policies[filename] = _flatten_for_diff(normalized)

    # Compute pairwise diffs
    pairs = []
    for file_a, file_b in itertools.combinations(flat_policies, 2):
        diffs = _diff_policies(flat_policies[file_a], flat_policies[file_b])
        pairs.append((len(diffs), file_a, file_b, diffs))

    pairs.sort(key=lambda x: x[0])

    if not pairs:
        print("Not enough files to compare.")
        return

    print("=" * 60)
    print("SIMILAR POLICIES (ranked by fewest differences)")
    print("=" * 60)

    for rank, (diff_count, file_a, file_b, diffs) in enumerate(pairs[:limit], 1):
        name_a = policies[file_a].get("displayName", "?")
        name_b = policies[file_b].get("displayName", "?")
        print(f"\n  #{rank}  {diff_count} difference(s)")
        print(f"    A: {file_a}  (\"{name_a}\")")
        print(f"    B: {file_b}  (\"{name_b}\")")
        if diff_count == 0:
            print("    (identical after normalization)")
        else:
            for key, val_a, val_b in diffs:
                print(f"    - {key}")
                print(f"        A: {val_a}")
                print(f"        B: {val_b}")

    print(f"\n  {len(pairs)} pair(s) compared total.\n")
