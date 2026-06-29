"""
email_finder_tab.py  —  Email Finder Tab for Business Lead Scraper
===================================================================
Paste this file in the same folder as app.py and scraper2.py.

Then add these two lines to app.py:

  1) At the top imports section, add:
        from email_finder_tab import EmailFinderTab

  2) In App._build(), inside the tab loop, add a third tab entry:
        ("finder", "📧", "Email Finder"),

  3) After self._csv_viewer is created, add:
        self._email_finder = EmailFinderTab(self.content)
        self._email_finder.grid(row=0, column=0, sticky="nsew")

  4) Add to self._frames dict:
        "finder": self._email_finder

  5) In _on_csv_ready(), add at the bottom:
        self._email_finder.set_csv(path)

That's it. Everything else is self-contained here.
"""

import os
import re
import csv
import time
import threading
import tkinter as tk
import tkinter.ttk as ttk
from tkinter import filedialog, messagebox
from urllib.parse import urlparse

import customtkinter as ctk

try:
    import requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

# ── Match app.py theme exactly ───────────────────────────────────────────────
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

EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]{2,}")
JUNK     = [
    "example", "youremail", "test@", "email@", "user@", "info@example",
    ".png", ".jpg", ".gif", ".svg", ".webp", "sentry", "wixpress",
    "squarespace", "shopify", "wordpress", "schema", "w3.org",
    "noreply", "no-reply", "donotreply", "//t.", "unsubscribe",
    "privacy", "support@sentry", "googleapis", "intl-segmenter",
    "segmenter", "v1.", "v2.", "v3.", "11.7.", "node_modules",
]
HEADERS  = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def clean_emails(raw: list) -> list:
    out = []
    seen = set()
    # Patterns that look like script imports or package names
    BAD_PATTERNS = [
        r"\d+\.\d+\.\d+", # Version numbers (e.g. @1.2.3)
        r"segmenter", r"intl", r"node_modules", r"bootstrap",
        r"jquery", r"webpack", r"npm", r"yarn", r"github", r"sentry",
    ]
    
    for e in raw:
        e = e.strip().lower()
        if any(j in e for j in JUNK):
            continue
        if any(re.search(p, e) for p in BAD_PATTERNS):
            continue
            
        parts = e.split("@")
        if len(parts) != 2:
            continue
        
        # Local part should be reasonable
        local_part = parts[0]
        if len(local_part) < 2 or len(local_part) > 64:
            continue
            
        domain_parts = parts[1].split(".")
        if len(domain_parts) < 2 or len(domain_parts[-1]) < 2:
            continue
        if len(e) > 80:
            continue
        if e not in seen:
            seen.add(e)
            out.append(e)
    return out


def scrape_email_from_website(website: str) -> str:
    """Visit website + contact/about pages, return first clean email found."""
    if not website or not website.strip():
        return ""
    try:
        url = website.strip()
        if not url.startswith("http"):
            url = "https://" + url

        base = url.rstrip("/")
        pages = [
            base,
            base + "/contact",
            base + "/contact-us",
            base + "/about",
            base + "/about-us",
            base + "/get-in-touch",
            base + "/reach-us",
            base + "/over-ons",       # Dutch
            base + "/kontakt",         # German
            base + "/impressum",       # German legal page — always has email
        ]

        for page_url in pages:
            try:
                r = requests.get(
                    page_url, headers=HEADERS,
                    timeout=7, allow_redirects=True
                )
                if r.status_code >= 400:
                    continue
                emails = clean_emails(EMAIL_RE.findall(r.text))
                if emails:
                    return emails[0]
            except Exception:
                continue

    except Exception:
        pass
    return ""


