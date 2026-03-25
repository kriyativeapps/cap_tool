#!/usr/bin/env python3
"""
CAP Tool GUI — Tkinter frontend for the cap_tool CLI.

Launch with:  python gui.py
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
from pathlib import Path

import yaml

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
    path = filedialog.askdirectory(initialdir=var.get() or str(SCRIPT_DIR), mustexist=False)
    if path:
        var.set(str(Path(path).resolve()))


def _browse_file_open(var, filetypes=None):
    """Open a file chooser (open mode) and write the result into *var*."""
    ft = filetypes or [("All files", "*.*")]
    init = str(Path(var.get()).parent) if var.get() else str(SCRIPT_DIR)
    path = filedialog.askopenfilename(initialdir=init, filetypes=ft)
    if path:
        var.set(str(Path(path).resolve()))


def _browse_file_save(var, filetypes=None, default_ext=None):
    """Open a file chooser (save mode) and write the result into *var*."""
    ft = filetypes or [("All files", "*.*")]
    init = str(Path(var.get()).parent) if var.get() else str(SCRIPT_DIR)
    path = filedialog.asksaveasfilename(initialdir=init, filetypes=ft,
                                        defaultextension=default_ext)
    if path:
        var.set(str(Path(path).resolve()))


JSON_FT = [("JSON files", "*.json"), ("All files", "*.*")]
YAML_FT = [("YAML files", "*.yaml *.yml"), ("All files", "*.*")]
XLSX_FT = [("Excel files", "*.xlsx"), ("All files", "*.*")]


# ---------------------------------------------------------------------------
# Row builder — keeps the grid layout consistent
# ---------------------------------------------------------------------------

def _add_path_row(parent, row, label_text, var, browse_fn, browse_kw=None):
    """Add a label + entry + Browse button on *row* inside *parent*."""
    ttk.Label(parent, text=label_text).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=6)
    ent = ttk.Entry(parent, textvariable=var, width=80)
    ent.grid(row=row, column=1, sticky="ew", pady=6)
    btn = ttk.Button(parent, text="Browse\u2026",
                     command=lambda: browse_fn(var, **(browse_kw or {})))
    btn.grid(row=row, column=2, padx=(8, 0), pady=6)
    return ent


# ---------------------------------------------------------------------------
# FieldEditor — reusable scrollable checkbox list for field selection
# ---------------------------------------------------------------------------

class FieldEditor(ttk.LabelFrame):
    """Scrollable checkbox list for selecting/deselecting config fields."""

    def __init__(self, parent, title="Fields"):
        super().__init__(parent, text=title, padding=5)

        # Toolbar
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", pady=(0, 4))
        ttk.Button(toolbar, text="Select All", command=self._select_all).pack(side="left", padx=(0, 4))
        ttk.Button(toolbar, text="Deselect All", command=self._deselect_all).pack(side="left")

        # Scrollable area
        container = ttk.Frame(self)
        container.pack(fill="both", expand=True)

        self._canvas = tk.Canvas(container, highlightthickness=0, borderwidth=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=self._canvas.yview)
        self._inner = ttk.Frame(self._canvas)

        self._inner.bind("<Configure>",
                         lambda _: self._canvas.configure(scrollregion=self._canvas.bbox("all")))
        self._canvas_win = self._canvas.create_window((0, 0), window=self._inner, anchor="nw")
        self._canvas.configure(yscrollcommand=scrollbar.set)

        self._canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Resize inner frame width to match canvas
        self._canvas.bind("<Configure>", self._on_canvas_resize)

        # Mouse wheel scrolling
        self._canvas.bind("<Enter>", lambda _: self._bind_mousewheel())
        self._canvas.bind("<Leave>", lambda _: self._unbind_mousewheel())

        self._vars: dict[str, tk.BooleanVar] = {}
        self._widgets: list[tk.Widget] = []

    def _on_canvas_resize(self, event):
        self._canvas.itemconfigure(self._canvas_win, width=event.width)

    def _bind_mousewheel(self):
        self._canvas.bind_all("<Button-4>", self._on_mousewheel)
        self._canvas.bind_all("<Button-5>", self._on_mousewheel)

    def _unbind_mousewheel(self):
        self._canvas.unbind_all("<Button-4>")
        self._canvas.unbind_all("<Button-5>")

    def _on_mousewheel(self, event):
        self._canvas.yview_scroll(-3 if event.num == 4 else 3, "units")

    def load(self, fields: dict[str, bool]):
        """Populate checkboxes from a {field_path: bool} dict."""
        self.clear()
        for path, enabled in fields.items():
            var = tk.BooleanVar(value=enabled)
            cb = ttk.Checkbutton(self._inner, text=path, variable=var)
            cb.pack(anchor="w", padx=4, pady=1)
            self._vars[path] = var
            self._widgets.append(cb)

    def get(self) -> dict[str, bool]:
        """Return current state as {field_path: bool}."""
        return {path: var.get() for path, var in self._vars.items()}

    def clear(self):
        for w in self._widgets:
            w.destroy()
        self._widgets.clear()
        self._vars.clear()

    def is_empty(self) -> bool:
        return len(self._vars) == 0

    def _select_all(self):
        for var in self._vars.values():
            var.set(True)

    def _deselect_all(self):
        for var in self._vars.values():
            var.set(False)


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------

class CapToolGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CAP Tool")
        self.minsize(900, 650)

        # --- Shared input dir — set in Infer, auto-populates other tabs ---
        self.shared_indir = tk.StringVar()
        self.shared_indir.trace_add("write", self._on_shared_indir_changed)

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

        self.output = scrolledtext.ScrolledText(out_frame, height=10, state="disabled",
                                                wrap="word", font=("Consolas", 10))
        self.output.pack(fill="both", expand=True, padx=4, pady=4)

        btn_frame = ttk.Frame(out_frame)
        btn_frame.pack(fill="x", padx=4, pady=(0, 4))
        ttk.Button(btn_frame, text="Clear", command=self._clear_output).pack(side="right")

    # ------------------------------------------------------------------
    # Shared input dir propagation
    # ------------------------------------------------------------------

    def _on_shared_indir_changed(self, *_args):
        """When Infer's input dir changes, auto-fill empty input dirs."""
        val = self.shared_indir.get()
        if not val:
            return
        for var in (self.dup_indir, self.sim_indir, self.rep_indir):
            if not var.get():
                var.set(val)

    # ------------------------------------------------------------------
    # Tab builders
    # ------------------------------------------------------------------

    def _build_infer_tab(self, nb):
        f = ttk.Frame(nb, padding=20)
        nb.add(f, text="  Infer  ")
        f.columnconfigure(1, weight=1)

        self.inf_output = tk.StringVar(value=str(SCRIPT_DIR / "inferred_schema.json"))

        _add_path_row(f, 0, "Input dir:", self.shared_indir, _browse_dir)
        _add_path_row(f, 1, "Output:", self.inf_output, _browse_file_save,
                      {"filetypes": JSON_FT, "default_ext": ".json"})
        ttk.Button(f, text="Run Infer", command=self._run_infer).grid(
            row=2, column=1, sticky="e", pady=(12, 0))

    def _build_generate_tab(self, nb):
        f = ttk.Frame(nb, padding=20)
        nb.add(f, text="  Generate  ")
        f.columnconfigure(1, weight=1)

        self.gen_schema = tk.StringVar(value=str(SCRIPT_DIR / "conditional_access_policy_schema.json"))
        self.gen_outdir = tk.StringVar(value=str(SCRIPT_DIR))
        self.gen_allfalse = tk.BooleanVar()

        _add_path_row(f, 0, "Schema:", self.gen_schema, _browse_file_open, {"filetypes": JSON_FT})
        _add_path_row(f, 1, "Output dir:", self.gen_outdir, _browse_dir)
        ttk.Checkbutton(f, text="All false (opt-in mode)", variable=self.gen_allfalse).grid(
            row=2, column=1, sticky="w", pady=8)
        ttk.Button(f, text="Run Generate", command=self._run_generate).grid(
            row=3, column=1, sticky="e", pady=(12, 0))

    def _build_dedup_tab(self, nb):
        f = ttk.Frame(nb, padding=20)
        nb.add(f, text="  Dedup  ")
        f.columnconfigure(1, weight=1)

        self.dup_indir = tk.StringVar()
        self.dup_config = tk.StringVar(value=str(SCRIPT_DIR / "dedup_config.yaml"))

        _add_path_row(f, 0, "Input dir:", self.dup_indir, _browse_dir)

        # Config row with Load / Save buttons
        ttk.Label(f, text="Config:").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=6)
        ttk.Entry(f, textvariable=self.dup_config, width=80).grid(row=1, column=1, sticky="ew", pady=6)
        cfg_btns = ttk.Frame(f)
        cfg_btns.grid(row=1, column=2, padx=(8, 0), pady=6)
        ttk.Button(cfg_btns, text="Browse\u2026",
                   command=lambda: _browse_file_open(self.dup_config, filetypes=YAML_FT)).pack(side="left", padx=(0, 2))
        ttk.Button(cfg_btns, text="Load", command=self._load_dedup_config).pack(side="left", padx=2)
        ttk.Button(cfg_btns, text="Save", command=self._save_dedup_config).pack(side="left", padx=2)

        # Single field editor — checked = excluded from comparison
        self.dup_editor = FieldEditor(f, title="Exclude Fields (checked = ignored during comparison)")
        self.dup_editor.grid(row=2, column=0, columnspan=3, sticky="nsew", pady=(8, 0))
        f.rowconfigure(2, weight=1)

        ttk.Button(f, text="Run Dedup", command=self._run_dedup).grid(
            row=3, column=1, columnspan=2, sticky="e", pady=(10, 0))

    def _build_similar_tab(self, nb):
        f = ttk.Frame(nb, padding=20)
        nb.add(f, text="  Similar  ")
        f.columnconfigure(1, weight=1)

        self.sim_indir = tk.StringVar()
        self.sim_config = tk.StringVar(value=str(SCRIPT_DIR / "similar_config.yaml"))

        _add_path_row(f, 0, "Input dir:", self.sim_indir, _browse_dir)

        # Config row with Load / Save buttons
        ttk.Label(f, text="Config:").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=6)
        ttk.Entry(f, textvariable=self.sim_config, width=80).grid(row=1, column=1, sticky="ew", pady=6)
        cfg_btns = ttk.Frame(f)
        cfg_btns.grid(row=1, column=2, padx=(8, 0), pady=6)
        ttk.Button(cfg_btns, text="Browse\u2026",
                   command=lambda: _browse_file_open(self.sim_config, filetypes=YAML_FT)).pack(side="left", padx=(0, 2))
        ttk.Button(cfg_btns, text="Load", command=self._load_similar_config).pack(side="left", padx=2)
        ttk.Button(cfg_btns, text="Save", command=self._save_similar_config).pack(side="left", padx=2)

        # Field editor for ignore_fields
        self.sim_editor = FieldEditor(f, title="Exclude Fields (checked = ignored during comparison)")
        self.sim_editor.grid(row=2, column=0, columnspan=3, sticky="nsew", pady=(8, 0))
        f.rowconfigure(2, weight=1)

        ttk.Button(f, text="Run Similar", command=self._run_similar).grid(
            row=3, column=1, columnspan=2, sticky="e", pady=(10, 0))

    def _build_report_tab(self, nb):
        f = ttk.Frame(nb, padding=20)
        nb.add(f, text="  Report  ")
        f.columnconfigure(1, weight=1)

        self.rep_indir = tk.StringVar()
        self.rep_config = tk.StringVar(value=str(SCRIPT_DIR / "report_config.yaml"))
        self.rep_output = tk.StringVar(value=str(SCRIPT_DIR / "cap_report.xlsx"))

        _add_path_row(f, 0, "Input dir:", self.rep_indir, _browse_dir)

        # Config row with Load / Save buttons
        ttk.Label(f, text="Config:").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=6)
        ttk.Entry(f, textvariable=self.rep_config, width=80).grid(row=1, column=1, sticky="ew", pady=6)
        cfg_btns = ttk.Frame(f)
        cfg_btns.grid(row=1, column=2, padx=(8, 0), pady=6)
        ttk.Button(cfg_btns, text="Browse\u2026",
                   command=lambda: _browse_file_open(self.rep_config, filetypes=YAML_FT)).pack(side="left", padx=(0, 2))
        ttk.Button(cfg_btns, text="Load", command=self._load_report_config).pack(side="left", padx=2)
        ttk.Button(cfg_btns, text="Save", command=self._save_report_config).pack(side="left", padx=2)

        _add_path_row(f, 2, "Output:", self.rep_output, _browse_file_save,
                      {"filetypes": XLSX_FT, "default_ext": ".xlsx"})

        # Field editor for columns
        self.rep_editor = FieldEditor(f, title="Columns (checked = include in report)")
        self.rep_editor.grid(row=3, column=0, columnspan=3, sticky="nsew", pady=(8, 0))
        f.rowconfigure(3, weight=1)

        ttk.Button(f, text="Run Report", command=self._run_report).grid(
            row=4, column=1, columnspan=2, sticky="e", pady=(10, 0))

    def _build_compare_tab(self, nb):
        f = ttk.Frame(nb, padding=20)
        nb.add(f, text="  Compare  ")
        f.columnconfigure(1, weight=1)

        self.cmp_inferred = tk.StringVar()
        self.cmp_reference = tk.StringVar(value=str(SCRIPT_DIR / "conditional_access_policy_schema.json"))

        _add_path_row(f, 0, "Inferred:", self.cmp_inferred, _browse_file_open, {"filetypes": JSON_FT})
        _add_path_row(f, 1, "Reference:", self.cmp_reference, _browse_file_open, {"filetypes": JSON_FT})
        ttk.Button(f, text="Run Compare", command=self._run_compare).grid(
            row=2, column=1, sticky="e", pady=(12, 0))

    # ------------------------------------------------------------------
    # Config load / save helpers
    # ------------------------------------------------------------------

    def _load_yaml(self, path_var: tk.StringVar) -> dict | None:
        """Load a YAML file, showing an error dialog on failure."""
        cfg_path = path_var.get()
        if not cfg_path or not Path(cfg_path).is_file():
            messagebox.showerror("Load Config", f"File not found:\n{cfg_path}")
            return None
        with open(cfg_path, encoding="utf-8-sig") as f:
            return yaml.safe_load(f) or {}

    def _save_yaml(self, path_var: tk.StringVar, data: dict, header: str = ""):
        """Write a YAML file, showing an error dialog on failure."""
        cfg_path = path_var.get()
        if not cfg_path:
            messagebox.showerror("Save Config", "No config path specified.")
            return
        with open(cfg_path, "w", encoding="utf-8") as f:
            if header:
                f.write(header)
            yaml.dump(data, f, default_flow_style=False, sort_keys=False, width=120)
        self._append_output(f"Saved: {cfg_path}\n")

    @staticmethod
    def _fields_from_raw(raw, all_paths: list[str] | None = None) -> dict[str, bool]:
        """Convert a list or dict field spec to a {path: bool} dict.

        If *raw* is a list, items in the list are True; if *all_paths* is
        provided, remaining paths are added as False.
        """
        if isinstance(raw, dict):
            return {k: bool(v) for k, v in raw.items()}
        # Legacy list format
        active = set(raw) if raw else set()
        if all_paths:
            return {p: (p in active) for p in all_paths}
        return {p: True for p in active}

    # --- Report ---

    def _load_report_config(self):
        config = self._load_yaml(self.rep_config)
        if config is None:
            return
        columns = config.get("columns", {})
        fields = self._fields_from_raw(columns)
        self.rep_editor.load(fields)

    def _save_report_config(self):
        if self.rep_editor.is_empty():
            messagebox.showinfo("Save Config", "No fields loaded. Click Load first.")
            return
        config = self._load_yaml(self.rep_config) or {}
        config["columns"] = self.rep_editor.get()
        header = ("# Report Configuration\n"
                  "# Set keys to false to exclude from the Excel report.\n\n")
        self._save_yaml(self.rep_config, config, header)

    # --- Dedup ---

    def _load_dedup_config(self):
        config = self._load_yaml(self.dup_config)
        if config is None:
            return
        # Merge volatile_fields and compare_fields into a single "exclude" view.
        # A field is "excluded" if it appears in volatile_fields (checked=true).
        volatile = self._fields_from_raw(config.get("volatile_fields", []))
        self.dup_editor.load(volatile)

    def _save_dedup_config(self):
        if self.dup_editor.is_empty():
            messagebox.showinfo("Save Config", "No fields loaded. Click Load first.")
            return
        config = self._load_yaml(self.dup_config) or {}
        config["volatile_fields"] = self.dup_editor.get()
        header = ("# Deduplication Configuration\n"
                  "# Controls how policies are normalized before comparison.\n\n")
        self._save_yaml(self.dup_config, config, header)

    # --- Similar ---

    def _load_similar_config(self):
        config = self._load_yaml(self.sim_config)
        if config is None:
            return
        ignore = self._fields_from_raw(config.get("ignore_fields", []))
        self.sim_editor.load(ignore)

    def _save_similar_config(self):
        if self.sim_editor.is_empty():
            messagebox.showinfo("Save Config", "No fields loaded. Click Load first.")
            return
        config = self._load_yaml(self.sim_config) or {}
        config["ignore_fields"] = self.sim_editor.get()
        header = ("# Similar Policy Finder Configuration\n"
                  "# Compares policy pairs and ranks by fewest differences.\n\n")
        self._save_yaml(self.sim_config, config, header)

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

    def _run_in_thread(self, label, func, on_done=None):
        """Run *func* in a background thread, capturing print output.

        *on_done* is called on the main thread after successful completion.
        """
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
                if on_done:
                    self.after(0, on_done)
            except SystemExit:
                self.after(0, self._append_output, buf.getvalue())
                self.after(0, self._append_output, "\nFinished (with errors — see above).\n")
            except Exception as exc:
                import traceback
                self.after(0, self._append_output, buf.getvalue())
                self.after(0, self._append_output, f"\nERROR: {exc}\n{traceback.format_exc()}\n")

        threading.Thread(target=worker, daemon=True).start()

    # ------------------------------------------------------------------
    # Command wrappers
    # ------------------------------------------------------------------

    def _run_generate(self):
        schema, outdir = self.gen_schema.get(), self.gen_outdir.get()
        all_false = self.gen_allfalse.get()

        # Resolve to absolute path and auto-create if needed
        outdir_abs = str(Path(outdir).resolve())
        Path(outdir_abs).mkdir(parents=True, exist_ok=True)

        def go():
            from src.config_generator import generate_configs
            generate_configs(schema, outdir_abs, all_true=not all_false)

        def on_done():
            # Auto-populate config paths in other tabs with generated files
            out = Path(outdir_abs)
            dedup_cfg = out / "dedup_config.yaml"
            similar_cfg = out / "similar_config.yaml"
            report_cfg = out / "report_config.yaml"
            if dedup_cfg.is_file():
                self.dup_config.set(str(dedup_cfg))
            if similar_cfg.is_file():
                self.sim_config.set(str(similar_cfg))
            if report_cfg.is_file():
                self.rep_config.set(str(report_cfg))

        self._run_in_thread("generate", go, on_done=on_done)

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

        # Auto-create parent directory for output file
        Path(output).parent.mkdir(parents=True, exist_ok=True)

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
        indir = self.shared_indir.get()
        output = self.inf_output.get()

        # Resolve relative output path against input dir
        out_path = Path(output)
        if not out_path.is_absolute() and indir:
            out_path = Path(indir) / out_path
        out_path = out_path.resolve()

        # Auto-create parent directories
        out_path.parent.mkdir(parents=True, exist_ok=True)

        def go():
            from src.schema_inferrer import infer_schema
            print(f"Input dir:   {indir}")
            print(f"Output file: {out_path}")
            print(f"Dir exists:  {Path(indir).is_dir() if indir else 'N/A'}")
            json_files = list(Path(indir).glob("*.json")) if indir and Path(indir).is_dir() else []
            print(f"JSON files:  {len(json_files)}")
            for jf in json_files:
                print(f"  - {jf.name}")
            print()
            infer_schema(indir, str(out_path))

        def on_done():
            # Auto-populate Generate's schema with the inferred output
            self.gen_schema.set(str(out_path))

        self._run_in_thread("infer", go, on_done=on_done)

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
