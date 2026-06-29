"""
scraper.py - Google Maps Business Lead Scraper Core Engine
Uses Playwright browser automation (no paid API required).
"""

import time
import random
import pandas as pd
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


SCROLL_PAUSE = 1.5   # seconds between result-panel scrolls
ITEM_TIMEOUT = 8000  # ms to wait for each element


def build_search_url(niche: str, location: str) -> str:
    """Build a Google Maps search URL."""
    query = f"{niche} in {location}".replace(" ", "+")
    return f"https://www.google.com/maps/search/{query}"


def safe_inner_text(page, selector: str, timeout: int = 3000) -> str:
    """Return the inner text of a selector, or empty string if not found."""
    try:
        el = page.locator(selector).first
        el.wait_for(timeout=timeout)
        return el.inner_text().strip()
    except Exception:
        return ""


def scroll_results_panel(page, target_count: int, max_scrolls: int = 60) -> None:
    """Scroll the Google Maps results list panel until we have enough results."""
    scrolled = 0
    while scrolled < max_scrolls:
        # Count currently loaded result cards
        cards = page.locator('a[href*="/maps/place/"]').count()
        if cards >= target_count:
            break
        # Check for "end of list" indicator
        if page.locator('span[class*="HlvSq"]').count() > 0:
            break
        # Scroll the left results panel
        page.evaluate("""
            const panel = document.querySelector('div[role="feed"]');
            if (panel) panel.scrollBy(0, 1000);
        """)
        time.sleep(SCROLL_PAUSE)
        scrolled += 1


def extract_business_details(page) -> dict:
    """Extract all details from the currently open business panel."""
    data = {
        "Name": "",
        "Category": "",
        "Address": "",
        "Phone": "",
        "Website": "",
        "Rating": "",
        "Reviews": "",
    }

    # Name
    try:
        data["Name"] = page.locator('h1.DUwDvf, h1[class*="fontHeadlineLarge"]').first.inner_text(timeout=3000).strip()
    except Exception:
        pass

    # Category
    try:
        data["Category"] = page.locator('button[jsaction*="category"]').first.inner_text(timeout=2000).strip()
    except Exception:
        try:
            data["Category"] = page.locator('span[jsan*="t-category-text"]').first.inner_text(timeout=2000).strip()
        except Exception:
            pass

    # Rating
    try:
        data["Rating"] = page.locator('div.F7nice span[aria-hidden="true"]').first.inner_text(timeout=2000).strip()
    except Exception:
        pass

    # Reviews count
    try:
        reviews_text = page.locator('div.F7nice span[aria-label*="reviews"]').first.get_attribute("aria-label", timeout=2000) or ""
        data["Reviews"] = reviews_text.replace(" reviews", "").replace(",", "").strip()
    except Exception:
        pass

    # Address, Phone, Website — scraped from info rows
    try:
        info_rows = page.locator('div[class*="rogA2c"], div[data-item-id]').all()
        for row in info_rows:
            try:
                row_text = row.inner_text(timeout=1000).strip()
                aria = row.get_attribute("aria-label") or row.get_attribute("data-item-id") or ""
                
                if "address" in aria.lower() or "address" in row.get_attribute("data-tooltip", default="").lower():
                    data["Address"] = row_text
                elif "phone" in aria.lower() or row_text.startswith(("+", "0")) or any(c.isdigit() for c in row_text[:3]):
                    if not data["Phone"]:
                        data["Phone"] = row_text
                elif "website" in aria.lower():
                    data["Website"] = row_text
            except Exception:
                continue
    except Exception:
        pass

    # Fallback: website button
    if not data["Website"]:
        try:
            wb = page.locator('a[data-item-id="authority"], a[aria-label*="website" i]').first
            wb.wait_for(timeout=2000)
            data["Website"] = wb.get_attribute("href") or wb.inner_text(timeout=1000).strip()
        except Exception:
            pass

    # Fallback: address via aria-label
    if not data["Address"]:
        try:
            addr_btn = page.locator('button[data-item-id*="address"], button[aria-label*="Address"]').first
            addr_btn.wait_for(timeout=2000)
            data["Address"] = addr_btn.inner_text(timeout=1000).strip()
        except Exception:
            pass

    # Fallback: phone via aria-label
    if not data["Phone"]:
        try:
            ph_btn = page.locator('button[data-item-id*="phone"], button[aria-label*="Phone"]').first
            ph_btn.wait_for(timeout=2000)
            data["Phone"] = ph_btn.inner_text(timeout=1000).strip()
        except Exception:
            pass

    return data


def scrape_google_maps(
    niche: str,
    location: str,
    max_leads: int,
    website_filter: str,  # "with", "without", "all"
    headless: bool = True,
    progress_callback=None,
) -> list[dict]:
    """
    Main scraping function.

    Args:
        niche: Business type to search (e.g. "plumbers")
        location: City/region (e.g. "London")
        max_leads: Maximum number of matching leads to collect
        website_filter: "with", "without", or "all"
        headless: Run browser without GUI
        progress_callback: Optional callable(current, total, name) for progress updates

    Returns:
        List of business dicts
    """
    results = []
    url = build_search_url(niche, location)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="en-GB",
        )
        page = context.new_page()
        page.set_default_timeout(20000)

        # Navigate to Google Maps search
        page.goto(url, wait_until="domcontentloaded")
        time.sleep(3)

        # Dismiss cookies banner if present
        try:
            accept_btn = page.locator('button[aria-label*="Accept"], form:has(button) button').first
            if accept_btn.is_visible(timeout=3000):
                accept_btn.click()
                time.sleep(1)
        except Exception:
            pass

        # Wait for results to appear
        try:
            page.locator('a[href*="/maps/place/"]').first.wait_for(timeout=15000)
        except PlaywrightTimeoutError:
            browser.close()
            print("[!] No results found or Google blocked the request. Try running with headless=False.")
            return []

        # Scroll to load enough results
        # We load more than needed to account for filter attrition
        scroll_target = min(max_leads * 3, 200) if website_filter != "all" else max_leads
        scroll_results_panel(page, scroll_target)

        # Collect all visible result links
        cards = page.locator('a[href*="/maps/place/"]').all()
        total_cards = len(cards)

        processed = 0
        for i, card in enumerate(cards):
            if len(results) >= max_leads:
                break

            try:
                # Click on the result card
                card.scroll_into_view_if_needed()
                card.click()
                time.sleep(random.uniform(1.5, 2.5))

                # Wait for details panel to open
                page.locator('h1.DUwDvf, h1[class*="fontHeadlineLarge"]').first.wait_for(timeout=8000)

                biz = extract_business_details(page)
                biz["Source"] = "Google Maps"

                has_website = bool(biz["Website"].strip())

                # Apply filter
                if website_filter == "with" and not has_website:
                    processed += 1
                    continue
                elif website_filter == "without" and has_website:
                    processed += 1
                    continue

                results.append(biz)
                processed += 1

                if progress_callback:
                    progress_callback(len(results), max_leads, biz["Name"])

                # Small random delay to avoid rate limiting
                time.sleep(random.uniform(0.5, 1.2))

            except PlaywrightTimeoutError:
                processed += 1
                continue
            except Exception as e:
                processed += 1
                continue

        browser.close()

    return results


def save_to_csv(data: list[dict], filepath: str) -> str:
    """Save results to a CSV file and return the path."""
    df = pd.DataFrame(data, columns=["Name", "Category", "Address", "Phone", "Website", "Rating", "Reviews", "Source"])
    df.to_csv(filepath, index=False, encoding="utf-8-sig")
    return filepath
