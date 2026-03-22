"""
Generate a YAML config file from the schema with all flattened keys.
"""

from pathlib import Path

import yaml

from .flattener import flatten_schema
from .schema_parser import load_schema


def generate_config(schema_path: str | Path, output_path: str | Path, all_true: bool = True):
    """Read the schema, flatten all keys, and write a YAML config file."""
    schema = load_schema(schema_path)
    paths = flatten_schema(schema)

    columns = {}
    for p in paths:
        columns[p] = all_true

    config = {"columns": columns}

    with open(output_path, "w") as f:
        f.write("# CAP Report Configuration\n")
        f.write("# Set keys to false to exclude from the Excel report\n")
        f.write("#\n")
        f.write("# Each key is a dot-notation path into the Conditional Access Policy JSON.\n")
        f.write("# Example: conditions.users.includeUsers corresponds to\n")
        f.write("#   policy[\"conditions\"][\"users\"][\"includeUsers\"]\n\n")
        yaml.dump(config, f, default_flow_style=False, sort_keys=False, width=120)

    print(f"Config written to {output_path} ({len(columns)} keys)")
