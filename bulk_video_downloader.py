#!/usr/bin/env python3
"""
Bulk Video Downloader — Cross-platform GUI (Windows native UI style)
Supports YouTube, Vimeo, Twitter/X, Reddit, and 1800+ sites via yt-dlp.
Original concept by EDM115 · GUI edition by officialputuid

Requirements:
  - Python 3.8+
  - yt-dlp   (pip install yt-dlp)
  - ffmpeg   (must be in PATH)
"""

from __future__ import annotations

import json
import os
import platform
import queue
import re
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import Optional

# ═══════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════

APP_NAME = "Bulk Video Downloader"
VERSION = "1.0"
CONFIG_FILE = "config.json"
ARCHIVE_FILE = "download_archive.txt"

DOWNLOAD_MODES = {
    "Best video + audio": {
        "args": ["-f", "bestvideo+bestaudio/best"],
        "merge": True,
    },
    "Audio only (MP3)": {
        "args": ["-f", "bestaudio/best", "-x", "--audio-format", "mp3", "--audio-quality", "0"],
        "merge": False,
    },
    "Audio only (native codec)": {
        "args": ["-f", "bestaudio/best"],
        "merge": False,
    },
    "Video only (no audio)": {
        "args": ["-f", "bestvideo"],
        "merge": False,
    },
    "720p max": {
        "args": ["-f", "bestvideo[height<=720]+bestaudio/best[height<=720]"],
        "merge": True,
    },
    "1080p max": {
        "args": ["-f", "bestvideo[height<=1080]+bestaudio/best[height<=1080]"],
        "merge": True,
    },
    "4K max": {
        "args": ["-f", "bestvideo[height<=2160]+bestaudio/best[height<=2160]"],
        "merge": True,
    },
}

CONTAINERS = ["mp4", "mkv", "webm"]

# ═══════════════════════════════════════════════════════════════════════════
# Utility helpers
# ═══════════════════════════════════════════════════════════════════════════

def which(cmd: str) -> Optional[str]:
    return shutil.which(cmd)


def check_requirements() -> list:
    missing = []
    for cmd in ("yt-dlp", "ffmpeg", "ffprobe"):
        if not which(cmd):
            missing.append(cmd)
    return missing


def clean_url(raw: str) -> str:
    line = raw.strip().strip('"').strip("'").strip(",").strip("[").strip("]").strip()
    return line


def parse_links_file(path: str) -> list:
    urls = []
    seen = set()
    with open(path, encoding="utf-8", errors="replace") as f:
        for raw in f:
            line = clean_url(raw)
            if not line or line.startswith("#"):
                continue
            if line not in seen:
                seen.add(line)
                urls.append(line)
    return urls


def timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# ═══════════════════════════════════════════════════════════════════════════
# Config persistence
# ═══════════════════════════════════════════════════════════════════════════

DEFAULT_CONFIG = {
    "output_dir": "downloads",
    "mode": "Best video + audio",
    "container": "mp4",
    "retries": 3,
    "rate_limit": "",
    "proxy": "",
    "subs_lang": "en",
    "embed_subs": True,
    "embed_thumbnail": True,
    "embed_metadata": True,
    "embed_chapters": True,
    "use_archive": True,
    "no_playlist": True,
    "extra_args": "",
}


