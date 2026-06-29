"""
about_tab.py  —  About / Branding Tab for Lead Scraper by Rolzah
=================================================================
Shows app info, your branding, license status, and contact links.
"""

import webbrowser
import customtkinter as ctk
from license_system import deactivate, APP_VERSION

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

INSTAGRAM_URL = "https://instagram.com/rolzah_"
WEBSITE_URL   = "https://exclusieftech.nl"


class AboutTab(ctk.CTkFrame):
    def __init__(self, master, tier: str = "Pro", **kw):
        super().__init__(master, fg_color=BG, **kw)
        self._tier = tier
        self._build()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        # ── Hero card ─────────────────────────────────────────────────────
        hero = ctk.CTkFrame(self, fg_color=CARD, corner_radius=20)
        hero.grid(row=0, column=0, sticky="ew", padx=40, pady=(40, 16))
        hero.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            hero, text="⚡",
            font=ctk.CTkFont(size=56)
        ).grid(row=0, column=0, pady=(32, 4))

        ctk.CTkLabel(
            hero, text="Lead Scraper Pro",
            font=ctk.CTkFont("Segoe UI", 28, "bold"), text_color=TEXT
        ).grid(row=1, column=0)

        ctk.CTkLabel(
            hero, text=f"Version {APP_VERSION}  •  by ExclusiefTech.nl",
            font=ctk.CTkFont("Segoe UI", 13), text_color=TEXT_DIM
        ).grid(row=2, column=0, pady=(4, 0))

        # License badge
        tier_color = SUCCESS if self._tier not in ("dev", "") else WARN
        tier_text  = f"  ✓  {self._tier.upper()} LICENSE  " if self._tier else "  ⚠  UNACTIVATED  "
        badge = ctk.CTkFrame(hero, fg_color=CARD2, corner_radius=20)
        badge.grid(row=3, column=0, pady=(16, 32))
        ctk.CTkLabel(
            badge, text=tier_text,
            font=ctk.CTkFont("Segoe UI", 12, "bold"), text_color=tier_color
        ).grid(padx=20, pady=8)

        # ── Stats row ─────────────────────────────────────────────────────
        stats = ctk.CTkFrame(self, fg_color="transparent")
        stats.grid(row=1, column=0, sticky="ew", padx=40, pady=8)
        stats.grid_columnconfigure((0, 1, 2), weight=1)

        for col, (icon, label, val) in enumerate([
            ("🌍", "Data Source",  "Google Maps"),
            ("📧", "Email Finder", "9-page crawler"),
            ("🔒", "Privacy",      "No data sold"),
        ]):
            c = ctk.CTkFrame(stats, fg_color=CARD, corner_radius=14)
            c.grid(row=0, column=col, sticky="ew", padx=(0 if col == 0 else 8, 0))
            ctk.CTkLabel(c, text=icon, font=ctk.CTkFont(size=28)).pack(pady=(16, 4))
            ctk.CTkLabel(c, text=label, font=ctk.CTkFont("Segoe UI", 10),
                         text_color=TEXT_DIM).pack()
            ctk.CTkLabel(c, text=val,   font=ctk.CTkFont("Segoe UI", 12, "bold"),
                         text_color=TEXT).pack(pady=(2, 16))

        # ── Contact / links ───────────────────────────────────────────────
        links = ctk.CTkFrame(self, fg_color=CARD, corner_radius=16)
        links.grid(row=2, column=0, sticky="ew", padx=40, pady=8)
        links.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(
            links, text="Contact & Links",
            font=ctk.CTkFont("Segoe UI", 13, "bold"), text_color=TEXT_DIM, anchor="w"
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=20, pady=(16, 8))

        ctk.CTkButton(
            links, text="📸  @rolzah_  on Instagram",
            height=44, font=ctk.CTkFont("Segoe UI", 13),
            fg_color=CARD2, hover_color=BORDER, text_color=TEXT, corner_radius=10,
            command=lambda: webbrowser.open(INSTAGRAM_URL)
        ).grid(row=1, column=0, sticky="ew", padx=(20, 8), pady=(0, 16))

        ctk.CTkButton(
            links, text="🌐  ExclusiefTech.nl",
            height=44, font=ctk.CTkFont("Segoe UI", 13),
            fg_color=CARD2, hover_color=BORDER, text_color=TEXT, corner_radius=10,
            command=lambda: webbrowser.open(WEBSITE_URL)
        ).grid(row=1, column=1, sticky="ew", padx=(0, 20), pady=(0, 16))

        # ── Deactivate ────────────────────────────────────────────────────
        foot = ctk.CTkFrame(self, fg_color="transparent")
        foot.grid(row=3, column=0, sticky="s", pady=(0, 32))

        ctk.CTkButton(
            foot, text="🔓  Deactivate License  (switch key)",
            height=36, width=260,
            font=ctk.CTkFont("Segoe UI", 11),
            fg_color="transparent", hover_color=CARD,
            text_color=TEXT_DIM, corner_radius=8,
            border_width=1, border_color=BORDER,
            command=self._deactivate
        ).pack()

        ctk.CTkLabel(
            foot,
            text="© 2025 ExclusiefTech.nl — All rights reserved",
            font=ctk.CTkFont("Segoe UI", 9), text_color=BORDER
        ).pack(pady=(8, 0))

    def _deactivate(self):
        deactivate()
        from tkinter import messagebox
        messagebox.showinfo(
            "Deactivated",
            "License cleared.\nRestart the app to enter a new key."
        )
