# CAP Tool

Utility for evaluating Azure Conditional Access Policy (CAP) JSON dumps exported from Microsoft Graph API.

## Features

- **Generate** YAML config files for report, dedup, and similar commands
- **Validate** dump files against a reference template schema
- **Report** policies as an Excel spreadsheet with configurable columns
- **Detect duplicates** across files using configurable normalization
- **Find similar policies** ranked by fewest differences to identify merge candidates
- **Infer** a JSON Schema from your actual dumps using [genson](https://github.com/wolverdude/GenSON)
- **Compare** inferred schema vs reference to find gaps in either direction

## Setup

```bash
cd cap_tool
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Quick Start

```bash
# 1. (Optional) Infer a schema from your dumps if you don't have one
.venv/bin/python cli.py infer \
  --input-dir <policy_dir> \
  --output inferred_schema.json

# 2. Generate all config files from the schema
.venv/bin/python cli.py generate \
  --schema conditional_access_policy_schema.json \
  --output-dir .

# 3. Validate your policy dumps
.venv/bin/python cli.py validate \
  --schema conditional_access_policy_schema.json \
  --input-dir <policy_dir>

# 4. Generate an Excel report
.venv/bin/python cli.py report \
  --input-dir <policy_dir> \
  --config report_config.yaml

# 5. Find exact duplicates
.venv/bin/python cli.py dedup \
  --input-dir <policy_dir> \
  --config dedup_config.yaml

# 6. Find near-duplicates (merge candidates)
.venv/bin/python cli.py similar \
  --input-dir <policy_dir> \
  --config similar_config.yaml
```

## Commands

All commands run from the `cap_tool/` directory.

### generate

Generate YAML config files for the `report`, `dedup`, and `similar` commands. This is typically the first command you run.

```bash
.venv/bin/python cli.py generate \
  --schema conditional_access_policy_schema.json \
  --output-dir .
```

Produces three files in the output directory:

| File | Used by | Contents |
|---|---|---|
| `report_config.yaml` | `report` | All flattened schema keys, each set to `true` |
| `dedup_config.yaml` | `dedup` | Volatile fields, sort settings, detection modes |
| `similar_config.yaml` | `similar` | Ignore fields and pair display limit |

Use `--all-false` to generate `report_config.yaml` with all columns disabled (opt-in mode).

The schema can be either the CAP template format (like the included `conditional_access_policy_schema.json`) or a standard JSON Schema with `type`/`properties`/`items`.

### validate

Check that dump files conform to the reference template schema.

```bash
.venv/bin/python cli.py validate \
  --schema conditional_access_policy_schema.json \
  --input-dir <policy_dir>
```

Reports per-file: unexpected keys, missing required keys, type mismatches.

### report

Create an Excel spreadsheet from dump files. Each row is a policy, each column is a flattened key enabled in the config.

```bash
.venv/bin/python cli.py report \
  --input-dir <policy_dir> \
  --config report_config.yaml \
  --output cap_report.xlsx
```

Edit `report_config.yaml` to toggle columns `true`/`false`. Array values are written with each element on a separate line within the cell. Missing fields appear as empty cells.

### dedup

Find exact duplicate policies across files. Two files with different names, key ordering, IDs, and timestamps can still be the same policy.

```bash
.venv/bin/python cli.py dedup \
  --input-dir <policy_dir> \
  --config dedup_config.yaml
```

**Config reference** (`dedup_config.yaml`):

| Setting | Purpose |
|---|---|
| `volatile_fields` | Dot-notation paths stripped before comparing (default: `id`, `createdDateTime`, `modifiedDateTime`, `templateId`) |
| `sort_arrays` | Treat `["a","b"]` and `["b","a"]` as equal |
| `modes` | List of detection strategies to run (see below) |
| `compare_fields` | List of dot-notation paths used by `fields` mode |

**Detection modes** (set in `modes`):

| Mode | What it does |
|---|---|
| `content` | Normalizes each file (strips volatile fields, sorts keys/arrays), then hashes. Files with identical hashes are exact duplicates. |
| `id` | Groups files that share the same `id` field value. Finds the same policy exported multiple times, possibly at different dates. |
| `fields` | Like `content`, but only compares the specific keys listed in `compare_fields`. Skipped if `compare_fields` is empty. Use case: find policies targeting the same users + apps regardless of grant controls. |

### similar

Find near-duplicate policies that are candidates for merging. Compares every pair of files, counts parameter-level differences, and ranks pairs from fewest to most.

```bash
.venv/bin/python cli.py similar \
  --input-dir <policy_dir> \
  --config similar_config.yaml
```

**Config reference** (`similar_config.yaml`):

| Setting | Purpose |
|---|---|
| `ignore_fields` | Dot-notation paths to exclude from comparison (default: `id`, `createdDateTime`, `modifiedDateTime`, `templateId`) |
| `limit` | Maximum number of most-similar pairs to display (default: `5`) |

For each pair, the output lists every parameter that differs between the two policies with both values shown.

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

## Project Structure

```
cap_tool/
├── cli.py                                # CLI entry point (7 subcommands)
├── conditional_access_policy_schema.json # Reference template schema
├── requirements.txt
├── sample_caps/                          # Sample policy files for testing
└── src/
    ├── config_generator.py               # Generate all YAML configs from schema
    ├── dedup.py                          # Exact duplicate detection
    ├── excel_reporter.py                 # Excel report generation
    ├── flattener.py                      # JSON flattening (dot-notation)
    ├── schema_inferrer.py                # genson-based schema inference + comparison
    ├── schema_parser.py                  # Schema parser (CAP template + JSON Schema)
    ├── similar.py                        # Near-duplicate / merge candidate finder
    └── validator.py                      # Structural validation
```