def load_config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    if os.path.isfile(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception:
            pass
    return cfg


def save_config(cfg: dict) -> None:
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass

# ═══════════════════════════════════════════════════════════════════════════
# Download worker (runs in a background thread)
# ═══════════════════════════════════════════════════════════════════════════

class DownloadWorker(threading.Thread):

    def __init__(self, urls, config, msg_queue):
        super().__init__(daemon=True)
        self.urls = urls
        self.config = config
        self.q = msg_queue
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    @property
    def stopped(self):
        return self._stop_event.is_set()

    def _post(self, kind, **kwargs):
        self.q.put({"kind": kind, **kwargs})

    def run(self):
        cfg = self.config
        total = len(self.urls)
        success = fail = 0

        self._post("log", text=f"[{timestamp()}] Session started - {total} URL(s), mode: {cfg['mode']}")

        for idx, url in enumerate(self.urls, 1):
            if self.stopped:
                self._post("log", text="Cancelled by user.")
                break

            self._post("progress", current=idx, total=total, url=url)
            self._post("log", text=f"\n[{idx}/{total}] {url}")

            ok = False
            retries = cfg.get("retries", 3)
            for attempt in range(1, retries + 1):
                if self.stopped:
                    break

                if attempt > 1:
                    self._post("log", text=f"  Retry {attempt}/{retries}...")

                cmd = self._build_cmd(url, cfg)

                try:
                    proc = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        errors="replace",
                        bufsize=1,
                    )
                    for line in proc.stdout:
                        stripped = line.rstrip()
                        if stripped:
                            pct = self._parse_progress(stripped)
                            if pct is not None:
                                self._post("item_progress", index=idx - 1, percent=pct)
                            self._post("output", text=stripped)
                    proc.wait()

                    if proc.returncode == 0:
                        ok = True
                        break
                    else:
                        self._post("log", text=f"  Exit code {proc.returncode}")
                except FileNotFoundError:
                    self._post("log", text="  ERROR: yt-dlp not found!")
                    break
                except Exception as exc:
                    self._post("log", text=f"  ERROR: {exc}")

            if ok:
                success += 1
                self._post("log", text="  Done.")
                self._post("item_status", index=idx - 1, status="ok")
                self._post("item_progress", index=idx - 1, percent=100)
            else:
                if self.stopped:
                    break
                fail += 1
                self._post("log", text=f"  FAILED after {retries} attempt(s).")
                self._post("item_status", index=idx - 1, status="fail")

        self._post("done", success=success, failed=fail)

    @staticmethod
    def _parse_progress(line):
        m = re.search(r'\[download\]\s+(\d+(?:\.\d+)?)%', line)
        if m:
            return float(m.group(1))
        return None

    @staticmethod
    def _build_cmd(url, cfg):
        cmd = ["yt-dlp"]

        mode_info = DOWNLOAD_MODES.get(cfg.get("mode", "Best video + audio"),
                                       DOWNLOAD_MODES["Best video + audio"])
        cmd.extend(mode_info["args"])

        if mode_info.get("merge") and cfg.get("container"):
            cmd.extend(["--merge-output-format", cfg["container"]])

        out_dir = cfg.get("output_dir", "downloads")
        os.makedirs(out_dir, exist_ok=True)
        sep = "\\" if platform.system() == "Windows" else "/"
        cmd.extend(["-o", f"{out_dir}{sep}%(title).150s [%(id)s].%(ext)s"])

        if cfg.get("embed_subs"):
            cmd.append("--embed-subs")
            cmd.extend(["--sub-langs", cfg.get("subs_lang", "en")])
        if cfg.get("embed_thumbnail"):
            cmd.append("--embed-thumbnail")
        if cfg.get("embed_metadata"):
            cmd.append("--embed-metadata")
        if cfg.get("embed_chapters"):
            cmd.append("--embed-chapters")
        if cfg.get("no_playlist"):
            cmd.append("--no-playlist")
        if cfg.get("use_archive"):
            cmd.extend(["--download-archive", ARCHIVE_FILE])

        cmd.extend(["--no-overwrites", "--progress", "--newline"])

        if platform.system() == "Windows":
            cmd.append("--windows-filenames")

        rate = cfg.get("rate_limit", "")
        if rate:
            cmd.extend(["-r", rate])
        proxy = cfg.get("proxy", "")
        if proxy:
            cmd.extend(["--proxy", proxy])

        extra = cfg.get("extra_args", "").strip()
        if extra:
            cmd.extend(extra.split())

        cmd.append(url)
        return cmd

