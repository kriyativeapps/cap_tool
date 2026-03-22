# CAP Tool

Utility for evaluating Azure Conditional Access Policy (CAP) JSON dumps exported from Microsoft Graph API.

## Features

- **Validate** dump files against a reference template schema
- **Infer** a JSON Schema from your actual dumps using [genson](https://github.com/wolverdude/GenSON)
- **Compare** inferred schema vs reference to find gaps in either direction
- **Detect duplicates** across files using configurable normalization (key sort, volatile field exclusion, array sort)
- **Generate Excel reports** with configurable column selection via YAML config

## Setup

```bash
cd cap_tool
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Commands

All commands run from the `cap_tool/` directory.

### validate

Check that dump files conform to the reference template schema.

```bash
.venv/bin/python cli.py validate \
  --schema conditional_access_policy_schema.json \
  --input-dir <policy_dir>
```

Reports per-file: unexpected keys, missing required keys, type mismatches.

### infer

Infer a proper draft-07 JSON Schema from actual dump files using genson.

```bash
.venv/bin/python cli.py infer \
  --input-dir <policy_dir> \
  --output inferred_schema.json
```

Merges all files into one schema capturing observed types, required fields, and nesting.

### compare

Diff the inferred schema against the reference template.

```bash
.venv/bin/python cli.py compare \
  --inferred inferred_schema.json \
  --reference conditional_access_policy_schema.json
```

Shows keys found in dumps but not in the reference, and vice versa.

### dedup

Find duplicate policies across files. Two files with different names, key ordering, IDs, and timestamps can still be the same policy.

```bash
.venv/bin/python cli.py dedup \
  --input-dir <policy_dir> \
  --config dedup_config.yaml
```

Controlled by `dedup_config.yaml`:

| Setting | Purpose |
|---|---|
| `volatile_fields` | Dot-notation paths stripped before comparing (default: `id`, `createdDateTime`, `modifiedDateTime`, `templateId`) |
| `sort_arrays` | Treat `["a","b"]` and `["b","a"]` as equal |
| `modes` | Detection strategies: `content` (normalized hash), `id` (same policy ID), `fields` (subset of keys) |
| `compare_fields` | For `fields` mode — compare only specific paths |

### generate

Auto-generate a YAML report config listing all flattened keys from the schema.

```bash
.venv/bin/python cli.py generate \
  --schema conditional_access_policy_schema.json \
  --output report_config.yaml
```

Edit the generated `report_config.yaml` to toggle columns `true`/`false`.
Use `--all-false` to start with everything disabled (opt-in mode).

### report

Create an Excel spreadsheet from dump files. Each row is a policy, each column is a flattened key enabled in the config.

```bash
.venv/bin/python cli.py report \
  --input-dir <policy_dir> \
  --config report_config.yaml \
  --output cap_report.xlsx
```

Arrays are semicolon-joined. Missing fields appear as empty cells.

## Project Structure

```
cap_tool/
├── cli.py                                # CLI entry point
├── conditional_access_policy_schema.json # Reference template schema
├── dedup_config.yaml                     # Deduplication settings
├── requirements.txt
├── sample_caps/                          # Sample policy files for testing
└── src/
    ├── config_generator.py               # Generate YAML report config from schema
    ├── dedup.py                          # Duplicate policy detection
    ├── excel_reporter.py                 # Excel report generation
    ├── flattener.py                      # JSON flattening (dot-notation)
    ├── schema_inferrer.py                # genson-based schema inference + comparison
    ├── schema_parser.py                  # Template schema parser (AST)
    └── validator.py                      # Structural validation
```
