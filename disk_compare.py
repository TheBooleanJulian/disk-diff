"""
DiskDiff — Disk Comparison & Sync Tool
TheBooleanJulian

Usage:
    python disk_compare.py

Requirements:
    Python 3.8+  (tkinter is stdlib)
    Fonts (auto-resolved with fallback):
        Monospace : JetBrains Mono → Cascadia Code → Fira Code → Courier New
        UI/Heading: Space Grotesk  → Outfit → Syne → Segoe UI
"""

import os
import sys
import hashlib
import threading
import subprocess
import shutil
from pathlib import Path
from collections import defaultdict
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime


# ─────────────────────────────────────────────
# THEME — TheBooleanJulian design system
# ─────────────────────────────────────────────
BG         = "#0a0e14"
BG2        = "#111720"
BG3        = "#1a2233"
ACCENT     = "#00d4c8"
ACCENT_DIM = "#00a09a"
SURFACE2   = "#0d2233"    # secondary button surface (deep navy — no purple)
TEXT       = "#e8edf5"
TEXT_DIM   = "#7a8ba0"
RED        = "#ff4f6a"
YELLOW     = "#f5c842"
GREEN      = "#3ddc84"
TEAL_LITE  = "#4dd9d4"    # lighter teal for duplicates (was purple — removed)
BORDER     = "#1e2d40"

# Font stacks — resolved once after Tk() starts
_MONO_STACK    = ["JetBrains Mono", "JetBrainsMono NF", "JetBrainsMono",
                  "Cascadia Code", "Cascadia Mono", "Fira Code",
                  "Consolas", "Courier New"]
_UI_STACK      = ["Space Grotesk", "Outfit", "Syne", "Nunito",
                  "DM Sans", "Segoe UI", "Helvetica Neue", "Arial"]

# Module-level font tuples — overwritten by resolve_fonts()
FONT_MONO     = ("Courier New",  9)
FONT_MONO_XS  = ("Courier New",  7)
FONT_MONO_SM  = ("Courier New",  8, "bold")
FONT_MONO_MD  = ("Courier New",  9, "bold")
FONT_MONO_LG  = ("Courier New", 14, "bold")
FONT_BRAND    = ("Courier New", 15, "bold")
FONT_UI       = ("Segoe UI",    10)
FONT_UI_SM    = ("Segoe UI",     9)
FONT_H1       = ("Segoe UI",    13, "bold")
FONT_H2       = ("Segoe UI",    11, "bold")


def resolve_fonts():
    """Call once after Tk() is created — picks best installed font from each stack."""
    global FONT_MONO, FONT_MONO_XS, FONT_MONO_SM, FONT_MONO_MD, FONT_MONO_LG
    global FONT_BRAND, FONT_UI, FONT_UI_SM, FONT_H1, FONT_H2
    from tkinter import font as tkfont
    available = set(tkfont.families())

    def pick(stack):
        for f in stack:
            if f in available:
                return f
        return stack[-1]

    mono = pick(_MONO_STACK)
    ui   = pick(_UI_STACK)

    FONT_MONO     = (mono,  9)
    FONT_MONO_XS  = (mono,  7)
    FONT_MONO_SM  = (mono,  8, "bold")
    FONT_MONO_MD  = (mono,  9, "bold")
    FONT_MONO_LG  = (mono, 14, "bold")
    FONT_BRAND    = (mono, 15, "bold")
    FONT_UI       = (ui,   10)
    FONT_UI_SM    = (ui,    9)
    FONT_H1       = (ui,   13, "bold")
    FONT_H2       = (ui,   11, "bold")


# ─────────────────────────────────────────────
# CORE LOGIC
# ─────────────────────────────────────────────

def format_size(n_bytes):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n_bytes < 1024:
            return f"{n_bytes:.1f} {unit}"
        n_bytes /= 1024
    return f"{n_bytes:.1f} PB"


