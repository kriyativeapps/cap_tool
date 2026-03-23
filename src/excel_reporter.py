"""
Create an Excel report from validated CAP JSON files using a YAML config.
"""

import json
from pathlib import Path

import yaml
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .flattener import flatten_json


def load_config(config_path: str | Path) -> list[str]:
    """Load the YAML config and return the list of enabled column keys."""
    with open(config_path, encoding="utf-8-sig") as f:
        config = yaml.safe_load(f)
    columns = config.get("columns", {})
    return [key for key, enabled in columns.items() if enabled]


def generate_report(input_dir: str | Path, config_path: str | Path, output_path: str | Path):
    """Read all JSON files, flatten them, and write an Excel workbook."""
    columns = load_config(config_path)
    if not columns:
        print("No columns enabled in config. Nothing to report.")
        return

    input_dir = Path(input_dir)
    json_files = sorted(input_dir.glob("*.json"))

    # Exclude any file that looks like a schema or config
    json_files = [f for f in json_files if "schema" not in f.name.lower()]

    if not json_files:
        print(f"No JSON files found in {input_dir}")
        return

    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "CAP Policies"

    # Header style
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")

    # Write header row: first column is the filename
    headers = ["filename"] + columns
    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", wrap_text=True)

    # Write data rows
    for row_idx, json_file in enumerate(json_files, 2):
        with open(json_file, encoding="utf-8-sig") as f:
            data = json.load(f)

        flat = flatten_json(data)

        ws.cell(row=row_idx, column=1, value=json_file.name)
        for col_idx, key in enumerate(columns, 2):
            value = flat.get(key, "")
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            if isinstance(value, str) and "\n" in value:
                cell.alignment = Alignment(wrap_text=True, vertical="top")

    # Auto-size columns (approximate)
    for col_idx, header in enumerate(headers, 1):
        col_letter = get_column_letter(col_idx)
        # Use header length as minimum, cap at 50
        max_len = min(max(len(header.split(".")[-1]), 12), 50)
        ws.column_dimensions[col_letter].width = max_len + 2

    # Freeze the header row and filename column
    ws.freeze_panes = "B2"

    # Auto-filter
    ws.auto_filter.ref = ws.dimensions

    wb.save(output_path)
    print(f"Report written to {output_path} ({len(json_files)} policies, {len(columns)} columns)")
