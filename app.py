"""
app.py â€” Business Lead Scraper Desktop GUI
Beautiful CustomTkinter app with:
  â€¢ Scraper Tab  â€” configure & run scrapes with live progress
  â€¢ CSV Viewer Tab â€” browse, filter, and open any saved CSV
  â€¢ Desktop shortcut launcher via run_app.bat
"""

import os
import sys
import csv
import threading
import subprocess
import webbrowser
from datetime import datetime
from tkinter import filedialog, messagebox
import tkinter as tk

import customtkinter as ctk

# â”€â”€ Import scraper engine (must be in same folder) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from scraper2 import scrape, save_to_csv
    SCRAPER_OK = True
except ImportError:
    SCRAPER_OK = False

from email_finder_tab import EmailFinderTab
from about_tab import AboutTab

# â”€â”€ Theme â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

ACCENT       = "#4F8EF7"
ACCENT_HOVER = "#3B78E7"
BG           = "#0F1117"
CARD         = "#1A1D27"
CARD2        = "#22263A"
TEXT         = "#E8EAF6"
TEXT_DIM     = "#8892B0"
SUCCESS      = "#43D17A"
WARN         = "#F7A74F"
DANGER       = "#F74F4F"
BORDER       = "#2E3250"


# â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—
# â•‘                         SCRAPER TAB                                     â•‘
# â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