def file_checksum(path, algorithm="md5"):
    h = hashlib.new(algorithm)
    try:
        with open(path, "rb") as f:
            while chunk := f.read(1 << 20):
                h.update(chunk)
    except (PermissionError, OSError):
        return None
    return h.hexdigest()


def scan_directory(root):
    root = Path(root)
    files = {}
    errors = []
    total_size = 0
    for abs_path in root.rglob("*"):
        if abs_path.is_file():
            try:
                rel = str(abs_path.relative_to(root))
                size = abs_path.stat().st_size
                mtime = abs_path.stat().st_mtime
                files[rel] = {"abs": str(abs_path), "size": size, "mtime": mtime}
                total_size += size
            except Exception as e:
                errors.append(str(e))
    return files, total_size, errors


def compare_directories(src_files, dst_files, checksum_cb=None, case_insensitive=None):
    """Compare two scanned file maps.

    case_insensitive: match relative paths ignoring case (default: True on
    Windows, since NTFS is case-insensitive and cloud-sync tools frequently
    re-case files, which would otherwise show up as false missing/extra pairs).
    """
    if case_insensitive is None:
        case_insensitive = (sys.platform == "win32")

    def key(rel):
        return rel.lower() if case_insensitive else rel

    src_index = {}
    for rel in src_files:
        src_index.setdefault(key(rel), rel)
    dst_index = {}
    for rel in dst_files:
        dst_index.setdefault(key(rel), rel)

    src_keys = set(src_index)
    dst_keys = set(dst_index)

    only_in_src      = sorted(src_index[k] for k in src_keys - dst_keys)
    only_in_dst      = sorted(dst_index[k] for k in dst_keys - src_keys)
    common           = sorted(src_keys & dst_keys)
    size_mismatch    = []
    checksum_mismatch = []
    identical        = []
    unreadable       = []

    for k in common:
        rel = src_index[k]
        s = src_files[rel]
        d = dst_files[dst_index[k]]
        if s["size"] != d["size"]:
            size_mismatch.append(rel)
        else:
            if checksum_cb:
                cs = checksum_cb(s["abs"], rel, "src")
                cd = checksum_cb(d["abs"], rel, "dst")
                if cs is None or cd is None:
                    # Could not verify (permission error, locked file, etc.) —
                    # must NOT be reported as identical.
                    unreadable.append(rel)
                elif cs != cd:
                    checksum_mismatch.append((rel, cs, cd))
                else:
                    identical.append(rel)
            else:
                identical.append(rel)

    return {
        "only_in_src":        only_in_src,
        "only_in_dst":        only_in_dst,
        "size_mismatch":      size_mismatch,
        "checksum_mismatch":  checksum_mismatch,
        "identical":          identical,
        "unreadable":         unreadable,
    }


def find_duplicates(files):
    size_groups = defaultdict(list)
    for rel, info in files.items():
        size_groups[info["size"]].append(rel)
    dupes = {}
    for size, rels in size_groups.items():
        if len(rels) < 2:
            continue
        hash_groups = defaultdict(list)
        for rel in rels:
            h = file_checksum(files[rel]["abs"])
            if h:
                hash_groups[h].append(rel)
        for h, group in hash_groups.items():
            if len(group) > 1:
                dupes[h] = group
    return dupes


def open_in_explorer(path):
    path = Path(path)
    if sys.platform == "win32":
        if path.is_file():
            subprocess.run(["explorer", "/select,", str(path)])
        else:
            subprocess.run(["explorer", str(path)])
    elif sys.platform == "darwin":
        subprocess.run(["open", str(path.parent if path.is_file() else path)])
    else:
        subprocess.run(["xdg-open", str(path.parent if path.is_file() else path)])


# ─────────────────────────────────────────────
# GUI
# ─────────────────────────────────────────────

