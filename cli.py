#!/usr/bin/env python3
"""
CAP Tool — Azure Conditional Access Policy evaluation utility.

Subcommands:
  validate   Validate JSON dump files against the template schema
  generate   Generate a YAML report config from the schema
  report     Create an Excel report from validated JSON files
  infer      Infer a JSON Schema from dump files using genson
  compare    Compare inferred schema against the reference template
  dedup      Find duplicate policies across JSON files
"""

import argparse
import sys


def cmd_validate(args):
    from src.validator import validate_directory

    results = validate_directory(args.input_dir, args.schema)

    total_errors = 0
    total_warnings = 0

    for filename, issues in results.items():
        errors = [i for i in issues if i.severity == "error"]
        warnings = [i for i in issues if i.severity == "warning"]
        total_errors += len(errors)
        total_warnings += len(warnings)

        if not issues:
            print(f"  OK  {filename}")
        else:
            status = "FAIL" if errors else "WARN"
            print(f"  {status}  {filename} ({len(errors)} errors, {len(warnings)} warnings)")
            for issue in issues:
                marker = "E" if issue.severity == "error" else "W"
                path = issue.path or "(root)"
                print(f"        [{marker}] {path}: {issue.message}")

    print(f"\nTotal: {len(results)} files, {total_errors} errors, {total_warnings} warnings")
    if total_errors > 0:
        sys.exit(1)


def cmd_generate(args):
    from src.config_generator import generate_config

    generate_config(args.schema, args.output, all_true=not args.all_false)


def cmd_report(args):
    from src.excel_reporter import generate_report

    generate_report(args.input_dir, args.config, args.output)


def cmd_infer(args):
    from src.schema_inferrer import infer_schema

    infer_schema(args.input_dir, args.output)


def cmd_compare(args):
    from src.schema_inferrer import compare_schemas

    compare_schemas(args.inferred, args.reference)


def cmd_dedup(args):
    from src.dedup import find_duplicates

    find_duplicates(args.input_dir, args.config)


def main():
    parser = argparse.ArgumentParser(
        prog="cap_tool",
        description="Azure Conditional Access Policy evaluation utility",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- validate ---
    p_val = subparsers.add_parser("validate", help="Validate JSON dumps against the template schema")
    p_val.add_argument("--schema", required=True, help="Path to the template schema JSON file")
    p_val.add_argument("--input-dir", required=True, help="Directory containing CAP JSON dump files")
    p_val.set_defaults(func=cmd_validate)

    # --- generate ---
    p_gen = subparsers.add_parser("generate", help="Generate a YAML report config from the schema")
    p_gen.add_argument("--schema", required=True, help="Path to the template schema JSON file")
    p_gen.add_argument("--output", default="report_config.yaml", help="Output YAML config file path")
    p_gen.add_argument("--all-false", action="store_true", help="Set all columns to false (opt-in mode)")
    p_gen.set_defaults(func=cmd_generate)

    # --- report ---
    p_rep = subparsers.add_parser("report", help="Create an Excel report from JSON files + YAML config")
    p_rep.add_argument("--input-dir", required=True, help="Directory containing validated CAP JSON files")
    p_rep.add_argument("--config", required=True, help="Path to the YAML report config file")
    p_rep.add_argument("--output", default="cap_report.xlsx", help="Output Excel file path")
    p_rep.set_defaults(func=cmd_report)

    # --- infer ---
    p_inf = subparsers.add_parser("infer", help="Infer a JSON Schema from dump files using genson")
    p_inf.add_argument("--input-dir", required=True, help="Directory containing CAP JSON dump files")
    p_inf.add_argument("--output", default="inferred_schema.json", help="Output JSON Schema file path")
    p_inf.set_defaults(func=cmd_infer)

    # --- compare ---
    p_cmp = subparsers.add_parser("compare", help="Compare inferred schema against the reference template")
    p_cmp.add_argument("--inferred", required=True, help="Path to the genson-inferred JSON Schema")
    p_cmp.add_argument("--reference", required=True, help="Path to the reference template schema")
    p_cmp.set_defaults(func=cmd_compare)

    # --- dedup ---
    p_dup = subparsers.add_parser("dedup", help="Find duplicate policies across JSON files")
    p_dup.add_argument("--input-dir", required=True, help="Directory containing CAP JSON dump files")
    p_dup.add_argument("--config", default="dedup_config.yaml", help="Path to the dedup YAML config file")
    p_dup.set_defaults(func=cmd_dedup)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
