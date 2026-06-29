"""
license_dialog.py  —  Premium animated license gate for Lead Scraper by Rolzah
"""

import tkinter as tk
import customtkinter as ctk
import webbrowser
import threading
from license_system import validate_key, get_cached_key

ACCENT       = "#4F8EF7"
ACCENT_HOVER = "#3B78E7"
ACCENT_DIM   = "#2A4A8A"
BG           = "#0A0D14"
BG2          = "#0F1117"
CARD         = "#14171F"
CARD2        = "#1C2030"
CARD3        = "#222840"
TEXT         = "#E8EAF6"
TEXT_DIM     = "#6B7394"
TEXT_MID     = "#9AA3C2"
SUCCESS      = "#2ECC71"
SUCCESS_DIM  = "#1A6B3C"
WARN         = "#F39C12"
DANGER       = "#E74C3C"
DANGER_DIM   = "#7B1F1F"
BORDER       = "#1E2340"
GLOW         = "#4F8EF720"

INSTAGRAM_URL = "https://instagram.com/rolzah_"


class LicenseDialog(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.result_valid = False
        self.result_tier  = ""
        self._checking    = False
        self._pulse_up    = True
        self._pulse_size  = 52
        self._dots        = 0
        self._shake_count = 0
        self._orig_x      = 0
        self._orig_y      = 0

        # Window setup
        W, H = 480, 520
        self.title("")
        self.geometry(f"{W}x{H}")
        self.resizable(False, False)
        self.configure(fg_color=BG)
        self.overrideredirect(False)

        # Center on screen
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x  = (sw - W) // 2
        y  = (sh - H) // 2
        self.geometry(f"{W}x{H}+{x}+{y}")
        self._orig_x = x
        self._orig_y = y

        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.attributes("-alpha", 0.0)

        self._build()
        self._fade_in()

        # Auto-fill cached key — delay so UI renders fully first
        cached = get_cached_key()
        if cached:
            self.key_entry.insert(0, cached)
            self.after(800, self._validate)

    # ── Build UI ─────────────────────────────────────────────────────────────

    def _build(self):
        # Main container with subtle border
        outer = ctk.CTkFrame(self, fg_color=CARD, corner_radius=20,
                             border_width=1, border_color=CARD3)
        outer.place(relx=0.5, rely=0.5, anchor="center",
                    relwidth=0.92, relheight=0.92)
        outer.grid_columnconfigure(0, weight=1)

        # ── Logo section ─────────────────────────────────────────────────
        logo_frame = ctk.CTkFrame(outer, fg_color="transparent")
        logo_frame.grid(row=0, column=0, pady=(36, 0))

        self.logo_lbl = ctk.CTkLabel(
            logo_frame, text="⚡",
            font=ctk.CTkFont(size=52)
        )
        self.logo_lbl.pack()

        ctk.CTkLabel(
            logo_frame, text="Lead Scraper Pro",
            font=ctk.CTkFont("Segoe UI", 22, "bold"),
            text_color=TEXT
        ).pack(pady=(6, 0))

        ctk.CTkLabel(
            logo_frame,
            text="by ExclusiefTech.nl  ·  @rolzah_",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=TEXT_DIM
        ).pack(pady=(3, 0))

        # Thin accent line
        line = ctk.CTkFrame(outer, fg_color=CARD3, height=1, corner_radius=0)
        line.grid(row=1, column=0, sticky="ew", padx=30, pady=(24, 0))

        # ── Key input section ────────────────────────────────────────────
        form = ctk.CTkFrame(outer, fg_color="transparent")
        form.grid(row=2, column=0, sticky="ew", padx=32, pady=(24, 0))
        form.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            form, text="License Key",
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            text_color=TEXT_DIM, anchor="w"
        ).grid(row=0, column=0, sticky="w", pady=(0, 6))

        # Key entry with inner glow border effect
        self.entry_frame = ctk.CTkFrame(
            form, fg_color=CARD2, corner_radius=12,
            border_width=2, border_color=CARD3
        )
        self.entry_frame.grid(row=1, column=0, sticky="ew")
        self.entry_frame.grid_columnconfigure(0, weight=1)

        self.key_entry = ctk.CTkEntry(
            self.entry_frame,
            placeholder_text="ROLZ-XXXX-XXXX-XXXX",
            height=48,
            font=ctk.CTkFont("Consolas", 15),
            fg_color="transparent",
            border_width=0,
            text_color=TEXT,
            placeholder_text_color=TEXT_DIM,
            justify="center",
        )
        self.key_entry.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        self.key_entry.bind("<Return>", lambda _: self._validate())
        self.key_entry.bind("<FocusIn>",  lambda _: self._entry_focus(True))
        self.key_entry.bind("<FocusOut>", lambda _: self._entry_focus(False))

        # ── Status message ───────────────────────────────────────────────
        self.status_outer = ctk.CTkFrame(
            form, fg_color="transparent", corner_radius=8
        )
        self.status_outer.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        self.status_outer.grid_columnconfigure(0, weight=1)

        self.status_lbl = ctk.CTkLabel(
            self.status_outer, text="",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=TEXT_DIM,
            wraplength=380, justify="center"
        )
        self.status_lbl.grid(row=0, column=0)

        # ── Activate button ──────────────────────────────────────────────
        self.btn = ctk.CTkButton(
            outer,
            text="Activate",
            height=50,
            font=ctk.CTkFont("Segoe UI", 14, "bold"),
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            corner_radius=12,
            command=self._validate,
        )
        self.btn.grid(row=3, column=0, sticky="ew", padx=32, pady=(20, 0))

        # ── Get key link ─────────────────────────────────────────────────
        ctk.CTkButton(
            outer,
            text="Don't have a key?  DM @rolzah_ on Instagram",
            height=34,
            font=ctk.CTkFont("Segoe UI", 11),
            fg_color="transparent",
            hover_color=CARD2,
            text_color=TEXT_DIM,
            corner_radius=8,
            command=lambda: webbrowser.open(INSTAGRAM_URL),
        ).grid(row=4, column=0, padx=32, pady=(10, 0))

        # ── Footer ───────────────────────────────────────────────────────
        ctk.CTkLabel(
            outer,
            text="Keys are verified online  ·  ExclusiefTech.nl",
            font=ctk.CTkFont("Segoe UI", 9),
            text_color=BORDER
        ).grid(row=5, column=0, pady=(16, 20))

        # Start logo pulse
        self._pulse_logo()

    # ── Animations ───────────────────────────────────────────────────────────

    def _fade_in(self, alpha=0.0):
        alpha = min(1.0, alpha + 0.06)
        try:
            self.attributes("-alpha", alpha)
        except Exception:
            return
        if alpha < 1.0:
            self.after(16, lambda: self._fade_in(alpha))

    def _fade_out(self, callback, alpha=1.0):
        alpha = max(0.0, alpha - 0.08)
        try:
            self.attributes("-alpha", alpha)
        except Exception:
            return
        if alpha > 0.0:
            self.after(16, lambda: self._fade_out(callback, alpha))
        else:
            callback()

    def _pulse_logo(self):
        if not self.winfo_exists():
            return
        if self._checking:
            # Spin feeling — alternate characters
            self._dots = (self._dots + 1) % 4
            self.logo_lbl.configure(text=["⚡", "✦", "⚡", "✦"][self._dots])
            self.after(250, self._pulse_logo)
            return
        # Size pulse 50 ↔ 56
        if self._pulse_up:
            self._pulse_size += 0.5
            if self._pulse_size >= 56:
                self._pulse_up = False
        else:
            self._pulse_size -= 0.5
            if self._pulse_size <= 50:
                self._pulse_up = True
        try:
            self.logo_lbl.configure(
                font=ctk.CTkFont(size=int(self._pulse_size)),
                text="⚡"
            )
        except Exception:
            return
        self.after(40, self._pulse_logo)

    def _shake(self, count=0):
        if count >= 8:
            self.geometry(f"+{self._orig_x}+{self._orig_y}")
            return
        offset = 8 if count % 2 == 0 else -8
        try:
            self.geometry(f"+{self._orig_x + offset}+{self._orig_y}")
        except Exception:
            return
        self.after(45, lambda: self._shake(count + 1))

    def _entry_focus(self, focused: bool):
        self.entry_frame.configure(
            border_color=ACCENT if focused else CARD3
        )

    def _animate_dots(self):
        if not self._checking:
            return
        dots = "." * (self._dots % 4)
        self._dots += 1
        try:
            self.btn.configure(text=f"Checking{dots}")
        except Exception:
            return
        self.after(350, self._animate_dots)

    def _set_status(self, text: str, color: str, bg: str = "transparent"):
        self.status_outer.configure(fg_color=bg)
        self.status_lbl.configure(text=text, text_color=color)

    # ── Validation ────────────────────────────────────────────────────────────

    def _validate(self):
        if self._checking:
            return
        key = self.key_entry.get().strip()
        if not key:
            self._set_status("Please enter your license key.", WARN)
            return

        self._checking = True
        self._dots     = 0
        self.btn.configure(state="disabled", text="Checking", fg_color=ACCENT_DIM)
        self._set_status("", TEXT_DIM)
        self._animate_dots()

        def _do():
            valid, result = validate_key(key)
            self.after(0, lambda: self._on_result(valid, result))

        threading.Thread(target=_do, daemon=True).start()

    def _on_result(self, valid: bool, result: str):
        self._checking = False
        # Always reset button first to prevent stuck state
        self.btn.configure(state="normal", text="Activate",
                           fg_color=ACCENT, hover_color=ACCENT_HOVER)

        if valid:
            self.result_valid = True
            self.result_tier  = result
            # Success state
            self.btn.configure(
                state="normal", text="✓  Activated!",
                fg_color=SUCCESS, hover_color=SUCCESS
            )
            self.entry_frame.configure(border_color=SUCCESS)
            self._set_status(f"Welcome! Tier: {result}", SUCCESS)
            self.after(900, lambda: self._fade_out(self.destroy))
        else:
            # Error state
            self.btn.configure(
                state="normal", text="Activate",
                fg_color=ACCENT, hover_color=ACCENT_HOVER
            )
            self.entry_frame.configure(border_color=DANGER)
            self._set_status(result, DANGER)
            self._shake()
            # Reset border after 2s
            self.after(2000, lambda: self.entry_frame.configure(border_color=CARD3))

    def _on_close(self):
        self.master.destroy()


# ── Entry point ───────────────────────────────────────────────────────────────

def check_license() -> tuple:
    """Show license dialog. Returns (is_valid, tier). Call before App()."""
    ctk.set_appearance_mode("dark")
    root = ctk.CTk()
    root.withdraw()
    root.title("")

    dlg = LicenseDialog(root)
    root.wait_window(dlg)

    valid = dlg.result_valid
    tier  = dlg.result_tier
    root.destroy()

    return valid, tier