# ═══════════════════════════════════════════════════════════════════════════
# Main GUI — Native Windows Style
# ═══════════════════════════════════════════════════════════════════════════

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} v{VERSION}")
        self.geometry("1000x720")
        self.minsize(800, 560)
        self.config_data = load_config()
        self.worker = None
        self.msg_queue = queue.Queue()

        self._apply_theme()
        self._build_ui()
        self._check_deps()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _apply_theme(self):
        style = ttk.Style(self)
        available = style.theme_names()
        # Use winnative on Windows, clam on Linux (closest to native look)
        if "winnative" in available:
            style.theme_use("winnative")
        elif "vista" in available:
            style.theme_use("vista")
        elif "clam" in available:
            style.theme_use("clam")

        style.configure("TNotebook.Tab", padding=[14, 6])
        style.configure("Header.TLabel", font=("Segoe UI", 14, "bold"))
        style.configure("SubHeader.TLabel", font=("Segoe UI", 9))
        style.configure("Section.TLabel", font=("Segoe UI", 10, "bold"))

        # Treeview styling
        style.configure("Treeview", rowheight=28, font=("Segoe UI", 9))
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))

    # ── Build UI ──────────────────────────────────────────────────────────
    def _build_ui(self):
        # Header
        hdr = ttk.Frame(self, padding=(12, 8))
        hdr.pack(fill="x")
        ttk.Label(hdr, text=APP_NAME, style="Header.TLabel").pack(side="left")
        ttk.Label(hdr, text=f"  v{VERSION} - yt-dlp powered - 1800+ sites supported",
                  style="SubHeader.TLabel").pack(side="left", padx=(8, 0))

        ttk.Separator(self, orient="horizontal").pack(fill="x")

        # Notebook (tabs)
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=4)

        self._build_downloads_tab()
        self._build_settings_tab()

        # Status bar
        sep = ttk.Separator(self, orient="horizontal")
        sep.pack(fill="x", side="bottom")

        status_frame = ttk.Frame(self, padding=(8, 4))
        status_frame.pack(fill="x", side="bottom")

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(status_frame, textvariable=self.status_var,
                  font=("Segoe UI", 9)).pack(side="left")

        self.count_label = ttk.Label(status_frame, text="0 URLs",
                                      font=("Segoe UI", 9))
        self.count_label.pack(side="right")

    # ── Downloads Tab ─────────────────────────────────────────────────────
    def _build_downloads_tab(self):
        tab = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(tab, text="  Downloads  ")

        # ─── Toolbar ─────────────────────────────────────────────────────
        toolbar = ttk.LabelFrame(tab, text="URL Management", padding=8)
        toolbar.pack(fill="x", pady=(0, 6))

        # Row 1: buttons
        btn_row = ttk.Frame(toolbar)
        btn_row.pack(fill="x", pady=(0, 6))

        ttk.Button(btn_row, text="+ Add URL", command=self._add_url).pack(side="left", padx=2)
        ttk.Button(btn_row, text="Paste URLs", command=self._paste_urls).pack(side="left", padx=2)
        ttk.Button(btn_row, text="Import File", command=self._import_file).pack(side="left", padx=2)
        ttk.Separator(btn_row, orient="vertical").pack(side="left", fill="y", padx=6)
        ttk.Button(btn_row, text="Remove Selected", command=self._remove_selected).pack(side="left", padx=2)
        ttk.Button(btn_row, text="Clear All", command=self._clear_urls).pack(side="left", padx=2)

        # Row 2: mode, output, actions
        opts_row = ttk.Frame(toolbar)
        opts_row.pack(fill="x")

        ttk.Label(opts_row, text="Mode:").pack(side="left")
        self.mode_var = tk.StringVar(value=self.config_data.get("mode", "Best video + audio"))
        ttk.Combobox(opts_row, textvariable=self.mode_var,
                     values=list(DOWNLOAD_MODES.keys()),
                     state="readonly", width=24).pack(side="left", padx=(4, 12))

        ttk.Label(opts_row, text="Output:").pack(side="left")
        self.outdir_var = tk.StringVar(value=self.config_data.get("output_dir", "downloads"))
        ttk.Entry(opts_row, textvariable=self.outdir_var, width=20).pack(side="left", padx=(4, 2))
        ttk.Button(opts_row, text="Browse...", command=self._browse_outdir).pack(side="left", padx=(0, 12))

        ttk.Separator(opts_row, orient="vertical").pack(side="left", fill="y", padx=6)

        self.dl_btn = ttk.Button(opts_row, text="Start Download", command=self._start_download)
        self.dl_btn.pack(side="left", padx=4)

        self.stop_btn = ttk.Button(opts_row, text="Stop", command=self._stop_download, state="disabled")
        self.stop_btn.pack(side="left", padx=2)

        ttk.Button(opts_row, text="Update yt-dlp", command=self._update_ytdlp).pack(side="right", padx=2)

        # ─── Progress ────────────────────────────────────────────────────
        prog_frame = ttk.Frame(tab)
        prog_frame.pack(fill="x", pady=(4, 4))

        self.progress_label = ttk.Label(prog_frame, text="Ready")
        self.progress_label.pack(side="left")

        self.overall_progress = ttk.Progressbar(prog_frame, mode="determinate", length=300)
        self.overall_progress.pack(side="right")

        self.progress_pct_label = ttk.Label(prog_frame, text="0/0")
        self.progress_pct_label.pack(side="right", padx=(0, 6))

        # ─── Paned window: URL list + Log ────────────────────────────────
        pane = ttk.PanedWindow(tab, orient="vertical")
        pane.pack(fill="both", expand=True, pady=(4, 0))

        # URL List
        list_frame = ttk.Frame(pane)

        cols = ("status", "url", "progress")
        self.url_tree = ttk.Treeview(list_frame, columns=cols, show="headings",
                                      selectmode="extended", height=12)
        self.url_tree.heading("status", text="Status")
        self.url_tree.heading("url", text="URL")
        self.url_tree.heading("progress", text="Progress")
        self.url_tree.column("status", width=90, minwidth=70, anchor="center")
        self.url_tree.column("url", width=550, minwidth=200)
        self.url_tree.column("progress", width=80, minwidth=60, anchor="center")

        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=self.url_tree.yview)
        hsb = ttk.Scrollbar(list_frame, orient="horizontal", command=self.url_tree.xview)
        self.url_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.url_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)

        # Tag colors
        self.url_tree.tag_configure("ok", background="#d4edda")
        self.url_tree.tag_configure("fail", background="#f8d7da")
        self.url_tree.tag_configure("active", background="#fff3cd")
        self.url_tree.tag_configure("pending", background="")

        pane.add(list_frame, weight=3)

        # Log panel
        log_frame = ttk.LabelFrame(pane, text="Live Output", padding=4)

        log_toolbar = ttk.Frame(log_frame)
        log_toolbar.pack(fill="x", pady=(0, 2))
        ttk.Button(log_toolbar, text="Clear", command=self._clear_log).pack(side="right")
        ttk.Button(log_toolbar, text="Save Log...", command=self._save_log).pack(side="right", padx=2)

        self.log_text = scrolledtext.ScrolledText(
            log_frame, wrap="word", font=("Consolas", 9),
            state="disabled", height=8,
            bg="#1e1e1e", fg="#d4d4d4", insertbackground="#d4d4d4"
        )
        self.log_text.pack(fill="both", expand=True)

        # Log text colors
        self.log_text.tag_configure("info", foreground="#569cd6")
        self.log_text.tag_configure("success", foreground="#6a9955")
        self.log_text.tag_configure("error", foreground="#f44747")
        self.log_text.tag_configure("warning", foreground="#d7ba7d")
        self.log_text.tag_configure("dim", foreground="#808080")

        pane.add(log_frame, weight=2)

    # ── Settings Tab ──────────────────────────────────────────────────────
    def _build_settings_tab(self):
        tab = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(tab, text="  Settings  ")

        # Canvas for scrolling
        canvas = tk.Canvas(tab, highlightthickness=0)
        vsb = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)

        scroll_frame.bind("<Configure>",
                          lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=vsb.set)

        canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Mousewheel
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        canvas.bind_all("<Button-4>", lambda e: canvas.yview_scroll(-3, "units"))
        canvas.bind_all("<Button-5>", lambda e: canvas.yview_scroll(3, "units"))

        row = 0

        def add_section(title):
            nonlocal row
            ttk.Label(scroll_frame, text=title, style="Section.TLabel").grid(
                row=row, column=0, columnspan=3, sticky="w", pady=(14, 4))
            row += 1
            ttk.Separator(scroll_frame, orient="horizontal").grid(
                row=row, column=0, columnspan=3, sticky="ew", pady=(0, 6))
            row += 1

        def add_entry(label, key, width=20):
            nonlocal row
            ttk.Label(scroll_frame, text=label).grid(row=row, column=0, sticky="w", padx=(8, 4), pady=3)
            var = tk.StringVar(value=str(self.config_data.get(key, "")))
            ttk.Entry(scroll_frame, textvariable=var, width=width).grid(row=row, column=1, sticky="w", pady=3)
            setattr(self, f"cfg_{key}", var)
            row += 1

        def add_check(label, key):
            nonlocal row
            var = tk.BooleanVar(value=self.config_data.get(key, True))
            ttk.Checkbutton(scroll_frame, text=label, variable=var).grid(
                row=row, column=0, columnspan=3, sticky="w", padx=(8, 0), pady=2)
            setattr(self, f"cfg_{key}", var)
            row += 1

        def add_combo(label, key, values, width=10):
            nonlocal row
            ttk.Label(scroll_frame, text=label).grid(row=row, column=0, sticky="w", padx=(8, 4), pady=3)
            var = tk.StringVar(value=str(self.config_data.get(key, values[0])))
            ttk.Combobox(scroll_frame, textvariable=var, values=values,
                         state="readonly", width=width).grid(row=row, column=1, sticky="w", pady=3)
            setattr(self, f"cfg_{key}", var)
            row += 1

        # Download
        add_section("Download")
        add_entry("Retries:", "retries", 6)
        add_entry("Rate limit (e.g. 5M):", "rate_limit", 12)
        add_combo("Container format:", "container", CONTAINERS)

        # Network
        add_section("Network")
        add_entry("Proxy (e.g. socks5://host:port):", "proxy", 36)

        # Embedding
        add_section("Embedding")
        add_check("Embed subtitles", "embed_subs")
        add_entry("Subtitle languages:", "subs_lang", 16)
        add_check("Embed thumbnail", "embed_thumbnail")
        add_check("Embed metadata", "embed_metadata")
        add_check("Embed chapters", "embed_chapters")

        # Behavior
        add_section("Behavior")
        add_check("Use download archive (skip re-downloads)", "use_archive")
        add_check("Single video only (no playlists)", "no_playlist")

        # Advanced
        add_section("Advanced")
        add_entry("Extra yt-dlp arguments:", "extra_args", 50)

        # Buttons
        row += 1
        btn_frame = ttk.Frame(scroll_frame)
        btn_frame.grid(row=row, column=0, columnspan=3, sticky="w", pady=(14, 8))
        ttk.Button(btn_frame, text="Save Settings", command=self._save_settings).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Reset Defaults", command=self._reset_settings).pack(side="left", padx=4)

    # ── Dependency check ──────────────────────────────────────────────────
    def _check_deps(self):
        missing = check_requirements()
        if missing:
            msg = "Missing required tools:\n\n"
            for m in missing:
                msg += f"  \u2022 {m}\n"
            msg += "\nPlease install them and add to your PATH."
            if "yt-dlp" in missing:
                msg += "\n\n  pip install yt-dlp"
            if "ffmpeg" in missing or "ffprobe" in missing:
                msg += "\n\n  https://ffmpeg.org/download.html"
            messagebox.showwarning("Missing Dependencies", msg)
            self.status_var.set("Missing dependencies - see warning")
        else:
            self._log("All dependencies found (yt-dlp, ffmpeg, ffprobe).", tag="success")

    # ── URL management ────────────────────────────────────────────────────
    def _add_url(self):
        dialog = tk.Toplevel(self)
        dialog.title("Add URL")
        dialog.geometry("520x90")
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)

        frame = ttk.Frame(dialog, padding=12)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="URL:").pack(side="left")
        entry = ttk.Entry(frame, width=50)
        entry.pack(side="left", fill="x", expand=True, padx=(6, 6))
        entry.focus_set()

        def submit(event=None):
            url = entry.get().strip()
            if url:
                self._insert_url(url)
            dialog.destroy()

        entry.bind("<Return>", submit)
        ttk.Button(frame, text="Add", command=submit).pack(side="left")

    def _paste_urls(self):
        try:
            text = self.clipboard_get()
        except tk.TclError:
            messagebox.showinfo("Paste", "Clipboard is empty.")
            return

        existing = set()
        for iid in self.url_tree.get_children():
            existing.add(self.url_tree.item(iid, "values")[1])

        count = 0
        for line in text.splitlines():
            url = clean_url(line)
            if url and not url.startswith("#") and url not in existing:
                self._insert_url(url)
                existing.add(url)
                count += 1
        self.status_var.set(f"Pasted {count} URL(s)")

    def _import_file(self):
        path = filedialog.askopenfilename(
            title="Import URLs from file",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return
        urls = parse_links_file(path)
        existing = set()
        for iid in self.url_tree.get_children():
            existing.add(self.url_tree.item(iid, "values")[1])
        count = 0
        for url in urls:
            if url not in existing:
                self._insert_url(url)
                existing.add(url)
                count += 1
        self.status_var.set(f"Imported {count} URL(s) from {os.path.basename(path)}")

    def _insert_url(self, url):
        self.url_tree.insert("", "end", values=("Pending", url, "-"), tags=("pending",))
        self._update_count()

    def _remove_selected(self):
        for iid in self.url_tree.selection():
            self.url_tree.delete(iid)
        self._update_count()

    def _clear_urls(self):
        self.url_tree.delete(*self.url_tree.get_children())
        self._update_count()

    def _update_count(self):
        n = len(self.url_tree.get_children())
        self.count_label.config(text=f"{n} URL(s)")

    def _browse_outdir(self):
        d = filedialog.askdirectory(title="Select download folder")
        if d:
            self.outdir_var.set(d)

    # ── Download control ──────────────────────────────────────────────────
    def _get_urls(self):
        return [self.url_tree.item(iid, "values")[1] for iid in self.url_tree.get_children()]

    def _start_download(self):
        urls = self._get_urls()
        if not urls:
            messagebox.showinfo("No URLs", "Add some URLs first.")
            return

        cfg = self._collect_config()
        cfg["output_dir"] = self.outdir_var.get()
        cfg["mode"] = self.mode_var.get()

        # Reset statuses
        for iid in self.url_tree.get_children():
            url = self.url_tree.item(iid, "values")[1]
            self.url_tree.item(iid, values=("Pending", url, "-"), tags=("pending",))

        self.overall_progress["maximum"] = len(urls)
        self.overall_progress["value"] = 0
        self.progress_label.config(text="Downloading...")
        self.progress_pct_label.config(text=f"0/{len(urls)}")

        self.dl_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.status_var.set("Downloading...")

        self.msg_queue = queue.Queue()
        self.worker = DownloadWorker(urls, cfg, self.msg_queue)
        self.worker.start()
        self._poll_queue()

    def _stop_download(self):
        if self.worker:
            self.worker.stop()
            self.status_var.set("Stopping...")

    def _poll_queue(self):
        try:
            while True:
                msg = self.msg_queue.get_nowait()
                kind = msg["kind"]

                if kind == "log":
                    text = msg["text"]
                    tag = None
                    if "Done" in text:
                        tag = "success"
                    elif "FAIL" in text or "ERROR" in text:
                        tag = "error"
                    elif "Retry" in text:
                        tag = "warning"
                    self._log(text, tag=tag)

                elif kind == "output":
                    text = msg["text"]
                    tag = "dim"
                    if "[download]" in text:
                        tag = "info"
                    self._log(text, tag=tag)

                elif kind == "progress":
                    cur, tot = msg["current"], msg["total"]
                    self.overall_progress["value"] = cur - 1
                    self.progress_label.config(text=f"Downloading [{cur}/{tot}]...")
                    self.progress_pct_label.config(text=f"{cur}/{tot}")

                    items = self.url_tree.get_children()
                    idx = cur - 1
                    if idx < len(items):
                        iid = items[idx]
                        url = self.url_tree.item(iid, "values")[1]
                        self.url_tree.item(iid, values=("Downloading", url, "0%"), tags=("active",))
                        self.url_tree.see(iid)

                elif kind == "item_progress":
                    items = self.url_tree.get_children()
                    idx = msg["index"]
                    pct = msg["percent"]
                    if idx < len(items):
                        iid = items[idx]
                        url = self.url_tree.item(iid, "values")[1]
                        self.url_tree.item(iid, values=("Downloading", url, f"{pct:.0f}%"))

                elif kind == "item_status":
                    items = self.url_tree.get_children()
                    idx = msg["index"]
                    if idx < len(items):
                        iid = items[idx]
                        url = self.url_tree.item(iid, "values")[1]
                        if msg["status"] == "ok":
                            self.url_tree.item(iid, values=("Done", url, "100%"), tags=("ok",))
                        else:
                            self.url_tree.item(iid, values=("FAILED", url, "-"), tags=("fail",))

                elif kind == "done":
                    s, f = msg["success"], msg["failed"]
                    self.overall_progress["value"] = self.overall_progress["maximum"]
                    self.progress_label.config(text=f"Complete - {s} succeeded, {f} failed")
                    self.progress_pct_label.config(text=f"{s+f}/{s+f}")
                    self.status_var.set(f"Done: {s} succeeded, {f} failed")
                    self.dl_btn.config(state="normal")
                    self.stop_btn.config(state="disabled")

                    self._log(f"\n[{timestamp()}] Session complete: {s} succeeded, {f} failed",
                              tag="success" if f == 0 else "error")

                    if f == 0:
                        messagebox.showinfo("Done", f"All {s} download(s) completed successfully!")
                    else:
                        messagebox.showwarning("Done", f"Finished.\n\nSuccess: {s}\nFailed: {f}\n\nCheck Live Output for details.")
                    return
        except queue.Empty:
            pass

        self.after(80, self._poll_queue)

    # ── Log helpers ───────────────────────────────────────────────────────
    def _log(self, text, tag=None):
        self.log_text.config(state="normal")
        if tag:
            self.log_text.insert("end", text + "\n", tag)
        else:
            self.log_text.insert("end", text + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _clear_log(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")

    def _save_log(self):
        content = self.log_text.get("1.0", "end").strip()
        if not content:
            messagebox.showinfo("Log", "Nothing to save.")
            return
        path = filedialog.asksaveasfilename(
            title="Save log",
            defaultextension=".txt",
            initialfile="download_log.txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            self.status_var.set(f"Log saved to {os.path.basename(path)}")

    # ── Settings helpers ──────────────────────────────────────────────────
    def _collect_config(self):
        cfg = {}
        for key in DEFAULT_CONFIG:
            attr = f"cfg_{key}"
            if hasattr(self, attr):
                var = getattr(self, attr)
                val = var.get()
                if isinstance(DEFAULT_CONFIG[key], bool):
                    cfg[key] = bool(val)
                elif isinstance(DEFAULT_CONFIG[key], int):
                    try:
                        cfg[key] = int(val)
                    except (ValueError, TypeError):
                        cfg[key] = DEFAULT_CONFIG[key]
                else:
                    cfg[key] = val
            else:
                cfg[key] = self.config_data.get(key, DEFAULT_CONFIG[key])
        return cfg

    def _save_settings(self):
        cfg = self._collect_config()
        cfg["output_dir"] = self.outdir_var.get()
        cfg["mode"] = self.mode_var.get()
        self.config_data = cfg
        save_config(cfg)
        self.status_var.set("Settings saved to config.json")
        self._log("Settings saved.", tag="success")

    def _reset_settings(self):
        self.config_data = dict(DEFAULT_CONFIG)
        for key, val in DEFAULT_CONFIG.items():
            attr = f"cfg_{key}"
            if hasattr(self, attr):
                getattr(self, attr).set(val)
        self.mode_var.set(DEFAULT_CONFIG["mode"])
        self.outdir_var.set(DEFAULT_CONFIG["output_dir"])
        self.status_var.set("Settings reset to defaults")

    def _update_ytdlp(self):
        self.status_var.set("Updating yt-dlp...")
        self._log("Updating yt-dlp...", tag="info")

        def run():
            try:
                result = subprocess.run(
                    ["yt-dlp", "-U"],
                    capture_output=True, text=True, errors="replace",
                )
                output = (result.stdout + "\n" + result.stderr).strip()
                tag = "success" if result.returncode == 0 else "error"
                self.after(0, lambda: self._log(output, tag=tag))
                if result.returncode == 0:
                    self.after(0, lambda: self.status_var.set("yt-dlp updated successfully"))
                else:
                    self.after(0, lambda: self.status_var.set("yt-dlp update failed"))
            except Exception as e:
                self.after(0, lambda: self._log(f"Error: {e}", tag="error"))
                self.after(0, lambda: self.status_var.set("yt-dlp update failed"))

        threading.Thread(target=run, daemon=True).start()

    # ── Close ─────────────────────────────────────────────────────────────
    def _on_close(self):
        if self.worker and self.worker.is_alive():
            if not messagebox.askyesno("Confirm Exit", "A download is in progress. Quit anyway?"):
                return
            self.worker.stop()
        self.destroy()


# ═══════════════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app = App()
    app.mainloop()
2