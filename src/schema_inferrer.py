"""
Infer a JSON Schema from actual CAP dump files using genson.

This tool scans all JSON dump files in a directory, feeds them into genson's
SchemaBuilder, and produces a merged JSON Schema that describes the actual
structure observed across all files.
"""

import json
from pathlib import Path

from genson import SchemaBuilder


def infer_schema(input_dir: str | Path, output_path: str | Path, schema_uri: str = "http://json-schema.org/draft-07/schema#"):
    """
    Infer a JSON Schema from all JSON files in input_dir.

    genson merges multiple samples into one schema that accepts all of them.
    The result captures:
      - Which keys exist (properties)
      - Which keys appear in every file (required)
      - Value types (string, boolean, integer, array, object, null)
      - Array item types
      - Nested object structures
    """
    input_dir = Path(input_dir)
    json_files = sorted(input_dir.glob("*.json"))
    json_files = [f for f in json_files if "schema" not in f.name.lower()]

    if not json_files:
        print(f"No JSON files found in {input_dir}")
        return

    builder = SchemaBuilder(schema_uri=schema_uri)

    file_count = 0
    for json_file in json_files:
        try:
            with open(json_file, encoding="utf-8-sig") as f:
                data = json.load(f)
            builder.add_object(data)
            file_count += 1
        except (json.JSONDecodeError, Exception) as e:
            print(f"  Skipping {json_file.name}: {e}")

    schema = builder.to_schema()

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2)

    print(f"Inferred schema from {file_count} files -> {output_path}")
    _print_schema_summary(schema)


def _print_schema_summary(schema: dict, prefix: str = "", depth: int = 0):
    """Print a brief summary of the inferred schema structure."""
    if depth == 0:
        print("\nSchema summary:")
        print("-" * 60)

    props = schema.get("properties", {})
    required = set(schema.get("required", []))

    for key, defn in props.items():
        full_path = f"{prefix}.{key}" if prefix else key
        types = defn.get("type", "?")
        if isinstance(types, list):
            type_str = "|".join(types)
        else:
            type_str = types

        req_marker = "*" if key in required else " "
        print(f"  {req_marker} {full_path}: {type_str}")

        # Recurse into objects
        if "properties" in defn:
            _print_schema_summary(defn, full_path, depth + 1)
        # Recurse into array items
        if "items" in defn and isinstance(defn["items"], dict) and "properties" in defn["items"]:
            _print_schema_summary(defn["items"], f"{full_path}[]", depth + 1)


def compare_schemas(inferred_path: str | Path, reference_path: str | Path):
    """
    Compare an inferred schema against the reference template schema.
    Shows keys present in one but not the other.
    """
    from .flattener import flatten_schema
    from .schema_parser import load_schema

    # Load inferred schema keys
    with open(inferred_path, encoding="utf-8-sig") as f:
        inferred = json.load(f)
    inferred_keys = set(_extract_paths(inferred))

    # Load reference template schema keys
    ref_schema = load_schema(reference_path)
    ref_keys = set(flatten_schema(ref_schema))

    only_in_inferred = sorted(inferred_keys - ref_keys)
    only_in_reference = sorted(ref_keys - inferred_keys)

    print("\n=== Schema Comparison ===")
    print(f"Keys in inferred schema:  {len(inferred_keys)}")
    print(f"Keys in reference schema: {len(ref_keys)}")
    print(f"Common keys:              {len(inferred_keys & ref_keys)}")

    if only_in_inferred:
        print(f"\nKeys ONLY in inferred (present in dumps but not in reference schema):")
        for k in only_in_inferred:
            print(f"  + {k}")

    if only_in_reference:
        print(f"\nKeys ONLY in reference (in schema but not observed in any dump):")
        for k in only_in_reference:
            print(f"  - {k}")

    if not only_in_inferred and not only_in_reference:
        print("\nSchemas match perfectly!")


def _extract_paths(schema: dict, prefix: str = "") -> list[str]:
    """Extract dot-notation paths from a standard JSON Schema."""
    paths = []
    props = schema.get("properties", {})
    for key, defn in props.items():
        full_path = f"{prefix}.{key}" if prefix else key

        if "properties" in defn:
            paths.extend(_extract_paths(defn, full_path))
        elif defn.get("type") == "array" and "items" in defn:
            items = defn["items"]
            if isinstance(items, dict) and "properties" in items:
                paths.extend(_extract_paths(items, full_path))
            else:
                paths.append(full_path)
        else:
            paths.append(full_path)

    return paths
