"""
Generate YAML config files for the report, dedup, and similar commands.
"""

from pathlib import Path

import yaml

from .flattener import flatten_schema
from .schema_parser import load_schema


def generate_configs(schema_path: str | Path, output_dir: str | Path, all_true: bool = True):
    """Read the schema and write all three config files to output_dir."""
    schema = load_schema(schema_path)
    paths = flatten_schema(schema)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Generating config files in {output_dir}/")
    _generate_report_config(paths, output_dir / "report_config.yaml", all_true)
    _generate_dedup_config(paths, output_dir / "dedup_config.yaml")
    _generate_similar_config(output_dir / "similar_config.yaml")


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
    volatile = ["id", "createdDateTime", "modifiedDateTime", "templateId"]

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# Deduplication Configuration\n")
        f.write("#\n")
        f.write("# Controls how policies are normalized before comparison.\n")
        f.write("# Two policies are \"duplicates\" if their normalized forms hash identically.\n\n")

        f.write("# Fields to strip before comparing (dot-notation paths).\n")
        f.write("# These change across exports but don't affect policy behavior.\n")
        yaml.dump({"volatile_fields": volatile}, f, default_flow_style=False, sort_keys=False)

        f.write("\n# Sort primitive arrays before comparison.\n")
        f.write("# When true, [\"b\", \"a\"] and [\"a\", \"b\"] are treated as equal.\n")
        yaml.dump({"sort_arrays": True}, f, default_flow_style=False, sort_keys=False)

        f.write("\n# Which duplicate checks to run. Each produces its own section in the output.\n")
        f.write("#\n")
        f.write("#   content — Are any two files identical (after stripping volatile_fields)?\n")
        f.write("#             Compares ALL remaining keys in each policy.\n")
        f.write("#             Use case: detect re-exported or copy-pasted policies.\n")
        f.write("#\n")
        f.write("#   id      — Do any two files share the same \"id\" value?\n")
        f.write("#             Use case: spot the same policy saved in multiple files\n")
        f.write("#             (possibly different versions from different export dates).\n")
        f.write("#\n")
        f.write("#   fields  — Are any two files identical when comparing ONLY the keys\n")
        f.write("#             listed in compare_fields below? (Skipped if compare_fields is empty.)\n")
        f.write("#             This is NOT the same as \"content\" — content compares every key,\n")
        f.write("#             while fields compares only the specific keys you choose.\n")
        f.write("#             Use case: find policies that target the same users + apps\n")
        f.write("#             even if their grant controls or session settings differ.\n")
        f.write("#\n")
        yaml.dump({"modes": ["content", "id"]}, f, default_flow_style=False, sort_keys=False)

        f.write("\n# Only used when \"fields\" mode is enabled.\n")
        f.write("# List of dot-notation paths to compare. If empty, \"fields\" mode is skipped.\n")
        f.write("# Uncomment the lines below (remove the leading #) to enable:\n")
        f.write("compare_fields: []\n")
        # Write example fields as comments
        for p in paths:
            if any(k in p for k in ["includeUsers", "excludeUsers",
                                     "includeApplications", "excludeApplications",
                                     "builtInControls", "state"]):
                f.write(f"#  - {p}\n")

    print(f"  dedup_config.yaml   (volatile: {volatile})")


def _generate_similar_config(output_path: Path):
    ignore = ["id", "createdDateTime", "modifiedDateTime", "templateId"]

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# Similar Policy Finder Configuration\n")
        f.write("#\n")
        f.write("# Compares every pair of policy files, counts parameter-level differences,\n")
        f.write("# and ranks pairs from fewest to most — helping identify merge candidates.\n\n")

        f.write("# Fields to ignore during comparison (dot-notation paths).\n")
        f.write("# These change across exports but don't affect policy behavior.\n")
        yaml.dump({"ignore_fields": ignore}, f, default_flow_style=False, sort_keys=False)

        f.write("\n# Maximum number of most-similar pairs to display.\n")
        yaml.dump({"limit": 5}, f, default_flow_style=False, sort_keys=False)

    print(f"  similar_config.yaml (ignore: {ignore})")
