"""
Parse a CAP schema into a structural definition for validation.

Supports two formats:
1. CAP template format — leaf values are type-description strings, arrays contain
   a single exemplar element, and metadata keys ($type, $comment, $ref, $variants)
   are not data keys.
2. Standard JSON Schema — objects use "type", "properties", and "items" structurally.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

ENUM_PATTERN = re.compile(r"'([^']+)'")
META_KEYS = {"$type", "$comment", "$schema", "$ref", "$variants"}


@dataclass
class SchemaLeaf:
    base_type: str  # string, boolean, integer, datetime, enum, unknown
    nullable: bool = False
    enum_values: list[str] = field(default_factory=list)
    read_only: bool = False
    required: bool = False
    raw: str = ""


@dataclass
class SchemaArray:
    item_schema: Union["SchemaLeaf", "SchemaArray", "SchemaObject", None] = None


@dataclass
class SchemaObject:
    properties: dict[str, Union["SchemaLeaf", "SchemaArray", "SchemaObject"]] = field(
        default_factory=dict
    )


SchemaNode = Union[SchemaLeaf, SchemaArray, SchemaObject]


def parse_leaf(value: str) -> SchemaLeaf:
    nullable = "| null" in value or value.strip() == "null"
    enums = ENUM_PATTERN.findall(value)
    read_only = "read-only" in value.lower()
    required = "required" in value.lower()

    if "Boolean" in value:
        base_type = "boolean"
    elif "Int32" in value or "Integer" in value:
        base_type = "integer"
    elif "DateTimeOffset" in value:
        base_type = "datetime"
    elif enums and "String" not in value:
        base_type = "enum"
    elif "String" in value:
        base_type = "string"
    else:
        # Could be a bare enum like "'minor' | 'moderate' | ..."
        if enums:
            base_type = "enum"
        else:
            base_type = "unknown"

    return SchemaLeaf(
        base_type=base_type,
        nullable=nullable,
        enum_values=enums,
        read_only=read_only,
        required=required,
        raw=value,
    )


def parse_schema_node(value, parent_properties=None) -> Optional[SchemaNode]:
    if isinstance(value, str):
        return parse_leaf(value)

    if isinstance(value, list):
        if len(value) == 0:
            return SchemaArray(item_schema=None)
        item = value[0]
        return SchemaArray(item_schema=parse_schema_node(item))

    if isinstance(value, dict):
        # Detect standard JSON Schema format

        # Handle "anyOf" (genson nullable pattern: [{"type":"null"}, {"type":"object",...}])
        if "anyOf" in value and isinstance(value["anyOf"], list):
            non_null = [v for v in value["anyOf"] if v != {"type": "null"}]
            if non_null:
                return parse_schema_node(non_null[0])
            return parse_leaf("null")

        # Handle "type" as a string
        if "type" in value and isinstance(value["type"], str):
            schema_type = value["type"]
            if schema_type == "object" and "properties" in value:
                obj = SchemaObject()
                for k, v in value["properties"].items():
                    parsed = parse_schema_node(v)
                    if parsed is not None:
                        obj.properties[k] = parsed
                return obj
            if schema_type == "array" and "items" in value:
                return SchemaArray(item_schema=parse_schema_node(value["items"]))
            if schema_type == "array":
                return SchemaArray(item_schema=None)
            # Primitive or null JSON Schema type
            return parse_leaf(value.get("description", schema_type))

        # Handle "type" as a list (genson nullable: ["null", "string"])
        if "type" in value and isinstance(value["type"], list):
            non_null_types = [t for t in value["type"] if t != "null"]
            resolved_type = non_null_types[0] if non_null_types else "null"
            return parse_leaf(value.get("description", resolved_type))

        obj = SchemaObject()
        # First pass: parse non-meta, non-$ref keys
        for k, v in value.items():
            if k in META_KEYS:
                continue
            parsed = parse_leaf(v) if isinstance(v, str) else parse_schema_node(v)
            if parsed is not None:
                obj.properties[k] = parsed

        # Handle $variants: lift all variant keys into this object's allowed properties
        if "$variants" in value and isinstance(value["$variants"], dict):
            for variant_name, variant_obj in value["$variants"].items():
                if isinstance(variant_obj, dict):
                    for vk, vv in variant_obj.items():
                        if vk not in META_KEYS and vk not in obj.properties:
                            parsed_vv = parse_schema_node(vv)
                            if parsed_vv is not None:
                                obj.properties[vk] = parsed_vv

        # Handle $ref: copy from sibling
        if "$ref" in value and parent_properties:
            ref_str = value["$ref"]
            # Try to find the referenced sibling key name in the ref string
            for sibling_key, sibling_node in parent_properties.items():
                if sibling_key in ref_str:
                    obj = SchemaObject(
                        properties=dict(
                            sibling_node.properties
                            if isinstance(sibling_node, SchemaObject)
                            else {}
                        )
                    )
                    break

        return obj

    return None


def load_schema(schema_path: str | Path) -> SchemaObject:
    with open(schema_path, encoding="utf-8-sig") as f:
        raw = json.load(f)
    node = parse_schema_node(raw)
    if not isinstance(node, SchemaObject):
        raise ValueError("Top-level schema must be an object")
    # Allow @odata.context and @odata.type at top level (Graph API metadata)
    for odata_key in ["@odata.context", "@odata.type", "@odata.id"]:
        if odata_key not in node.properties:
            node.properties[odata_key] = SchemaLeaf(base_type="string", raw="OData metadata")
    return node
