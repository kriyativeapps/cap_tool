"""
Generate YAML config files for the report, dedup, and similar commands.
"""

import json
from pathlib import Path

import yaml

from .flattener import flatten_json, flatten_schema
from .schema_parser import load_schema


def _collect_observed_paths(input_dir: Path) -> set[str]:
    """Scan all JSON policy files and return the set of dot-notation paths
    that have a non-empty value in at least one file."""
    observed: set[str] = set()
    json_files = sorted(input_dir.glob("*.json"))
    json_files = [f for f in json_files if "schema" not in f.name.lower()]

    for json_file in json_files:
        try:
            with open(json_file, encoding="utf-8-sig") as f:
                data = json.load(f)
            flat = flatten_json(data)
            for key, value in flat.items():
                if value:  # skip empty strings (from None / empty arrays)
                    observed.add(key)
        except (json.JSONDecodeError, Exception):
            pass

    return observed


def generate_configs(schema_path: str | Path, output_dir: str | Path,
                     all_true: bool = True, input_dir: str | Path | None = None):
    """Read the schema and write all three config files to output_dir.

    If *input_dir* is provided, only include paths that actually appear
    with non-empty values in the policy files (eliminates phantom columns).
    """
    schema = load_schema(schema_path)
    paths = flatten_schema(schema)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Filter to paths actually observed in data
    if input_dir:
        input_dir = Path(input_dir)
        observed = _collect_observed_paths(input_dir)
        before = len(paths)
        paths = [p for p in paths if p in observed]
        dropped = before - len(paths)
        if dropped:
            print(f"Filtered {dropped} empty paths (not observed in any policy file)")

    print(f"Generating config files in {output_dir}/ ({len(paths)} fields)")
    _generate_report_config(paths, output_dir / "report_config.yaml", all_true)
    _generate_dedup_config(paths, output_dir / "dedup_config.yaml")
    _generate_similar_config(paths, output_dir / "similar_config.yaml")


def _generate_report_config(paths: list[str], output_path: Path, all_true: bool):
    columns = {p: all_true for p in paths}
    config = {"columns": columns}

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# Report Configuration\n")
        f.write("# Set keys to false to exclude from the Excel report.\n")
        f.write("#\n")
        f.write("# Each key is a dot-notation path into the Conditional Access Policy JSON.\n")
        f.write("# Example: conditions.users.includeUsers corresponds to\n")
        f.write("#   policy[\"conditions\"][\"users\"][\"includeUsers\"]\n\n")
        yaml.dump(config, f, default_flow_style=False, sort_keys=False, width=120)

    print(f"  report_config.yaml  ({len(columns)} columns)")


def _generate_dedup_config(paths: list[str], output_path: Path):
    default_volatile = {"id", "createdDateTime", "modifiedDateTime", "templateId"}
    volatile = {p: (p in default_volatile) for p in paths}
    compare = {p: False for p in paths}

    config = {
        "volatile_fields": volatile,
        "sort_arrays": True,
        "modes": ["content", "id"],
        "compare_fields": compare,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# Deduplication Configuration\n")
        f.write("#\n")
        f.write("# Controls how policies are normalized before comparison.\n")
        f.write("# Two policies are \"duplicates\" if their normalized forms hash identically.\n\n")

        f.write("# Fields to strip before comparing.\n")
        f.write("# Set to true to exclude a field from comparison.\n")
        yaml.dump({"volatile_fields": volatile}, f, default_flow_style=False, sort_keys=False, width=120)

        f.write("\n# Sort primitive arrays before comparison.\n")
        yaml.dump({"sort_arrays": True}, f, default_flow_style=False, sort_keys=False)

        f.write("\n# Which duplicate checks to run.\n")
        f.write("#   content — compare ALL remaining keys after stripping volatile_fields\n")
        f.write("#   id      — check if same policy ID appears in multiple files\n")
        f.write("#   fields  — compare ONLY the keys set to true in compare_fields\n")
        yaml.dump({"modes": ["content", "id"]}, f, default_flow_style=False, sort_keys=False)

        f.write("\n# Fields to compare in \"fields\" mode.\n")
        f.write("# Set to true to include a field in comparison.\n")
        yaml.dump({"compare_fields": compare}, f, default_flow_style=False, sort_keys=False, width=120)

    print(f"  dedup_config.yaml   ({sum(volatile.values())} volatile, {len(paths)} fields)")


def _generate_similar_config(paths: list[str], output_path: Path):
    default_ignore = {"id", "createdDateTime", "modifiedDateTime", "templateId"}
    ignore = {p: (p in default_ignore) for p in paths}

    config = {
        "ignore_fields": ignore,
        "limit": 5,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# Similar Policy Finder Configuration\n")
        f.write("#\n")
        f.write("# Compares every pair of policy files, counts parameter-level differences,\n")
        f.write("# and ranks pairs from fewest to most — helping identify merge candidates.\n\n")

        f.write("# Fields to ignore during comparison.\n")
        f.write("# Set to true to exclude a field from similarity analysis.\n")
        yaml.dump({"ignore_fields": ignore}, f, default_flow_style=False, sort_keys=False, width=120)

        f.write("\n# Maximum number of most-similar pairs to display.\n")
        yaml.dump({"limit": 5}, f, default_flow_style=False, sort_keys=False)

    print(f"  similar_config.yaml ({sum(ignore.values())} ignored, {len(paths)} fields)")