class EmailFinderTab(ctk.CTkFrame):
    def __init__(self, master, **kw):
        super().__init__(master, fg_color=BG, **kw)
        self._csv_path   = ""
        self._rows       = []       # list of dicts from CSV
        self._running    = False
        self._stop_flag  = False
        self._emails     = []       # found emails in order
        self._build()

    # ─────────────────────────────────────────────────────────────────────
    # UI BUILD
    # ─────────────────────────────────────────────────────────────────────

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        # ── Header ────────────────────────────────────────────────────────
        hdr = ctk.CTkFrame(self, fg_color=CARD, corner_radius=16)
        hdr.grid(row=0, column=0, sticky="ew", padx=24, pady=(24, 12))
        hdr.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(hdr, text="📧", font=ctk.CTkFont(size=36)).grid(
            row=0, column=0, padx=(20, 8), pady=16
        )
        col = ctk.CTkFrame(hdr, fg_color="transparent")
        col.grid(row=0, column=1, sticky="w", pady=16)
        ctk.CTkLabel(
            col, text="Email Finder",
            font=ctk.CTkFont("Segoe UI", 22, "bold"), text_color=TEXT
        ).pack(anchor="w")
        ctk.CTkLabel(
            col,
            text="Opens every business website → scrapes email → saves to TXT",
            font=ctk.CTkFont("Segoe UI", 12), text_color=TEXT_DIM
        ).pack(anchor="w")

        # ── Controls ──────────────────────────────────────────────────────
        ctrl = ctk.CTkFrame(self, fg_color=CARD, corner_radius=16)
        ctrl.grid(row=1, column=0, sticky="ew", padx=24, pady=8)
        ctrl.grid_columnconfigure(1, weight=1)

        # CSV path display
        ctk.CTkLabel(
            ctrl, text="📂  CSV File",
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            text_color=TEXT_DIM, anchor="w"
        ).grid(row=0, column=0, padx=20, pady=(16, 4), sticky="w")

        path_row = ctk.CTkFrame(ctrl, fg_color="transparent")
        path_row.grid(row=1, column=0, columnspan=3, sticky="ew",
                      padx=20, pady=(0, 16))
        path_row.grid_columnconfigure(0, weight=1)

        self.path_lbl = ctk.CTkLabel(
            path_row,
            text="No CSV loaded — run the Scraper tab first, or open a file below",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=TEXT_DIM, anchor="w"
        )
        self.path_lbl.grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            path_row, text="📂  Browse CSV",
            height=36, width=130,
            font=ctk.CTkFont("Segoe UI", 11),
            fg_color=CARD2, hover_color=BORDER,
            text_color=TEXT, corner_radius=8,
            command=self._browse_csv
        ).grid(row=0, column=1, padx=(12, 0))

        # Buttons row
        btn_row = ctk.CTkFrame(ctrl, fg_color="transparent")
        btn_row.grid(row=2, column=0, columnspan=3, sticky="ew",
                     padx=20, pady=(0, 16))

        self.btn_start = ctk.CTkButton(
            btn_row, text="▶   Find Emails",
            height=48, font=ctk.CTkFont("Segoe UI", 14, "bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            corner_radius=12, command=self._start,
            state="disabled"
        )
        self.btn_start.pack(side="left", padx=(0, 8))

        self.btn_stop = ctk.CTkButton(
            btn_row, text="⏹  Stop",
            height=48, width=100,
            font=ctk.CTkFont("Segoe UI", 13),
            fg_color=DANGER, hover_color="#C43F3F",
            corner_radius=12, command=self._stop,
            state="disabled"
        )
        self.btn_stop.pack(side="left", padx=(0, 16))

        self.btn_save = ctk.CTkButton(
            btn_row, text="💾  Save TXT",
            height=48, width=130,
            font=ctk.CTkFont("Segoe UI", 13),
            fg_color=SUCCESS, hover_color="#35A862",
            corner_radius=12, command=self._save_txt,
            state="disabled", text_color="#000000"
        )
        self.btn_save.pack(side="left")

        self.btn_copy = ctk.CTkButton(
            btn_row, text="📋  Copy All",
            height=48, width=130,
            font=ctk.CTkFont("Segoe UI", 13),
            fg_color=CARD2, hover_color=BORDER,
            corner_radius=12, command=self._copy_all,
            state="disabled"
        )
        self.btn_copy.pack(side="left", padx=(8, 0))

        # ── Progress bar ──────────────────────────────────────────────────
        prog_card = ctk.CTkFrame(self, fg_color=CARD, corner_radius=16)
        prog_card.grid(row=2, column=0, sticky="ew", padx=24, pady=8)
        prog_card.grid_columnconfigure(0, weight=1)

        self.status_lbl = ctk.CTkLabel(
            prog_card,
            text="Load a CSV and click Find Emails to start",
            font=ctk.CTkFont("Segoe UI", 12), text_color=TEXT_DIM, anchor="w"
        )
        self.status_lbl.grid(row=0, column=0, padx=20, pady=(14, 6), sticky="w")

        self.progress = ctk.CTkProgressBar(
            prog_card, height=10, corner_radius=5,
            fg_color=CARD2, progress_color=ACCENT
        )
        self.progress.set(0)
        self.progress.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 6))

        stats_row = ctk.CTkFrame(prog_card, fg_color="transparent")
        stats_row.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 14))

        self.found_lbl = ctk.CTkLabel(
            stats_row, text="0 emails found",
            font=ctk.CTkFont("Segoe UI", 12, "bold"), text_color=SUCCESS
        )
        self.found_lbl.pack(side="left")

        self.checked_lbl = ctk.CTkLabel(
            stats_row, text="  |  0 checked",
            font=ctk.CTkFont("Segoe UI", 12), text_color=TEXT_DIM
        )
        self.checked_lbl.pack(side="left")

        self.skipped_lbl = ctk.CTkLabel(
            stats_row, text="  |  0 no website",
            font=ctk.CTkFont("Segoe UI", 12), text_color=WARN
        )
        self.skipped_lbl.pack(side="left")

        # ── Results table + email list ─────────────────────────────────────
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=3, column=0, sticky="nsew", padx=24, pady=(0, 24))
        bottom.grid_columnconfigure(0, weight=3)
        bottom.grid_columnconfigure(1, weight=2)
        bottom.grid_rowconfigure(0, weight=1)

        # Left — results table
        tbl_frame = ctk.CTkFrame(bottom, fg_color=CARD, corner_radius=16)
        tbl_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        tbl_frame.grid_columnconfigure(0, weight=1)
        tbl_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            tbl_frame, text="Results",
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            text_color=TEXT_DIM, anchor="w"
        ).grid(row=0, column=0, padx=16, pady=(12, 4), sticky="w")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("EF.Treeview",
            background=CARD2, foreground=TEXT,
            fieldbackground=CARD2, borderwidth=0,
            rowheight=28, font=("Segoe UI", 10),
        )
        style.configure("EF.Treeview.Heading",
            background=CARD, foreground=TEXT_DIM,
            font=("Segoe UI", 10, "bold"), relief="flat",
        )
        style.map("EF.Treeview",
            background=[("selected", ACCENT)],
            foreground=[("selected", "white")],
        )

        cols = ("Business", "Email", "Status")
        self.tree = ttk.Treeview(
            tbl_frame, columns=cols,
            show="headings", style="EF.Treeview"
        )
        self.tree.heading("Business", text="Business Name")
        self.tree.heading("Email",    text="Email Found")
        self.tree.heading("Status",   text="Status")
        self.tree.column("Business", width=200, minwidth=120)
        self.tree.column("Email",    width=220, minwidth=120)
        self.tree.column("Status",   width=100, minwidth=80)

        self.tree.tag_configure("found",    foreground=SUCCESS)
        self.tree.tag_configure("notfound", foreground=WARN)
        self.tree.tag_configure("nosite",   foreground=TEXT_DIM)
        self.tree.tag_configure("checking", foreground=ACCENT)

        vsb = ttk.Scrollbar(tbl_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)

        self.tree.grid(row=1, column=0, sticky="nsew", padx=(12, 0), pady=(0, 12))
        vsb.grid(row=1, column=1, sticky="ns", pady=(0, 12))

        # Right — email box
        email_frame = ctk.CTkFrame(bottom, fg_color=CARD, corner_radius=16)
        email_frame.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        email_frame.grid_columnconfigure(0, weight=1)
        email_frame.grid_rowconfigure(1, weight=1)

        hdr_row = ctk.CTkFrame(email_frame, fg_color="transparent")
        hdr_row.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 4))
        ctk.CTkLabel(
            hdr_row, text="📧  Found Emails",
            font=ctk.CTkFont("Segoe UI", 12, "bold"), text_color=TEXT_DIM
        ).pack(side="left")
        ctk.CTkLabel(
            hdr_row,
            text="Copy → paste into bulk sender",
            font=ctk.CTkFont("Segoe UI", 10), text_color=TEXT_DIM
        ).pack(side="right")

        self.email_box = ctk.CTkTextbox(
            email_frame,
            font=ctk.CTkFont("Consolas", 11),
            fg_color=CARD2, text_color=SUCCESS,
            corner_radius=10, wrap="none",
            state="disabled",
        )
        self.email_box.grid(row=1, column=0, sticky="nsew",
                            padx=12, pady=(0, 12))

    # ─────────────────────────────────────────────────────────────────────
    # PUBLIC
    # ─────────────────────────────────────────────────────────────────────

    def set_csv(self, path: str):
        """Called automatically when scraper finishes."""
        self._load_csv(path)

    # ─────────────────────────────────────────────────────────────────────
    # INTERNAL
    # ─────────────────────────────────────────────────────────────────────

    def _browse_csv(self):
        path = filedialog.askopenfilename(
            title="Select leads CSV",
            filetypes=[("CSV files", "*.csv"), ("All", "*.*")],
            initialdir=os.path.dirname(os.path.abspath(__file__)),
        )
        if path:
            self._load_csv(path)

    def _load_csv(self, path: str):
        self._csv_path = path
        self._rows     = []

        try:
            with open(path, encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    self._rows.append(row)
        except Exception as e:
            messagebox.showerror("CSV Error", str(e))
            return

        fname = os.path.basename(path)
        total = len(self._rows)
        has_w = sum(1 for r in self._rows if r.get("Website", "").strip())

        self.path_lbl.configure(
            text=f"{fname}  —  {total} businesses  |  {has_w} with website",
            text_color=TEXT
        )

        # Pre-populate table
        self.tree.delete(*self.tree.get_children())
        self._emails = []
        self.email_box.configure(state="normal")
        self.email_box.delete("1.0", "end")
        self.email_box.configure(state="disabled")
        self.found_lbl.configure(text="0 emails found")
        self.checked_lbl.configure(text=f"  |  0/{total} checked")
        self.skipped_lbl.configure(text="  |  0 no website")
        self.progress.set(0)
        self.btn_save.configure(state="disabled")
        self.btn_copy.configure(state="disabled")

        for row in self._rows:
            name = row.get("Name", "Unknown")
            site = row.get("Website", "").strip()
            tag  = "nosite" if not site else ""
            status = "No website" if not site else "Pending"
            self.tree.insert("", "end",
                             values=(name, "", status),
                             tags=(tag,))

        if has_w == 0:
            self.status_lbl.configure(
                text="⚠  None of these businesses have a website — no emails to find.",
                text_color=WARN
            )
            self.btn_start.configure(state="disabled")
        else:
            self.status_lbl.configure(
                text=f"Ready — will check {has_w} websites for emails",
                text_color=TEXT_DIM
            )
            self.btn_start.configure(state="normal")

    def _start(self):
        if self._running or not self._rows:
            return
        if not REQUESTS_OK:
            messagebox.showerror(
                "Missing Package",
                "Install requests first:\n\n  pip install requests"
            )
            return

        self._running   = True
        self._stop_flag = False
        self._emails    = []

        self.btn_start.configure(state="disabled", text="⏳  Running…")
        self.btn_stop.configure(state="normal")
        self.btn_save.configure(state="disabled")
        self.btn_copy.configure(state="disabled")

        # Reset table
        self.tree.delete(*self.tree.get_children())
        for row in self._rows:
            name   = row.get("Name", "Unknown")
            site   = row.get("Website", "").strip()
            status = "No website" if not site else "Pending"
            tag    = "nosite" if not site else ""
            self.tree.insert("", "end",
                             values=(name, "", status),
                             tags=(tag,))

        self.email_box.configure(state="normal")
        self.email_box.delete("1.0", "end")
        self.email_box.configure(state="disabled")

        threading.Thread(target=self._run, daemon=True).start()

    def _stop(self):
        self._stop_flag = True
        self.status_lbl.configure(text="Stopping after current business…",
                                  text_color=WARN)

    def _run(self):
        total      = len(self._rows)
        checked    = 0
        found      = 0
        no_website = 0
        tree_ids   = self.tree.get_children()

        for i, row in enumerate(self._rows):
            if self._stop_flag:
                break

            name    = row.get("Name", "Unknown")
            website = row.get("Website", "").strip()
            iid     = tree_ids[i] if i < len(tree_ids) else None

            if not website:
                no_website += 1
                self.after(0, lambda iid=iid: self.tree.item(
                    iid, values=(name, "—", "No website"), tags=("nosite",)
                ) if iid else None)
                self.after(0, lambda ns=no_website: self.skipped_lbl.configure(
                    text=f"  |  {ns} no website"
                ))
                continue

            # Mark as checking
            self.after(0, lambda iid=iid, n=name: self.tree.item(
                iid, values=(n, "checking…", "Checking"), tags=("checking",)
            ) if iid else None)
            self.after(0, lambda n=name: self.status_lbl.configure(
                text=f"🔍  {n[:55]}…", text_color=ACCENT
            ))

            email = scrape_email_from_website(website)
            checked += 1
            pct = checked / max(sum(1 for r in self._rows if r.get("Website","").strip()), 1)

            if email:
                found += 1
                self._emails.append(email)
                self.after(0, lambda iid=iid, n=name, em=email: self.tree.item(
                    iid, values=(n, em, "✅ Found"), tags=("found",)
                ) if iid else None)
                self.after(0, lambda em=email: self._append_email(em))
            else:
                self.after(0, lambda iid=iid, n=name: self.tree.item(
                    iid, values=(n, "—", "Not found"), tags=("notfound",)
                ) if iid else None)

            self.after(0, lambda f=found: self.found_lbl.configure(
                text=f"{f} emails found"
            ))
            self.after(0, lambda c=checked, t=sum(
                1 for r in self._rows if r.get("Website","").strip()
            ): self.checked_lbl.configure(
                text=f"  |  {c}/{t} checked"
            ))
            self.after(0, lambda p=pct: self.progress.set(p))

            time.sleep(0.5)  # polite delay

        self.after(0, self._done)

    def _append_email(self, email: str):
        self.email_box.configure(state="normal")
        self.email_box.insert("end", email + "\n")
        self.email_box.see("end")
        self.email_box.configure(state="disabled")

    def _done(self):
        self._running = False
        self.btn_start.configure(state="normal", text="▶   Find Emails")
        self.btn_stop.configure(state="disabled")

        total_found = len(self._emails)

        if total_found > 0:
            self.btn_save.configure(state="normal")
            self.btn_copy.configure(state="normal")
            self.status_lbl.configure(
                text=f"✅  Done! {total_found} emails found — copy or save to TXT",
                text_color=SUCCESS
            )
            self.progress.set(1)
            self._auto_save()
        else:
            self.status_lbl.configure(
                text="Done — no emails found. These businesses keep email private.",
                text_color=WARN
            )

    def _auto_save(self):
        """Auto-save TXT next to the CSV as soon as scraping finishes."""
        if not self._emails or not self._csv_path:
            return
        base    = os.path.splitext(self._csv_path)[0]
        outpath = base + "_emails.txt"
        try:
            with open(outpath, "w", encoding="utf-8") as f:
                f.write("\n".join(self._emails))
            self.status_lbl.configure(
                text=f"✅  {len(self._emails)} emails found  •  Auto-saved: {os.path.basename(outpath)}",
                text_color=SUCCESS
            )
        except Exception:
            pass

    def _save_txt(self):
        if not self._emails:
            return
        default = ""
        if self._csv_path:
            default = os.path.splitext(self._csv_path)[0] + "_emails.txt"

        path = filedialog.asksaveasfilename(
            title="Save emails as TXT",
            defaultextension=".txt",
            filetypes=[("Text file", "*.txt")],
            initialfile=os.path.basename(default) if default else "emails.txt",
            initialdir=os.path.dirname(default) if default else os.getcwd(),
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(self._emails))
            messagebox.showinfo(
                "Saved",
                f"{len(self._emails)} emails saved to:\n{path}"
            )

    def _copy_all(self):
        if not self._emails:
            return
        text = "\n".join(self._emails)
        self.clipboard_clear()
        self.clipboard_append(text)
        self.btn_copy.configure(text="✅  Copied!")
        self.after(2000, lambda: self.btn_copy.configure(text="📋  Copy All"))