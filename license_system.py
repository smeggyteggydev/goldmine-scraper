"""
license_system.py  —  License validation via GitHub Gist
=========================================================
SETUP (2 minutes, completely free):
  1. Go to https://gist.github.com  (login with GitHub — everyone has one)
  2. Click the '+' button (New Gist)
  3. Filename: keys.json
  4. Paste this content:
       {
         "keys": {}
       }
  5. Click "Create secret gist"
  6. Click the "Raw" button on your gist page
  7. Copy that URL and paste it as GIST_RAW_URL below

  To ADD a user key:   edit the gist, add to "keys": {"ROLZ-XXXX-XXXX-XXXX": "Pro"}
  To REVOKE a key:     edit the gist, delete that line. Done instantly.
  To EXPIRE a key:     change value to "expired"
"""

import os
import hashlib
import platform
import threading
from datetime import date

try:
    import requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

# ── YOUR CONFIG — paste your GitHub Gist Raw URL here ────────────────────────
GIST_RAW_URL = "https://gist.githubusercontent.com/smeggyteggydev/4628147698c938e6f668ffae30faa6ff/raw/1c8ba8794cad88988d72ef4638fa84e9df407524/keys.json"
# Example (replace with yours after setup):
# GIST_RAW_URL = "https://gist.githubusercontent.com/rolzah/abc123def456/raw/keys.json"
# ─────────────────────────────────────────────────────────────────────────────

APP_VERSION = "1.0.0"
APP_NAME    = "LeadScraper"
CACHE_DIR   = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), APP_NAME)
CACHE_FILE  = os.path.join(CACHE_DIR, "lc.dat")
XOR_KEY     = 0x5A


def _xor(text: str) -> str:
    return "".join(chr(ord(c) ^ XOR_KEY) for c in text)

def _save_cache(key: str):
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        open(CACHE_FILE, "w").write(_xor(key))
    except Exception:
        pass

def _load_cache() -> str:
    try:
        return _xor(open(CACHE_FILE).read().strip())
    except Exception:
        return ""

def _clear_cache():
    try:
        if os.path.exists(CACHE_FILE):
            os.remove(CACHE_FILE)
    except Exception:
        pass


def validate_key(key: str) -> tuple:
    """Returns (True, tier) or (False, error_message)."""
    key = key.strip().upper()

    if not key:
        return False, "Please enter your license key."

    if not REQUESTS_OK:
        return False, "Missing package — run: pip install requests"

    # ── Dev mode (no URL set yet) — accepts any key ────────────────────
    if "YOUR_GIST" in GIST_RAW_URL or not GIST_RAW_URL.startswith("http"):
        _save_cache(key)
        return True, "Dev"

    # ── Online check via GitHub Gist ────────────────────────────────────
    try:
        resp = requests.get(GIST_RAW_URL, timeout=10)

        if resp.status_code != 200:
            if _load_cache() == key:
                return True, "Pro (offline)"
            return False, f"Server error {resp.status_code}. Contact @rolzah_"

        data       = resp.json()
        valid_keys = data.get("keys", {})

        if key not in valid_keys:
            return False, "Invalid key — DM @rolzah_ on Instagram to get one."

        tier_or_exp = valid_keys[key]

        # Check if manually revoked
        if tier_or_exp in ("expired", "revoked", "inactive", False):
            return False, "License revoked. Contact @rolzah_ to renew."

        # Check expiry if dict format {"tier": "Pro", "expires": "2026-05-30"}
        tier = "Pro"
        if isinstance(tier_or_exp, dict):
            tier    = tier_or_exp.get("tier", "Pro")
            expires = tier_or_exp.get("expires", "")
            active  = tier_or_exp.get("active", True)
            if not active:
                return False, "License deactivated. Contact @rolzah_ to renew."
            if expires:
                try:
                    if date.today() > date.fromisoformat(expires):
                        return False, f"Expired on {expires}. DM @rolzah_ to renew subscription."
                except ValueError:
                    pass
        elif isinstance(tier_or_exp, str):
            tier = tier_or_exp

        _save_cache(key)
        return True, tier

    except requests.exceptions.Timeout:
        if _load_cache() == key:
            return True, "Pro (offline)"
        return False, "Connection timed out. Check internet and try again."

    except requests.exceptions.ConnectionError:
        if _load_cache() == key:
            return True, "Pro (offline)"
        return False, "No internet. Connect and try again."

    except Exception as e:
        if _load_cache() == key:
            return True, "Pro (offline)"
        return False, f"Error: {str(e)[:80]}"


def get_cached_key() -> str:
    return _load_cache()

def deactivate():
    _clear_cache()