class DiskDiff(tk.Tk):
    def __init__(self):
        super().__init__()
        resolve_fonts()   # ← must come after super().__init__()

        self.title("DiskDiff — TheBooleanJulian")
        self.geometry("1200x800")
        self.minsize(900, 620)
        self.configure(bg=BG)

        self.src_path   = tk.StringVar()
        self.dst_path   = tk.StringVar()
        self.src_files  = {}
        self.dst_files  = {}
        self._dst_ci    = {}   # lowercase(rel) -> actual dst rel, for case-insensitive lookups
        self.diff_result = {}
        self.src_total  = 0
        self.dst_total  = 0
        self._scan_thread = None

        self._build_ui()
        self._style_ttk()

    # ── UI BUILD ──────────────────────────────

    def _build_ui(self):
        # ── Title bar
        header = tk.Frame(self, bg=BG, pady=12)
        header.pack(fill="x", padx=24)

        tk.Label(header, text="⬡  DISKDIFF",
                 font=FONT_BRAND, fg=ACCENT, bg=BG).pack(side="left")
        tk.Label(header, text="  disk comparison & sync tool",
                 font=FONT_UI, fg=TEXT_DIM, bg=BG).pack(side="left", pady=2)

        # ── Path inputs
        path_frame = tk.Frame(self, bg=BG2, padx=20, pady=16)
        path_frame.pack(fill="x", padx=16, pady=(0, 8))

        self._path_row(path_frame, "SOURCE",      self.src_path, 0, ACCENT)
        self._path_row(path_frame, "DESTINATION", self.dst_path, 1, ACCENT_DIM)

        # ── Action bar
        action = tk.Frame(self, bg=BG, pady=6)
        action.pack(fill="x", padx=16)

        self.btn_scan = self._btn(action, "⟳  SCAN & COMPARE",
                                  self._start_scan, ACCENT)
        self.btn_scan.pack(side="left", padx=(0, 8))

        self.btn_checksum = self._btn(action, "⊕  DEEP SCAN (checksum)",
                                      self._start_deep_scan, ACCENT_DIM)
        self.btn_checksum.pack(side="left", padx=(0, 8))

        self.btn_dupes = self._btn(action, "⊗  FIND DUPLICATES",
                                   self._find_dupes, SURFACE2,
                                   fg=ACCENT)
        self.btn_dupes.pack(side="left", padx=(0, 16))

        self.status_label = tk.Label(action, text="Ready.",
                                     font=FONT_UI_SM, fg=TEXT_DIM, bg=BG)
        self.status_label.pack(side="left")

        # ── Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress = ttk.Progressbar(self, variable=self.progress_var,
                                        maximum=100, mode="indeterminate")
        self.progress.pack(fill="x", padx=16, pady=(0, 4))

        # ── Stats bar
        self.stats_frame = tk.Frame(self, bg=BG3, padx=16, pady=10)
        self.stats_frame.pack(fill="x", padx=16, pady=(0, 8))
        self.stat_labels = {}
        for col, (key, label, color) in enumerate([
            ("src_count", "SRC FILES",  TEXT),
            ("src_size",  "SRC SIZE",   TEXT),
            ("dst_count", "DST FILES",  TEXT),
            ("dst_size",  "DST SIZE",   TEXT),
            ("missing",   "MISSING",    RED),
            ("extra",     "EXTRA",      YELLOW),
            ("mismatch",  "MISMATCH",   RED),
            ("unread",    "UNVERIFIED", YELLOW),
            ("identical", "IDENTICAL",  GREEN),
        ]):
            f = tk.Frame(self.stats_frame, bg=BG3, padx=12)
            f.grid(row=0, column=col, sticky="w")
            tk.Label(f, text=label, font=FONT_MONO_XS,
                     fg=TEXT_DIM, bg=BG3).pack()
            lbl = tk.Label(f, text="—", font=FONT_MONO_LG, fg=color, bg=BG3)
            lbl.pack()
            self.stat_labels[key] = lbl

        # ── Main paned area
        paned = tk.PanedWindow(self, orient="horizontal", bg=BORDER,
                                sashwidth=4, sashrelief="flat")
        paned.pack(fill="both", expand=True, padx=16, pady=(0, 12))

        # Left: diff tree
        left = tk.Frame(paned, bg=BG2)
        paned.add(left, minsize=400)

        tk.Label(left, text="DIFF RESULTS", font=FONT_MONO_MD,
                 fg=ACCENT, bg=BG2, padx=12, pady=8, anchor="w").pack(fill="x")

        tree_frame = tk.Frame(left, bg=BG2)
        tree_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.tree = ttk.Treeview(tree_frame,
                                  columns=("status", "size_src", "size_dst"),
                                  show="tree headings", selectmode="extended")
        self.tree.heading("#0",       text="Path")
        self.tree.heading("status",   text="Status")
        self.tree.heading("size_src", text="Src Size")
        self.tree.heading("size_dst", text="Dst Size")
        self.tree.column("#0",       width=320, minwidth=200)
        self.tree.column("status",   width=130, anchor="center")
        self.tree.column("size_src", width=80,  anchor="e")
        self.tree.column("size_dst", width=80,  anchor="e")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical",
                             command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self.tree.tag_configure("missing",  foreground=RED)
        self.tree.tag_configure("extra",    foreground=YELLOW)
        self.tree.tag_configure("mismatch", foreground=RED)
        self.tree.tag_configure("chksum",   foreground=YELLOW)
        self.tree.tag_configure("unread",   foreground=YELLOW)
        self.tree.tag_configure("ok",       foreground=GREEN)
        self.tree.tag_configure("dupe",     foreground=TEAL_LITE)
        self.tree.tag_configure("header",   foreground=ACCENT,
                                            font=FONT_MONO_MD)
        self.tree.bind("<Double-1>",         self._on_tree_double_click)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        # Right: actions panel
        right = tk.Frame(paned, bg=BG2, width=280)
        paned.add(right, minsize=240)

        tk.Label(right, text="ACTIONS", font=FONT_MONO_MD,
                 fg=ACCENT, bg=BG2, padx=12, pady=8, anchor="w").pack(fill="x")

        act_inner = tk.Frame(right, bg=BG2, padx=12)
        act_inner.pack(fill="x")

        self.btn_copy_src_dst = self._btn(act_inner, "→  Copy Missing to DST",
                                          self._copy_missing_to_dst, ACCENT)
        self.btn_copy_src_dst.pack(fill="x", pady=3)

        self.btn_copy_sel = self._btn(act_inner, "↓  Copy Selected → DST",
                                      self._copy_selected_to_dst, ACCENT_DIM)
        self.btn_copy_sel.pack(fill="x", pady=3)

        self.btn_open_src = self._btn(act_inner, "⊞  Open in Explorer (SRC)",
                                      lambda: self._open_selected("src"),
                                      SURFACE2, fg=ACCENT)
        self.btn_open_src.pack(fill="x", pady=3)

        self.btn_open_dst = self._btn(act_inner, "⊞  Open in Explorer (DST)",
                                      lambda: self._open_selected("dst"),
                                      SURFACE2, fg=ACCENT)
        self.btn_open_dst.pack(fill="x", pady=3)

        ttk.Separator(act_inner, orient="horizontal").pack(fill="x", pady=10)

        tk.Label(act_inner, text="FILTER", font=FONT_MONO_SM,
                 fg=TEXT_DIM, bg=BG2).pack(anchor="w")

        self.filter_var = tk.StringVar(value="all")
        for val, label in [
            ("all",      "All"),
            ("missing",  "Missing from DST"),
            ("extra",    "Extra in DST"),
            ("mismatch", "Size/Checksum Mismatch"),
            ("unread",   "Unverified (read error)"),
            ("ok",       "Identical"),
            ("dupe",     "Duplicates"),
        ]:
            rb = tk.Radiobutton(act_inner, text=label, variable=self.filter_var,
                                value=val, command=self._apply_filter,
                                bg=BG2, fg=TEXT, selectcolor=BG3,
                                activebackground=BG2, activeforeground=ACCENT,
                                font=FONT_UI_SM)
            rb.pack(anchor="w", padx=4)

        ttk.Separator(act_inner, orient="horizontal").pack(fill="x", pady=10)

        tk.Label(act_inner, text="DETAIL", font=FONT_MONO_SM,
                 fg=TEXT_DIM, bg=BG2).pack(anchor="w")
        self.detail_text = tk.Text(act_inner, height=10, bg=BG3, fg=TEXT,
                                    font=FONT_MONO, relief="flat",
                                    borderwidth=0, state="disabled", wrap="word")
        self.detail_text.pack(fill="x", pady=4)

    def _path_row(self, parent, label, var, row, color):
        tk.Label(parent, text=label, font=FONT_MONO_SM,
                 fg=color, bg=BG2, width=13, anchor="w").grid(
                     row=row, column=0, sticky="w", pady=4)
        entry = tk.Entry(parent, textvariable=var, font=FONT_MONO,
                         bg=BG3, fg=TEXT, insertbackground=ACCENT,
                         relief="flat", borderwidth=0)
        entry.grid(row=row, column=1, sticky="ew", padx=(8, 8), ipady=6)
        btn = tk.Button(parent, text="Browse…", font=FONT_UI_SM,
                        bg=BG3, fg=TEXT_DIM, relief="flat", borderwidth=0,
                        activebackground=BG, activeforeground=ACCENT,
                        cursor="hand2",
                        command=lambda v=var: self._browse(v))
        btn.grid(row=row, column=2, padx=(0, 4))
        parent.columnconfigure(1, weight=1)

    def _btn(self, parent, text, cmd, bg, fg=BG):
        return tk.Button(parent, text=text, command=cmd,
                         font=FONT_MONO_MD,
                         bg=bg, fg=fg,
                         activebackground=ACCENT, activeforeground=BG,
                         relief="flat", borderwidth=0,
                         padx=12, pady=7, cursor="hand2")

    def _style_ttk(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Treeview",
                         background=BG3, foreground=TEXT,
                         fieldbackground=BG3, borderwidth=0,
                         rowheight=22, font=FONT_MONO)
        style.configure("Treeview.Heading",
                         background=BG2, foreground=ACCENT,
                         font=FONT_MONO_SM, borderwidth=0)
        style.map("Treeview",
                  background=[("selected", BG)],
                  foreground=[("selected", ACCENT)])
        style.configure("Horizontal.TProgressbar",
                         troughcolor=BG3, background=ACCENT, borderwidth=0)
        style.configure("Vertical.TScrollbar",
                         background=BG3, troughcolor=BG2, borderwidth=0)

    # ── BROWSE / HELPERS ──────────────────────

    def _browse(self, var):
        path = filedialog.askdirectory(title="Select Folder")
        if path:
            var.set(path)

    def _set_status(self, msg, color=TEXT_DIM):
        self.status_label.config(text=msg, fg=color)
        self.update_idletasks()

    def _dst_lookup(self, rel):
        """Look up a dst file entry, tolerating case differences (see _dst_ci)."""
        if rel in self.dst_files:
            return self.dst_files[rel]
        actual = self._dst_ci.get(rel.lower())
        return self.dst_files.get(actual) if actual else None

    def _set_stat(self, key, val):
        if key in self.stat_labels:
            self.stat_labels[key].config(text=str(val))

    def _update_stats(self):
        d = self.diff_result
        self._set_stat("src_count", f"{len(self.src_files):,}")
        self._set_stat("src_size",  format_size(self.src_total))
        self._set_stat("dst_count", f"{len(self.dst_files):,}")
        self._set_stat("dst_size",  format_size(self.dst_total))
        self._set_stat("missing",   len(d.get("only_in_src", [])))
        self._set_stat("extra",     len(d.get("only_in_dst", [])))
        self._set_stat("mismatch",  len(d.get("size_mismatch", [])) +
                                    len(d.get("checksum_mismatch", [])))
        self._set_stat("unread",    len(d.get("unreadable", [])))
        self._set_stat("identical", len(d.get("identical", [])))

    # ── SCAN ─────────────────────────────────

    def _start_scan(self):
        self._run_scan(deep=False)

    def _start_deep_scan(self):
        self._run_scan(deep=True)

    def _run_scan(self, deep=False):
        src = self.src_path.get().strip()
        dst = self.dst_path.get().strip()
        if not src or not dst:
            messagebox.showwarning("Missing Paths",
                                   "Please enter both source and destination paths.")
            return
        if not os.path.isdir(src):
            messagebox.showerror("Invalid Source", f"Not a directory:\n{src}")
            return
        if not os.path.isdir(dst):
            messagebox.showerror("Invalid Destination", f"Not a directory:\n{dst}")
            return

        self._clear_tree()
        self.progress.config(mode="indeterminate")
        self.progress.start(12)
        self._set_status("Scanning source…", ACCENT)
        self.btn_scan.config(state="disabled")
        self.btn_checksum.config(state="disabled")

        def worker():
            self.after(0, lambda: self._set_status("Scanning source…", ACCENT))
            src_files, src_total, src_err = scan_directory(src)
            self.src_files = src_files
            self.src_total = src_total

            self.after(0, lambda: self._set_status("Scanning destination…", ACCENT))
            dst_files, dst_total, dst_err = scan_directory(dst)
            self.dst_files = dst_files
            self.dst_total = dst_total
            self._dst_ci = ({rel.lower(): rel for rel in dst_files}
                             if sys.platform == "win32" else {})

            self.after(0, lambda: self._set_status("Comparing…", ACCENT))
            if deep:
                checked = [0]
                total_files = len(src_files) + len(dst_files)
                def checksum_cb(path, rel, side):
                    checked[0] += 1
                    self.after(0, lambda r=rel, c=checked[0]: self._set_status(
                        f"Checksumming [{c}/{total_files}]: {r[:50]}…", ACCENT))
                    return file_checksum(path)
                diff = compare_directories(src_files, dst_files, checksum_cb)
            else:
                diff = compare_directories(src_files, dst_files)

            self.diff_result = diff
            errors = src_err + dst_err
            self.after(0, lambda: self._scan_done(errors, deep))

        threading.Thread(target=worker, daemon=True).start()

    def _scan_done(self, errors, deep):
        self.progress.stop()
        self.progress.config(mode="determinate")
        self.progress_var.set(100)
        self.btn_scan.config(state="normal")
        self.btn_checksum.config(state="normal")
        self._update_stats()
        self._populate_tree()
        mode = "deep (checksum)" if deep else "quick (size)"
        self._set_status(
            f"✓  Scan complete [{mode}]  —  {datetime.now().strftime('%H:%M:%S')}", GREEN)
        if errors:
            messagebox.showwarning("Scan Errors",
                f"{len(errors)} error(s) during scan.\n\n" + "\n".join(errors[:10]))

    # ── TREE ─────────────────────────────────

    def _clear_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

    def _populate_tree(self, filter_mode=None):
        self._clear_tree()
        d = self.diff_result
        if not d:
            return
        fm = filter_mode or self.filter_var.get()

        def add_section(label, items, tag, col_fn):
            if not items:
                return
            sec = self.tree.insert("", "end",
                                   text=f"  {label}  ({len(items)})",
                                   values=("", "", ""),
                                   tags=("header",), open=True)
            for item in items:
                if isinstance(item, tuple):
                    rel, cs, cd = item
                    self.tree.insert(sec, "end", text=f"  {rel}",
                                     values=("HASH DIFF",
                                             col_fn(rel, "src"),
                                             col_fn(rel, "dst")),
                                     tags=(tag,))
                else:
                    self.tree.insert(sec, "end", text=f"  {item}",
                                     values=col_fn(item), tags=(tag,))

        def sizes_src_only(rel):
            s = format_size(self.src_files[rel]["size"]) if rel in self.src_files else "—"
            return ("MISSING in DST", s, "—")

        def sizes_dst_only(rel):
            d2 = format_size(self.dst_files[rel]["size"]) if rel in self.dst_files else "—"
            return ("EXTRA in DST", "—", d2)

        def sizes_common(rel):
            s  = format_size(self.src_files[rel]["size"]) if rel in self.src_files else "—"
            dinfo = self._dst_lookup(rel)
            d2 = format_size(dinfo["size"]) if dinfo else "—"
            return ("MISMATCH", s, d2)

        def sizes_ok(rel):
            s = format_size(self.src_files[rel]["size"]) if rel in self.src_files else "—"
            return ("OK", s, s)

        def chksum_sizes(rel, side):
            if side == "src":
                return format_size(self.src_files[rel]["size"]) if rel in self.src_files else "—"
            dinfo = self._dst_lookup(rel)
            return format_size(dinfo["size"]) if dinfo else "—"

        def unread_sizes(rel):
            s = format_size(self.src_files[rel]["size"]) if rel in self.src_files else "—"
            dinfo = self._dst_lookup(rel)
            d2 = format_size(dinfo["size"]) if dinfo else "—"
            return ("UNVERIFIED", s, d2)

        if fm in ("all", "missing"):
            add_section("MISSING FROM DESTINATION",
                        d.get("only_in_src", []), "missing", sizes_src_only)
        if fm in ("all", "extra"):
            add_section("EXTRA IN DESTINATION",
                        d.get("only_in_dst", []), "extra", sizes_dst_only)
        if fm in ("all", "mismatch"):
            add_section("SIZE MISMATCH",
                        d.get("size_mismatch", []), "mismatch", sizes_common)
            add_section("CHECKSUM MISMATCH (same size, different content)",
                        d.get("checksum_mismatch", []), "chksum", chksum_sizes)
        if fm in ("all", "unread"):
            add_section("UNVERIFIED (could not read file — not confirmed identical)",
                        d.get("unreadable", []), "unread", unread_sizes)
        if fm in ("all", "ok"):
            add_section("IDENTICAL",
                        d.get("identical", []), "ok", sizes_ok)

    def _apply_filter(self):
        if self.diff_result:
            self._populate_tree()

    # ── DUPLICATE FINDER ─────────────────────

    def _find_dupes(self):
        if not self.src_files:
            messagebox.showinfo("Scan First",
                                "Run a scan first so files are loaded.")
            return
        self._set_status("Finding duplicates in source…", ACCENT)
        self.progress.config(mode="indeterminate")
        self.progress.start(12)

        def worker():
            dupes = find_duplicates(self.src_files)
            self.after(0, lambda: self._show_dupes(dupes))

        threading.Thread(target=worker, daemon=True).start()

    def _show_dupes(self, dupes):
        self.progress.stop()
        self.progress.config(mode="determinate")
        self.progress_var.set(0)
        if not dupes:
            self._set_status("No duplicates found.", GREEN)
            return

        self._clear_tree()
        total_wasted = 0
        for h, paths in dupes.items():
            size = self.src_files[paths[0]]["size"]
            wasted = size * (len(paths) - 1)
            total_wasted += wasted
            sec = self.tree.insert("", "end",
                                   text=f"  [{h[:10]}…]  {len(paths)} copies · {format_size(wasted)} wasted",
                                   values=("DUPLICATE", format_size(size), ""),
                                   tags=("header",), open=True)
            for p in paths:
                self.tree.insert(sec, "end", text=f"  {p}",
                                 values=("", format_size(size), ""),
                                 tags=("dupe",))

        self._set_status(
            f"Found {len(dupes)} duplicate group(s) · {format_size(total_wasted)} wasted",
            YELLOW)

    # ── COPY ACTIONS ─────────────────────────

    def _copy_missing_to_dst(self):
        missing = self.diff_result.get("only_in_src", [])
        if not missing:
            messagebox.showinfo("Nothing to Copy", "No missing files to copy.")
            return
        dst_root = self.dst_path.get().strip()
        if not dst_root:
            messagebox.showerror("No Destination", "Set a destination path.")
            return
        if not messagebox.askyesno("Confirm Copy",
            f"Copy {len(missing)} missing file(s) to:\n{dst_root}\n\nContinue?"):
            return
        self._do_copy(missing, dst_root)

    def _copy_selected_to_dst(self):
        sel = self.tree.selection()
        dst_root = self.dst_path.get().strip()
        if not dst_root:
            messagebox.showerror("No Destination", "Set a destination path.")
            return
        rels = []
        for item_id in sel:
            tags = self.tree.item(item_id, "tags")
            if "header" not in tags:
                text = self.tree.item(item_id, "text").strip()
                if text:
                    rels.append(text)
        if not rels:
            messagebox.showinfo("No Files",
                                "Select file rows (not section headers) to copy.")
            return
        if not messagebox.askyesno("Confirm Copy",
            f"Copy {len(rels)} selected file(s) to destination?"):
            return
        self._do_copy(rels, dst_root)

    def _do_copy(self, rels, dst_root):
        src_root = self.src_path.get().strip()
        errors = []
        copied = 0
        total  = len(rels)
        self.progress.config(mode="determinate")
        for i, rel in enumerate(rels):
            self._set_status(f"Copying {i+1}/{total}: {rel[:60]}…", ACCENT)
            self.progress_var.set((i + 1) / total * 100)
            self.update_idletasks()
            src_abs = os.path.join(src_root, rel)
            dst_abs = os.path.join(dst_root, rel)
            try:
                os.makedirs(os.path.dirname(dst_abs), exist_ok=True)
                shutil.copy2(src_abs, dst_abs)
                copied += 1
            except Exception as e:
                errors.append(f"{rel}: {e}")

        self._set_status(f"✓  Copied {copied}/{total} files.", GREEN)
        if errors:
            messagebox.showwarning("Copy Errors",
                f"{len(errors)} file(s) failed:\n\n" + "\n".join(errors[:10]))
        else:
            messagebox.showinfo("Done", f"Successfully copied {copied} file(s).")

    def _open_selected(self, side):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("No Selection", "Select a file in the tree first.")
            return
        item_id = sel[0]
        tags = self.tree.item(item_id, "tags")
        if "header" in tags:
            messagebox.showinfo("Select a File",
                                "Select a file row, not a section header.")
            return
        rel  = self.tree.item(item_id, "text").strip()
        root = (self.src_path.get().strip() if side == "src"
                else self.dst_path.get().strip())
        abs_path = os.path.join(root, rel)
        if not os.path.exists(abs_path):
            abs_path = os.path.dirname(abs_path)
        open_in_explorer(abs_path)

    # ── DETAIL PANEL ─────────────────────────

    def _on_select(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        item_id = sel[0]
        tags = self.tree.item(item_id, "tags")
        if "header" in tags:
            return
        rel   = self.tree.item(item_id, "text").strip()
        lines = [f"PATH:\n  {rel}\n"]
        if rel in self.src_files:
            fi = self.src_files[rel]
            mt = datetime.fromtimestamp(fi["mtime"]).strftime("%Y-%m-%d %H:%M:%S")
            lines.append(f"SOURCE:\n  Size:     {format_size(fi['size'])}\n  Modified: {mt}\n")
        dfi = self._dst_lookup(rel)
        if dfi:
            mt = datetime.fromtimestamp(dfi["mtime"]).strftime("%Y-%m-%d %H:%M:%S")
            lines.append(f"DEST:\n  Size:     {format_size(dfi['size'])}\n  Modified: {mt}\n")
        self.detail_text.config(state="normal")
        self.detail_text.delete("1.0", "end")
        self.detail_text.insert("end", "\n".join(lines))
        self.detail_text.config(state="disabled")

    def _on_tree_double_click(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        item_id = sel[0]
        if "header" in self.tree.item(item_id, "tags"):
            return
        rel      = self.tree.item(item_id, "text").strip()
        src_abs  = os.path.join(self.src_path.get().strip(), rel)
        if os.path.exists(src_abs):
            open_in_explorer(src_abs)


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    app = DiskDiff()
    app.mainloop()
