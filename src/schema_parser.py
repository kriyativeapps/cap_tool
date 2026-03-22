"""
Parse the CAP template schema into a structural definition for validation.

The schema file is NOT a standard JSON Schema — it's a structural template where
leaf values are type-description strings, arrays contain a single exemplar element,
and metadata keys ($type, $comment, $ref, $variants) are not data keys.
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
    item_schema: Union["SchemaLeaf", "SchemaObject", None] = None


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
        obj = SchemaObject()
        # First pass: parse non-meta, non-$ref keys
        for k, v in value.items():
            if k in META_KEYS:
                continue
            if k == "@odata.type":
                obj.properties[k] = parse_leaf(v) if isinstance(v, str) else parse_schema_node(v)
                continue
            obj.properties[k] = parse_schema_node(v, parent_properties=obj.properties)

        # Handle $variants: lift all variant keys into this object's allowed properties
        if "$variants" in value and isinstance(value["$variants"], dict):
            for variant_name, variant_obj in value["$variants"].items():
                if isinstance(variant_obj, dict):
                    for vk, vv in variant_obj.items():
                        if vk not in META_KEYS and vk not in obj.properties:
                            obj.properties[vk] = parse_schema_node(vv)

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
    with open(schema_path) as f:
        raw = json.load(f)
    node = parse_schema_node(raw)
    if not isinstance(node, SchemaObject):
        raise ValueError("Top-level schema must be an object")
    # Allow @odata.context and @odata.type at top level (Graph API metadata)
    for odata_key in ["@odata.context", "@odata.type", "@odata.id"]:
        if odata_key not in node.properties:
            node.properties[odata_key] = SchemaLeaf(base_type="string", raw="OData metadata")
    return node