class ScraperTab(ctk.CTkFrame):
    def __init__(self, master, on_csv_ready, **kw):
        super().__init__(master, fg_color=BG, **kw)
        self.on_csv_ready = on_csv_ready
        self._running     = False
        self._results     = []
        self._out_path    = ""
        self._build()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)

        # â”€â”€ Header â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        hdr = ctk.CTkFrame(self, fg_color=CARD, corner_radius=16)
        hdr.grid(row=0, column=0, sticky="ew", padx=24, pady=(24, 12))
        hdr.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            hdr, text="âš¡", font=ctk.CTkFont(size=36)
        ).grid(row=0, column=0, padx=(20, 8), pady=16)

        title_col = ctk.CTkFrame(hdr, fg_color="transparent")
        title_col.grid(row=0, column=1, sticky="w", pady=16)
        ctk.CTkLabel(
            title_col, text="Business Lead Scraper",
            font=ctk.CTkFont("Segoe UI", 22, "bold"), text_color=TEXT
        ).pack(anchor="w")
        ctk.CTkLabel(
            title_col, text="Powered by Google Maps  â€¢  Free  â€¢  No API key",
            font=ctk.CTkFont("Segoe UI", 12), text_color=TEXT_DIM
        ).pack(anchor="w")

        # â”€â”€ Input card â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        card = ctk.CTkFrame(self, fg_color=CARD, corner_radius=16)
        card.grid(row=1, column=0, sticky="ew", padx=24, pady=8)
        card.grid_columnconfigure((0, 1), weight=1)

        def lbl(parent, text, row, col, pady=(8, 2)):
            ctk.CTkLabel(
                parent, text=text,
                font=ctk.CTkFont("Segoe UI", 12, "bold"),
                text_color=TEXT_DIM, anchor="w"
            ).grid(row=row, column=col, sticky="w", padx=20, pady=pady)

        lbl(card, "ðŸ“  Location",  0, 0)
        lbl(card, "ðŸ”  Niche",     0, 1)

        self.inp_loc = ctk.CTkEntry(
            card, placeholder_text="e.g. London, Amsterdam, Dubai",
            height=44, font=ctk.CTkFont("Segoe UI", 13),
            fg_color=CARD2, border_color=BORDER, text_color=TEXT,
            corner_radius=10
        )
        self.inp_loc.grid(row=1, column=0, sticky="ew", padx=(20, 10), pady=(0, 16))

        self.inp_niche = ctk.CTkEntry(
            card, placeholder_text="e.g. plumbers, dentists, restaurants",
            height=44, font=ctk.CTkFont("Segoe UI", 13),
            fg_color=CARD2, border_color=BORDER, text_color=TEXT,
            corner_radius=10
        )
        self.inp_niche.grid(row=1, column=1, sticky="ew", padx=(10, 20), pady=(0, 16))

        lbl(card, "ðŸŒ  Website Filter", 2, 0)
        lbl(card, "ðŸ“Š  Number of Leads  (max 500)", 2, 1)

        self.filter_var = tk.StringVar(value="without")
        filter_row = ctk.CTkFrame(card, fg_color="transparent")
        filter_row.grid(row=3, column=0, sticky="w", padx=20, pady=(0, 16))

        for val, label, color in [
            ("without", "ðŸš«  Without Website", WARN),
            ("with",    "âœ…  With Website",    SUCCESS),
            ("all",     "ðŸ“‹  All",             ACCENT),
        ]:
            ctk.CTkRadioButton(
                filter_row, text=label, variable=self.filter_var, value=val,
                font=ctk.CTkFont("Segoe UI", 12),
                fg_color=color, hover_color=color, border_color=BORDER,
                text_color=TEXT,
            ).pack(side="left", padx=(0, 16))

        self.inp_leads = ctk.CTkEntry(
            card, placeholder_text="50",
            height=44, font=ctk.CTkFont("Segoe UI", 13),
            fg_color=CARD2, border_color=BORDER, text_color=TEXT,
            corner_radius=10
        )
        self.inp_leads.grid(row=3, column=1, sticky="ew", padx=(10, 20), pady=(0, 16))

        # â”€â”€ Run button â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        self.btn_run = ctk.CTkButton(
            self, text="â–¶   Start Scraping",
            height=52, font=ctk.CTkFont("Segoe UI", 15, "bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            corner_radius=12, command=self._start
        )
        self.btn_run.grid(row=2, column=0, sticky="ew", padx=24, pady=8)

        # â”€â”€ Progress card â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        prog_card = ctk.CTkFrame(self, fg_color=CARD, corner_radius=16)
        prog_card.grid(row=3, column=0, sticky="ew", padx=24, pady=8)
        prog_card.grid_columnconfigure(0, weight=1)

        self.status_lbl = ctk.CTkLabel(
            prog_card, text="Ready â€” configure your search above",
            font=ctk.CTkFont("Segoe UI", 12), text_color=TEXT_DIM, anchor="w"
        )
        self.status_lbl.grid(row=0, column=0, padx=20, pady=(16, 6), sticky="w")

        self.progress = ctk.CTkProgressBar(
            prog_card, height=10, corner_radius=5,
            fg_color=CARD2, progress_color=ACCENT
        )
        self.progress.set(0)
        self.progress.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 8))

        count_row = ctk.CTkFrame(prog_card, fg_color="transparent")
        count_row.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 16))

        self.count_lbl = ctk.CTkLabel(
            count_row, text="0 leads found",
            font=ctk.CTkFont("Segoe UI", 12, "bold"), text_color=ACCENT
        )
        self.count_lbl.pack(side="left")

        self.btn_open_csv = ctk.CTkButton(
            count_row, text="ðŸ“‚  Open CSV",
            height=32, width=130, font=ctk.CTkFont("Segoe UI", 11),
            fg_color=CARD2, hover_color=BORDER, text_color=TEXT,
            corner_radius=8, command=self._open_csv, state="disabled"
        )
        self.btn_open_csv.pack(side="right")

        self.btn_open_folder = ctk.CTkButton(
            count_row, text="ðŸ—‚ï¸  Open Folder",
            height=32, width=130, font=ctk.CTkFont("Segoe UI", 11),
            fg_color=CARD2, hover_color=BORDER, text_color=TEXT,
            corner_radius=8, command=self._open_folder, state="disabled"
        )
        self.btn_open_folder.pack(side="right", padx=(0, 8))

        # â”€â”€ Log â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        log_frame = ctk.CTkFrame(self, fg_color=CARD, corner_radius=16)
        log_frame.grid(row=4, column=0, sticky="nsew", padx=24, pady=(8, 24))
        log_frame.grid_columnconfigure(0, weight=1)
        log_frame.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(4, weight=1)

        ctk.CTkLabel(
            log_frame, text="Live Log",
            font=ctk.CTkFont("Segoe UI", 12, "bold"), text_color=TEXT_DIM, anchor="w"
        ).grid(row=0, column=0, padx=20, pady=(12, 4), sticky="w")

        self.log_box = ctk.CTkTextbox(
            log_frame, font=ctk.CTkFont("Consolas", 11),
            fg_color=CARD2, text_color=TEXT, corner_radius=10,
            wrap="word", state="disabled",
        )
        self.log_box.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 16))

    # â”€â”€ Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _log(self, msg: str):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", msg + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _set_status(self, text: str, color: str = TEXT_DIM):
        self.status_lbl.configure(text=text, text_color=color)

    def _handle_progress(self, current, max_leads, name, info=None):
        info = info or {}
        stage = info.get("stage", "lead")

        if stage == "collect":
            raw = info.get("raw", 0)
            raw_total = max(info.get("raw_total", max_leads), 1)
            self.progress.set(min(raw / raw_total * 0.25, 0.25))
            self.count_lbl.configure(text="0 leads found")
            self._set_status(f"Phase 1 - collected {raw} business URLs...", ACCENT)
            return

        if stage == "checking":
            checked = info.get("checked", 0)
            raw_total = max(info.get("raw_total", max_leads), 1)
            pct = 1 if current >= max_leads else 0.25 + min(checked / raw_total, 1) * 0.75
            self.progress.set(pct)
            self.count_lbl.configure(text=f"{current} leads found")
            self._set_status(
                f"Phase 2 - checked {checked}/{raw_total}, saved {current}/{max_leads}...",
                TEXT,
            )
            return

        self.progress.set(current / max(max_leads, 1))
        self.count_lbl.configure(text=f"{current} leads found")
        self._log(f"  Saved [{current:>3}/{max_leads}]  {name}")
        self._set_status(f"Phase 2 - scraped {current}/{max_leads}...", TEXT)

    def _start(self):
        if self._running:
            return

        loc   = self.inp_loc.get().strip()
        niche = self.inp_niche.get().strip()
        try:
            leads = max(1, min(int(self.inp_leads.get().strip() or "50"), 500))
        except ValueError:
            leads = 50

        if not loc or not niche:
            messagebox.showwarning("Missing Input", "Please enter both Location and Niche.")
            return

        if not SCRAPER_OK:
            messagebox.showerror("Import Error", "scraper2.py not found in the same folder.")
            return

        self._running = True
        self._results = []
        self.btn_run.configure(state="disabled", text="â³  Scrapingâ€¦")
        self.btn_open_csv.configure(state="disabled")
        self.btn_open_folder.configure(state="disabled")
        self.progress.set(0)
        self.count_lbl.configure(text="0 leads found")
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

        wf    = self.filter_var.get()
        total = leads

        self._log(f"ðŸš€  Starting scrape: {niche} in {loc}")
        self._log(f"    Filter: {wf} website  |  Target: {total} leads")
        self._log(f"    {'â”€'*50}")
        self._set_status("Phase 1 â€” collecting business URLsâ€¦", ACCENT)

        def on_progress(current, max_leads, name, info=None):
            self.after(0, lambda: self._handle_progress(current, max_leads, name, info))

        def run():
            try:
                results = scrape(niche, loc, total, wf, on_progress)
                self.after(0, lambda: self._done(results, niche, loc))
            except Exception as e:
                self.after(0, lambda: self._error(str(e)))

        threading.Thread(target=run, daemon=True).start()

    def _done(self, results, niche, loc):
        self._running = False
        self.btn_run.configure(state="normal", text="â–¶   Start Scraping")

        if not results:
            self._set_status("No results found. Try a broader niche or city.", WARN)
            self._log("\nâš   No matching businesses found.")
            return

        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = f"leads_{niche.replace(' ','_')}_{loc.replace(' ','_')}_{ts}.csv"
        self._out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), name)
        save_to_csv(results, self._out_path)

        self._results = results
        self.progress.set(1)
        self.count_lbl.configure(text=f"{len(results)} leads saved  âœ“", )
        self.count_lbl.configure(text_color=SUCCESS)
        self.btn_open_csv.configure(state="normal")
        self.btn_open_folder.configure(state="normal")

        self._log(f"\n{'â”€'*52}")
        self._log(f"âœ…  Done!  {len(results)} leads â†’ {name}")
        self._set_status(f"âœ…  {len(results)} leads saved to {name}", SUCCESS)

        self.on_csv_ready(self._out_path)

    def _error(self, msg):
        self._running = False
        self.btn_run.configure(state="normal", text="â–¶   Start Scraping")
        self._set_status(f"Error: {msg}", DANGER)
        self._log(f"\nâœ—  Error: {msg}")

    def _open_csv(self):
        if self._out_path:
            os.startfile(self._out_path)

    def _open_folder(self):
        if self._out_path:
            subprocess.Popen(f'explorer /select,"{self._out_path}"')


