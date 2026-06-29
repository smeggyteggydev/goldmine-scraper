"""
keygen.py  —  License Key Generator for Lead Scraper by Rolzah
===============================================================
Run this yourself to create monthly subscription keys.
Then paste the output into your JSONBin dashboard.

Usage:
    python keygen.py              → generate 1 key (30 days)
    python keygen.py 5            → generate 5 keys
    python keygen.py 1 60         → generate 1 key valid for 60 days
"""

import random
import string
import sys
import json
from datetime import datetime, timedelta, timezone


# Remove ambiguous characters: O, 0, I, 1, L
CHARSET = "".join(
    c for c in (string.ascii_uppercase + string.digits)
    if c not in "O0I1L"
)


def generate_key() -> str:
    def block(n=4):
        return "".join(random.choices(CHARSET, k=n))
    return f"ROLZ-{block()}-{block()}-{block()}"


def make_entry(key: str, tier: str = "Pro", days: int = 30, user: str = "unnamed") -> dict:
    """Returns the JSON entry to paste into JSONBin valid_keys."""
    now     = datetime.now(timezone.utc)
    expires = (now + timedelta(days=days)).strftime("%Y-%m-%d")
    created = now.strftime("%Y-%m-%d")
    return {
        key: {
            "tier":    tier,
            "user":    user,
            "created": created,
            "expires": expires,
            "active":  True,
        }
    }


if __name__ == "__main__":
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    days  = int(sys.argv[2]) if len(sys.argv) > 2 else 30

    print(f"\n{'='*58}")
    print(f"  Lead Scraper Pro  --  Key Generator by Rolzah")
    print(f"  Subscription: {days}-day keys")
    print(f"{'='*58}\n")

    all_entries = {}

    for i in range(count):
        k = generate_key()
        entry = make_entry(k, days=days)
        all_entries.update(entry)

        print(f"  Key #{i+1}:  {k}")
        expires = list(entry.values())[0]["expires"]
        print(f"  Expires: {expires}\n")

    print(f"{'-'*58}")
    print("Paste this into JSONBin -> your bin -> valid_keys:\n")
    print(json.dumps(all_entries, indent=4))
    print(f"\n{'-'*58}")
    print("Steps:")
    print("  1. Go to jsonbin.io -> open your bin -> click Edit")
    print("  2. Find the \"valid_keys\": { } section")
    print("  3. Add the JSON above inside it")
    print("  4. Click 'Update Bin'")
    print("  5. Send the key string (ROLZ-...) to your customer")
    print(f"{'='*58}\n")
