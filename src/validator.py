"""
Validate CAP JSON dump files against the parsed template schema.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from .schema_parser import (
    SchemaArray,
    SchemaLeaf,
    SchemaNode,
    SchemaObject,
    load_schema,
)


@dataclass
class ValidationIssue:
    file: str
    path: str
    severity: str  # error, warning
    message: str


def validate_value(data, schema_node: SchemaNode, path: str, issues: list[ValidationIssue], filename: str):
    """Recursively validate a data value against a schema node."""

    if data is None:
        # Check nullability for leaves
        if isinstance(schema_node, SchemaLeaf) and not schema_node.nullable:
            issues.append(ValidationIssue(filename, path, "warning", "Value is null but schema does not indicate nullable"))
        return

    if isinstance(schema_node, SchemaLeaf):
        _validate_leaf(data, schema_node, path, issues, filename)

    elif isinstance(schema_node, SchemaArray):
        if not isinstance(data, list):
            issues.append(ValidationIssue(filename, path, "error", f"Expected array, got {type(data).__name__}"))
            return
        if schema_node.item_schema:
            for i, item in enumerate(data):
                validate_value(item, schema_node.item_schema, f"{path}[{i}]", issues, filename)

    elif isinstance(schema_node, SchemaObject):
        if not isinstance(data, dict):
            issues.append(ValidationIssue(filename, path, "error", f"Expected object, got {type(data).__name__}"))
            return
        _validate_object(data, schema_node, path, issues, filename)


def _validate_leaf(data, schema_node: SchemaLeaf, path: str, issues: list, filename: str):
    if schema_node.base_type == "boolean":
        if not isinstance(data, bool):
            issues.append(ValidationIssue(filename, path, "error", f"Expected boolean, got {type(data).__name__}: {data!r}"))
    elif schema_node.base_type == "integer":
        if not isinstance(data, int) or isinstance(data, bool):
            issues.append(ValidationIssue(filename, path, "error", f"Expected integer, got {type(data).__name__}: {data!r}"))
    elif schema_node.base_type == "enum":
        if isinstance(data, str) and schema_node.enum_values:
            if data not in schema_node.enum_values:
                issues.append(ValidationIssue(filename, path, "warning", f"Value '{data}' not in known enum values: {schema_node.enum_values}"))
    elif schema_node.base_type in ("string", "datetime"):
        if not isinstance(data, str):
            issues.append(ValidationIssue(filename, path, "warning", f"Expected string, got {type(data).__name__}: {data!r}"))


def _validate_object(data: dict, schema_node: SchemaObject, path: str, issues: list, filename: str):
    # Check for unexpected keys
    allowed_keys = set(schema_node.properties.keys())
    # Always allow OData metadata keys at any level
    odata_keys = {"@odata.type", "@odata.context", "@odata.id"}
    for key in data:
        if key not in allowed_keys and key not in odata_keys:
            issues.append(ValidationIssue(filename, f"{path}.{key}" if path else key, "warning", f"Unexpected key not in schema"))

    # Check for missing required keys
    for key, child_schema in schema_node.properties.items():
        if isinstance(child_schema, SchemaLeaf) and child_schema.required and key not in data:
            issues.append(ValidationIssue(filename, f"{path}.{key}" if path else key, "error", f"Missing required key"))

    # Recurse into known keys
    for key, value in data.items():
        full_path = f"{path}.{key}" if path else key
        if key in schema_node.properties:
            child_schema = schema_node.properties[key]
            # Handle case where schema says object but data has null (optional section)
            if value is None and isinstance(child_schema, SchemaObject):
                continue  # Optional sections can be null
            validate_value(value, child_schema, full_path, issues, filename)


def validate_file(file_path: Path, schema: SchemaObject) -> list[ValidationIssue]:
    filename = file_path.name
    try:
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return [ValidationIssue(filename, "", "error", f"Invalid JSON: {e}")]

    if not isinstance(data, dict):
        return [ValidationIssue(filename, "", "error", "Top-level value must be an object")]

    issues = []
    _validate_object(data, schema, "", issues, filename)
    return issues


def validate_directory(input_dir: str | Path, schema_path: str | Path) -> dict[str, list[ValidationIssue]]:
    """Validate all JSON files in a directory. Returns {filename: [issues]}."""
    schema = load_schema(schema_path)
    input_dir = Path(input_dir)
    results = {}
    for json_file in sorted(input_dir.glob("*.json")):
        if json_file.name == Path(schema_path).name:
            continue  # Skip the schema file itself
        issues = validate_file(json_file, schema)
        results[json_file.name] = issues
    return results