# â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—
# â•‘                         CSV VIEWER TAB                                  â•‘
# â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

class CsvViewerTab(ctk.CTkFrame):
    def __init__(self, master, **kw):
        super().__init__(master, fg_color=BG, **kw)
        self._all_rows: list[list] = []
        self._headers:  list[str]  = []
        self._col_widths: list[int] = []
        self._build()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # â”€â”€ Toolbar â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        bar = ctk.CTkFrame(self, fg_color=CARD, corner_radius=14)
        bar.grid(row=0, column=0, sticky="ew", padx=24, pady=(24, 8))
        bar.grid_columnconfigure(2, weight=1)

        ctk.CTkButton(
            bar, text="ðŸ“‚  Open CSV File",
            height=42, font=ctk.CTkFont("Segoe UI", 13, "bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER, corner_radius=10,
            command=self._load_file
        ).grid(row=0, column=0, padx=(16, 8), pady=12)

        ctk.CTkLabel(bar, text="ðŸ”", font=ctk.CTkFont(size=18)).grid(
            row=0, column=1, padx=(8, 0)
        )

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._filter())
        self.search_box = ctk.CTkEntry(
            bar, textvariable=self.search_var,
            placeholder_text="  Filter any columnâ€¦",
            height=42, font=ctk.CTkFont("Segoe UI", 13),
            fg_color=CARD2, border_color=BORDER, text_color=TEXT, corner_radius=10
        )
        self.search_box.grid(row=0, column=2, sticky="ew", padx=8, pady=12)

        self.info_lbl = ctk.CTkLabel(
            bar, text="No file loaded",
            font=ctk.CTkFont("Segoe UI", 11), text_color=TEXT_DIM
        )
        self.info_lbl.grid(row=0, column=3, padx=16)

        ctk.CTkButton(
            bar, text="ðŸ”—  Open Website",
            height=42, font=ctk.CTkFont("Segoe UI", 12),
            fg_color=CARD2, hover_color=BORDER, text_color=TEXT, corner_radius=10,
            command=self._open_selected_website
        ).grid(row=0, column=4, padx=(0, 16), pady=12)

        # â”€â”€ Stats cards â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        self.stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.stats_frame.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 8))

        self.stat_total   = self._stat_card("Total Leads",        "0")
        self.stat_with    = self._stat_card("With Website",       "0")
        self.stat_without = self._stat_card("Without Website",    "0")
        self.stat_phone   = self._stat_card("Have Phone",         "0")

        # â”€â”€ Table â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        tbl_outer = ctk.CTkFrame(self, fg_color=CARD, corner_radius=16)
        tbl_outer.grid(row=2, column=0, sticky="nsew", padx=24, pady=(0, 24))
        tbl_outer.grid_columnconfigure(0, weight=1)
        tbl_outer.grid_rowconfigure(0, weight=1)

        # Use plain tk for the table (CTk has no Treeview equivalent)
        import tkinter.ttk as ttk

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Custom.Treeview",
            background=CARD2, foreground=TEXT,
            fieldbackground=CARD2, borderwidth=0,
            rowheight=32, font=("Segoe UI", 11),
        )
        style.configure("Custom.Treeview.Heading",
            background=CARD, foreground=TEXT_DIM,
            font=("Segoe UI", 11, "bold"), relief="flat",
        )
        style.map("Custom.Treeview",
            background=[("selected", ACCENT)],
            foreground=[("selected", "white")],
        )

        self.tree = ttk.Treeview(
            tbl_outer, style="Custom.Treeview",
            selectmode="browse", show="headings"
        )

        vsb = ttk.Scrollbar(tbl_outer, orient="vertical",   command=self.tree.yview)
        hsb = ttk.Scrollbar(tbl_outer, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew", padx=(12, 0), pady=(12, 0))
        vsb.grid (row=0, column=1, sticky="ns",  pady=(12, 0))
        hsb.grid (row=1, column=0, sticky="ew",  padx=(12, 0))

        # Stripe rows
        self.tree.tag_configure("even", background=CARD2)
        self.tree.tag_configure("odd",  background="#1E2235")
        self.tree.tag_configure("has_website",    foreground=SUCCESS)
        self.tree.tag_configure("no_website",     foreground=WARN)

        self._filtered_rows: list[list] = []

    def _stat_card(self, label: str, value: str) -> ctk.CTkLabel:
        card = ctk.CTkFrame(self.stats_frame, fg_color=CARD, corner_radius=12)
        card.pack(side="left", padx=(0, 8), pady=4, fill="x", expand=True)
        val_lbl = ctk.CTkLabel(
            card, text=value,
            font=ctk.CTkFont("Segoe UI", 22, "bold"), text_color=ACCENT
        )
        val_lbl.pack(padx=20, pady=(10, 2))
        ctk.CTkLabel(
            card, text=label,
            font=ctk.CTkFont("Segoe UI", 10), text_color=TEXT_DIM
        ).pack(padx=20, pady=(0, 10))
        return val_lbl

    def _update_stats(self, rows):
        total   = len(rows)
        with_w  = sum(1 for r in rows if len(r) > 4 and r[4].strip())
        without = total - with_w
        with_ph = sum(1 for r in rows if len(r) > 3 and r[3].strip())
        self.stat_total.configure(text=str(total))
        self.stat_with.configure(text=str(with_w))
        self.stat_without.configure(text=str(without))
        self.stat_phone.configure(text=str(with_ph))

    def load_csv(self, path: str):
        """Load a CSV file into the viewer."""
        try:
            with open(path, encoding="utf-8-sig", newline="") as f:
                reader = csv.reader(f)
                rows   = list(reader)
        except Exception as e:
            messagebox.showerror("CSV Error", str(e))
            return

        if not rows:
            return

        self._headers = rows[0]
        self._all_rows = rows[1:]

        # Estimate column widths
        self._col_widths = []
        for i, h in enumerate(self._headers):
            max_w = len(h) * 10
            for row in self._all_rows[:50]:
                if i < len(row):
                    max_w = max(max_w, min(len(row[i]) * 8, 320))
            self._col_widths.append(max(80, max_w))

        # Set up treeview columns
        self.tree["columns"] = self._headers
        for h, w in zip(self._headers, self._col_widths):
            self.tree.heading(h, text=h, anchor="w")
            self.tree.column(h, width=w, minwidth=60, anchor="w")

        fname = os.path.basename(path)
        self.info_lbl.configure(text=f"ðŸ“„  {fname}  ({len(self._all_rows)} rows)")
        self._filter()

    def _filter(self):
        q = self.search_var.get().lower().strip()
        self._filtered_rows = [
            r for r in self._all_rows
            if not q or any(q in cell.lower() for cell in r)
        ]
        self._render()
        self._update_stats(self._filtered_rows)

    def _render(self):
        self.tree.delete(*self.tree.get_children())
        for i, row in enumerate(self._filtered_rows):
            tag = "even" if i % 2 == 0 else "odd"
            # Colour by website presence
            website = row[4].strip() if len(row) > 4 else ""
            site_tag = "has_website" if website else "no_website"
            self.tree.insert("", "end", values=row, tags=(tag, site_tag))

    def _load_file(self):
        path = filedialog.askopenfilename(
            title="Open leads CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialdir=os.path.dirname(os.path.abspath(__file__)),
        )
        if path:
            self.load_csv(path)

    def _open_selected_website(self):
        sel = self.tree.selection()
        if not sel:
            return
        vals = self.tree.item(sel[0], "values")
        # Website is column index 4
        if len(vals) > 4 and vals[4].strip():
            url = vals[4].strip()
            if not url.startswith("http"):
                url = "https://" + url
            webbrowser.open(url)


# â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—
# â•‘                         MAIN APP WINDOW                                 â•‘
# â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

class App(ctk.CTk):
    def __init__(self, tier: str = "Pro"):
        super().__init__()
        self._tier = tier

        self.title("Business Lead Scraper")
        self.geometry("1100x780")
        self.minsize(900, 640)
        self.configure(fg_color=BG)

        # Window icon (emoji fallback)
        try:
            self.iconbitmap(default="")
        except Exception:
            pass

        self._build()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # â”€â”€ Top nav bar â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        nav = ctk.CTkFrame(self, fg_color=CARD, corner_radius=0, height=54)
        nav.grid(row=0, column=0, sticky="ew")
        nav.grid_propagate(False)
        nav.grid_columnconfigure(2, weight=1)

        ctk.CTkLabel(
            nav, text="âš¡ Lead Scraper",
            font=ctk.CTkFont("Segoe UI", 16, "bold"), text_color=TEXT
        ).grid(row=0, column=0, padx=24, pady=12)

        # Tab buttons
        self._tab_btns: dict[str, ctk.CTkButton] = {}
        self._frames:   dict[str, ctk.CTkFrame]  = {}

        for i, (key, icon, label) in enumerate([
            ("scraper", "ðŸ•·ï¸", "Scraper"),
            ("viewer",  "ðŸ“Š", "CSV Viewer"),
            ("finder",  "ðŸ“§", "Email Finder"),
            ("about",   "â„¹ï¸",  "About"),
        ]):
            btn = ctk.CTkButton(
                nav, text=f"{icon}  {label}",
                height=38, width=140,
                font=ctk.CTkFont("Segoe UI", 12, "bold"),
                fg_color="transparent", hover_color=CARD2,
                text_color=TEXT_DIM, corner_radius=8,
                command=lambda k=key: self._switch(k)
            )
            btn.grid(row=0, column=i + 1, padx=(4, 0), pady=8)
            self._tab_btns[key] = btn

        # â”€â”€ Content area â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        self.content = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self.content.grid(row=1, column=0, sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

        self._csv_viewer = CsvViewerTab(self.content)
        self._csv_viewer.grid(row=0, column=0, sticky="nsew")

        self._email_finder = EmailFinderTab(self.content)
        self._email_finder.grid(row=0, column=0, sticky="nsew")

        self._about_tab = AboutTab(self.content, tier=self._tier)
        self._about_tab.grid(row=0, column=0, sticky="nsew")

        self._scraper_tab = ScraperTab(self.content, on_csv_ready=self._on_csv_ready)
        self._scraper_tab.grid(row=0, column=0, sticky="nsew")

        self._frames = {
            "scraper": self._scraper_tab,
            "viewer":  self._csv_viewer,
            "finder":  self._email_finder,
            "about":   self._about_tab,
        }

        self._switch("scraper")

    def _switch(self, key: str):
        for k, btn in self._tab_btns.items():
            if k == key:
                btn.configure(fg_color=ACCENT, text_color="white")
            else:
                btn.configure(fg_color="transparent", text_color=TEXT_DIM)

        for k, frame in self._frames.items():
            if k == key:
                frame.tkraise()

    def _on_csv_ready(self, path: str):
        """Called after a scrape completes â€” auto-load CSV in viewer."""
        self._csv_viewer.load_csv(path)
        self._email_finder.set_csv(path)


# â”€â”€ Entry point â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def main():
    # â”€â”€ License gate â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    from license_dialog import check_license
    valid, tier = check_license()
    if not valid:
        return   # user closed the dialog without activating

    # â”€â”€ Launch main app â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    app = App(tier=tier)
    app.mainloop()


if __name__ == "__main__":
    main()
