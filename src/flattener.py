"""
Flatten nested JSON data or schema nodes into dot-notation key paths.
"""

from .schema_parser import SchemaArray, SchemaLeaf, SchemaNode, SchemaObject


def flatten_json(data: dict, prefix: str = "") -> dict[str, str]:
    """Flatten a JSON dict into dot-notation keys with stringified values."""
    result = {}
    if not isinstance(data, dict):
        return result
    for key, value in data.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            result.update(flatten_json(value, full_key))
        elif isinstance(value, list):
            # Join primitive arrays with semicolons
            if value and isinstance(value[0], dict):
                # Array of objects — stringify as JSON
                import json

                result[full_key] = json.dumps(value)
            else:
                result[full_key] = ";".join(str(v) for v in value)
        elif value is None:
            result[full_key] = ""
        else:
            result[full_key] = str(value)
    return result


def flatten_schema(node: SchemaNode, prefix: str = "") -> list[str]:
    """Walk the schema tree and return all dot-notation leaf/array paths."""
    paths = []

    if isinstance(node, SchemaLeaf):
        if prefix:
            paths.append(prefix)

    elif isinstance(node, SchemaArray):
        if prefix:
            paths.append(prefix)
        # If the array contains objects, also flatten those sub-keys
        if isinstance(node.item_schema, SchemaObject):
            for key, child in node.item_schema.properties.items():
                child_prefix = f"{prefix}.{key}" if prefix else key
                paths.extend(flatten_schema(child, child_prefix))

    elif isinstance(node, SchemaObject):
        for key, child in node.properties.items():
            child_prefix = f"{prefix}.{key}" if prefix else key
            paths.extend(flatten_schema(child, child_prefix))

    return paths
