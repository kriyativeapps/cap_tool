#!/usr/bin/env python3
"""
CAP Tool GUI — Tkinter frontend for the cap_tool CLI.

Launch with:  python gui.py
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext
from pathlib import Path

# ---------------------------------------------------------------------------
# Resolve paths relative to this script so imports work when launched from
# any working directory.
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
os.chdir(SCRIPT_DIR)
sys.path.insert(0, str(SCRIPT_DIR))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _browse_dir(var):
    """Open a directory chooser and write the result into *var*."""
    path = filedialog.askdirectory(initialdir=var.get() or ".")
    if path:
        var.set(path)


def _browse_file_open(var, filetypes=None):
    """Open a file chooser (open mode) and write the result into *var*."""
    ft = filetypes or [("All files", "*.*")]
    path = filedialog.askopenfilename(initialdir=str(Path(var.get()).parent) if var.get() else ".",
                                      filetypes=ft)
    if path:
        var.set(path)


def _browse_file_save(var, filetypes=None, default_ext=None):
    """Open a file chooser (save mode) and write the result into *var*."""
    ft = filetypes or [("All files", "*.*")]
    path = filedialog.asksaveasfilename(initialdir=str(Path(var.get()).parent) if var.get() else ".",
                                        filetypes=ft,
                                        defaultextension=default_ext)
    if path:
        var.set(path)


JSON_FT = [("JSON files", "*.json"), ("All files", "*.*")]
YAML_FT = [("YAML files", "*.yaml *.yml"), ("All files", "*.*")]
XLSX_FT = [("Excel files", "*.xlsx"), ("All files", "*.*")]


# ---------------------------------------------------------------------------
# Row builder — keeps the grid layout consistent
# ---------------------------------------------------------------------------

def _add_path_row(parent, row, label_text, var, browse_fn, browse_kw=None):
    """Add a label + entry + Browse button on *row* inside *parent*."""
    ttk.Label(parent, text=label_text).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=6)
    ent = ttk.Entry(parent, textvariable=var, width=60)
    ent.grid(row=row, column=1, sticky="ew", pady=6)
    btn = ttk.Button(parent, text="Browse\u2026",
                     command=lambda: browse_fn(var, **(browse_kw or {})))
    btn.grid(row=row, column=2, padx=(8, 0), pady=6)
    return ent


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------

class CapToolGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CAP Tool")
        self.minsize(700, 520)

        # --- Notebook (tabs) ---
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=(10, 0))

        self._build_infer_tab(notebook)
        self._build_generate_tab(notebook)
        self._build_dedup_tab(notebook)
        self._build_similar_tab(notebook)
        self._build_report_tab(notebook)

        # --- Output console (shared) ---
        out_frame = ttk.LabelFrame(self, text="Output")
        out_frame.pack(fill="both", expand=True, padx=6, pady=6)

        self.output = scrolledtext.ScrolledText(out_frame, height=12, state="disabled",
                                                wrap="word", font=("Consolas", 10))
        self.output.pack(fill="both", expand=True, padx=4, pady=4)

        btn_frame = ttk.Frame(out_frame)
        btn_frame.pack(fill="x", padx=4, pady=(0, 4))
        ttk.Button(btn_frame, text="Clear", command=self._clear_output).pack(side="right")

    # ------------------------------------------------------------------
    # Tab builders
    # ------------------------------------------------------------------

    def _build_generate_tab(self, nb):
        f = ttk.Frame(nb, padding=20)
        nb.add(f, text="  Generate  ")
        f.columnconfigure(1, weight=1)

        self.gen_schema = tk.StringVar(value="conditional_access_policy_schema.json")
        self.gen_outdir = tk.StringVar(value=".")
        self.gen_allfalse = tk.BooleanVar()

        _add_path_row(f, 0, "Schema:", self.gen_schema, _browse_file_open, {"filetypes": JSON_FT})
        _add_path_row(f, 1, "Output dir:", self.gen_outdir, _browse_dir)
        ttk.Checkbutton(f, text="All false (opt-in mode)", variable=self.gen_allfalse).grid(
            row=2, column=1, sticky="w", pady=8)
        ttk.Button(f, text="Run Generate", command=self._run_generate).grid(
            row=3, column=1, sticky="e", pady=(12, 0))

    def _build_validate_tab(self, nb):
        f = ttk.Frame(nb, padding=20)
        nb.add(f, text="  Validate  ")
        f.columnconfigure(1, weight=1)

        self.val_schema = tk.StringVar(value="conditional_access_policy_schema.json")
        self.val_indir = tk.StringVar()

        _add_path_row(f, 0, "Schema:", self.val_schema, _browse_file_open, {"filetypes": JSON_FT})
        _add_path_row(f, 1, "Input dir:", self.val_indir, _browse_dir)
        ttk.Button(f, text="Run Validate", command=self._run_validate).grid(
            row=2, column=1, sticky="e", pady=(12, 0))

    def _build_report_tab(self, nb):
        f = ttk.Frame(nb, padding=20)
        nb.add(f, text="  Report  ")
        f.columnconfigure(1, weight=1)

        self.rep_indir = tk.StringVar()
        self.rep_config = tk.StringVar(value="report_config.yaml")
        self.rep_output = tk.StringVar(value="cap_report.xlsx")

        _add_path_row(f, 0, "Input dir:", self.rep_indir, _browse_dir)
        _add_path_row(f, 1, "Config:", self.rep_config, _browse_file_open, {"filetypes": YAML_FT})
        _add_path_row(f, 2, "Output:", self.rep_output, _browse_file_save,
                      {"filetypes": XLSX_FT, "default_ext": ".xlsx"})
        ttk.Button(f, text="Run Report", command=self._run_report).grid(
            row=3, column=1, sticky="e", pady=(12, 0))

    def _build_dedup_tab(self, nb):
        f = ttk.Frame(nb, padding=20)
        nb.add(f, text="  Dedup  ")
        f.columnconfigure(1, weight=1)

        self.dup_indir = tk.StringVar()
        self.dup_config = tk.StringVar(value="dedup_config.yaml")

        _add_path_row(f, 0, "Input dir:", self.dup_indir, _browse_dir)
        _add_path_row(f, 1, "Config:", self.dup_config, _browse_file_open, {"filetypes": YAML_FT})
        ttk.Button(f, text="Run Dedup", command=self._run_dedup).grid(
            row=2, column=1, sticky="e", pady=(12, 0))

    def _build_similar_tab(self, nb):
        f = ttk.Frame(nb, padding=20)
        nb.add(f, text="  Similar  ")
        f.columnconfigure(1, weight=1)

        self.sim_indir = tk.StringVar()
        self.sim_config = tk.StringVar(value="similar_config.yaml")

        _add_path_row(f, 0, "Input dir:", self.sim_indir, _browse_dir)
        _add_path_row(f, 1, "Config:", self.sim_config, _browse_file_open, {"filetypes": YAML_FT})
        ttk.Button(f, text="Run Similar", command=self._run_similar).grid(
            row=2, column=1, sticky="e", pady=(12, 0))

    def _build_infer_tab(self, nb):
        f = ttk.Frame(nb, padding=20)
        nb.add(f, text="  Infer  ")
        f.columnconfigure(1, weight=1)

        self.inf_indir = tk.StringVar()
        self.inf_output = tk.StringVar(value="inferred_schema.json")

        _add_path_row(f, 0, "Input dir:", self.inf_indir, _browse_dir)
        _add_path_row(f, 1, "Output:", self.inf_output, _browse_file_save,
                      {"filetypes": JSON_FT, "default_ext": ".json"})
        ttk.Button(f, text="Run Infer", command=self._run_infer).grid(
            row=2, column=1, sticky="e", pady=(12, 0))

    def _build_compare_tab(self, nb):
        f = ttk.Frame(nb, padding=20)
        nb.add(f, text="  Compare  ")
        f.columnconfigure(1, weight=1)

        self.cmp_inferred = tk.StringVar()
        self.cmp_reference = tk.StringVar(value="conditional_access_policy_schema.json")

        _add_path_row(f, 0, "Inferred:", self.cmp_inferred, _browse_file_open, {"filetypes": JSON_FT})
        _add_path_row(f, 1, "Reference:", self.cmp_reference, _browse_file_open, {"filetypes": JSON_FT})
        ttk.Button(f, text="Run Compare", command=self._run_compare).grid(
            row=2, column=1, sticky="e", pady=(12, 0))

    # ------------------------------------------------------------------
    # Output helpers
    # ------------------------------------------------------------------

    def _clear_output(self):
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.configure(state="disabled")

    def _append_output(self, text):
        self.output.configure(state="normal")
        self.output.insert("end", text)
        self.output.see("end")
        self.output.configure(state="disabled")

    # ------------------------------------------------------------------
    # Runner — executes CLI functions in a background thread so the GUI
    # stays responsive.  stdout/stderr are captured.
    # ------------------------------------------------------------------

    def _run_in_thread(self, label, func):
        """Run *func* in a background thread, capturing print output."""
        self._clear_output()
        self._append_output(f"--- {label} ---\n")

        def worker():
            import io
            import contextlib

            buf = io.StringIO()
            try:
                with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                    func()
                self.after(0, self._append_output, buf.getvalue())
                self.after(0, self._append_output, "\nDone.\n")
            except SystemExit:
                self.after(0, self._append_output, buf.getvalue())
                self.after(0, self._append_output, "\nFinished (with errors — see above).\n")
            except Exception as exc:
                self.after(0, self._append_output, buf.getvalue())
                self.after(0, self._append_output, f"\nERROR: {exc}\n")

        threading.Thread(target=worker, daemon=True).start()

    # ------------------------------------------------------------------
    # Command wrappers
    # ------------------------------------------------------------------

    def _run_generate(self):
        schema, outdir = self.gen_schema.get(), self.gen_outdir.get()
        all_false = self.gen_allfalse.get()

        def go():
            from src.config_generator import generate_configs
            generate_configs(schema, outdir, all_true=not all_false)

        self._run_in_thread("generate", go)

    def _run_validate(self):
        schema, indir = self.val_schema.get(), self.val_indir.get()

        def go():
            from src.validator import validate_directory
            from cli import cmd_validate
            import argparse
            ns = argparse.Namespace(schema=schema, input_dir=indir)
            cmd_validate(ns)

        self._run_in_thread("validate", go)

    def _run_report(self):
        indir = self.rep_indir.get()
        config = self.rep_config.get()
        output = self.rep_output.get()

        def go():
            from src.excel_reporter import generate_report
            generate_report(indir, config, output)

        self._run_in_thread("report", go)

    def _run_dedup(self):
        indir, config = self.dup_indir.get(), self.dup_config.get()

        def go():
            from src.dedup import find_duplicates
            find_duplicates(indir, config)

        self._run_in_thread("dedup", go)

    def _run_similar(self):
        indir, config = self.sim_indir.get(), self.sim_config.get()

        def go():
            from src.similar import find_similar
            find_similar(indir, config)

        self._run_in_thread("similar", go)

    def _run_infer(self):
        indir, output = self.inf_indir.get(), self.inf_output.get()

        def go():
            from src.schema_inferrer import infer_schema
            infer_schema(indir, output)

        self._run_in_thread("infer", go)

    def _run_compare(self):
        inferred, reference = self.cmp_inferred.get(), self.cmp_reference.get()

        def go():
            from src.schema_inferrer import compare_schemas
            compare_schemas(inferred, reference)

        self._run_in_thread("compare", go)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = CapToolGUI()
    app.mainloop()
