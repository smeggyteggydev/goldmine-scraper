"""
scraper2.py  —  Fast + Accurate Google Maps Business Scraper
=============================================================
Architecture:
  Phase 1  — One page scrolls the search results list and collects
              unique business URLs (deduped by Place ID).
  Phase 2  — Up to CONCURRENT_PAGES asyncio tasks each open a
              FRESH PAGE per business so no SPA state bleeds across
              navigations.  A semaphore caps concurrency.

Root-cause fixes vs v1:
  ✓ Fresh page per business → website/phone/address never bleed
  ✓ Place-ID deduplication  → zero duplicate rows
  ✓ tel: href for phone     → accurate phone numbers
  ✓ data-item-id selectors  → reliable field extraction
  ✓ Final dedup by Name+Address as safety net
"""

import asyncio
import inspect
import os
import re
import pandas as pd

PLAYWRIGHT_BROWSERS_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
    "ms-playwright",
)
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", PLAYWRIGHT_BROWSERS_DIR)

from playwright.async_api import async_playwright, TimeoutError as PWTimeout

# ── Tuning ──────────────────────────────────────────────────────────────────
CONCURRENT_PAGES = 2      # parallel detail pages (lowered to 2 for Render Free Tier RAM limits)
SCROLL_PAUSE     = 0.7    # seconds between result-panel scrolls
NAV_TIMEOUT      = 20000  # ms for page.goto (20 seconds)
ELEM_TIMEOUT     = 3000   # ms for individual element waits
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
# ────────────────────────────────────────────────────────────────────────────


# ── Helpers ─────────────────────────────────────────────────────────────────

def build_search_url(niche: str, location: str) -> str:
    return "https://www.google.com/maps/search/" + f"{niche} in {location}".replace(" ", "+")


def extract_place_id(url: str) -> str | None:
    """Pull the stable Place-ID (0x… hex or ChIJ…) from a Maps URL."""
    # ChIJ style (common outside USA)
    m = re.search(r'!1s(ChIJ[A-Za-z0-9_\-]+)', url)
    if m:
        return m.group(1)
    # 0x hex style
    m = re.search(r'(0x[0-9a-f]+:0x[0-9a-f]+)', url)
    if m:
        return m.group(1)
    # Fallback: use the place-name slug so we at least catch obvious dups
    m = re.search(r'/maps/place/([^/@]+)', url)
    return m.group(1) if m else url


async def _text(locator, timeout=ELEM_TIMEOUT) -> str:
    try:
        return _clean_text(await locator.first.inner_text(timeout=timeout))
    except Exception:
        return ""


async def _attr(locator, attr: str, timeout=ELEM_TIMEOUT) -> str:
    try:
        return (await locator.first.get_attribute(attr, timeout=timeout) or "").strip()
    except Exception:
        return ""


def _clean_text(value: str) -> str:
    value = re.sub(r"[\ue000-\uf8ff]", "", value or "")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


async def _goto_maps(page, url: str):
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT)
    except PWTimeout:
        await page.goto(url, wait_until="commit", timeout=15000)


def _emit_progress(progress_callback, current: int, total: int, name: str, **info):
    if not progress_callback:
        return
    try:
        sig = inspect.signature(progress_callback)
        params = sig.parameters.values()
        wants_info = any(p.kind == p.VAR_POSITIONAL for p in params) or len(sig.parameters) >= 4
    except Exception:
        wants_info = False

    if wants_info:
        progress_callback(current, total, name, info)
    else:
        progress_callback(current, total, name)


# ── Phase 1: collect unique URLs ────────────────────────────────────────────

async def collect_urls(page, target: int, progress_callback=None) -> list[str]:
    """Scroll the results panel; return up to *target* unique business URLs."""
    urls: list[str]   = []
    seen_ids: set[str] = set()
    max_scrolls = 100

    _emit_progress(
        progress_callback, 0, target, "Opening Google Maps results",
        stage="collect", raw=0, raw_total=target,
    )

    last_reported = -1
    no_change_count = 0
    prev_len = 0
    for _ in range(max_scrolls):
        cards = await page.locator('a[href*="/maps/place/"]').all()
        for card in cards:
            href = (await card.get_attribute("href") or "").strip()
            if not href:
                continue
            pid = extract_place_id(href)
            if pid and pid not in seen_ids:
                seen_ids.add(pid)
                urls.append(href)

        if len(urls) != last_reported:
            last_reported = len(urls)
            _emit_progress(
                progress_callback, min(len(urls), target), target,
                f"Collected {len(urls)} business URLs",
                stage="collect", raw=len(urls), raw_total=target,
            )

        if len(urls) >= target:
            break
        if await page.locator('span.HlvSq').count() > 0:
            break
            
        # Break if we've reached the end (no new URLs found after 5 scrolls)
        if len(urls) == prev_len:
            no_change_count += 1
        else:
            no_change_count = 0
        prev_len = len(urls)
        
        if no_change_count >= 5:
            break

        await page.evaluate(
            'const p = document.querySelector(\'div[role="feed"]\');'
            'if (p) p.scrollBy(0, 1200);'
        )
        await asyncio.sleep(SCROLL_PAUSE)

    return urls[:target]


# ── Phase 2: extract details from a FRESH page ──────────────────────────────

async def extract_detail(context, url: str) -> dict:
    """
    Open a brand-new page, navigate to the business URL, scrape, then close.
    A fresh page guarantees zero state bleed between businesses.
    """
    data = {
        "Name": "", "Category": "", "Address": "",
        "Phone": "", "Website": "", "Rating": "", "Reviews": "",
        "Source": "Google Maps",
    }

    page = await context.new_page()
    try:
        await _goto_maps(page, url)

        # Dismiss cookie/consent banner if it blocks the detail page
        for sel in ['button[aria-label*="Accept"]', 'form button[type="submit"]', 'button[aria-label*="Agree"]', 'button[aria-label*="consent"]']:
            try:
                btn = page.locator(sel).first
                if await btn.is_visible(timeout=1500):
                    await btn.click()
                    await asyncio.sleep(0.5)
                    break
            except Exception:
                pass

        # Wait for the business name heading
        try:
            await page.locator(
                'h1.DUwDvf, h1[class*="fontHeadlineLarge"]'
            ).first.wait_for(timeout=8000)
        except PWTimeout:
            # Capture screenshot to debug if Google Map blocks or CAPTCHAs the server
            try:
                os.makedirs("debug_screenshots", exist_ok=True)
                await page.screenshot(path=f"debug_screenshots/error_{int(time.time())}.png")
            except Exception:
                pass
            return data

        # ── Name ──────────────────────────────────────────────────────────
        data["Name"] = await _text(
            page.locator('h1.DUwDvf, h1[class*="fontHeadlineLarge"]')
        )

        # ── Category ──────────────────────────────────────────────────────
        for sel in [
            'button[jsaction*="category"]',
            'span[jsan*="t-category-text"]',
            'div.skqShb button',
        ]:
            v = await _text(page.locator(sel))
            if v:
                data["Category"] = v
                break

        # ── Rating ────────────────────────────────────────────────────────
        data["Rating"] = await _text(
            page.locator('div.F7nice span[aria-hidden="true"]')
        )

        # ── Reviews ───────────────────────────────────────────────────────
        try:
            aria = await _attr(
                page.locator('div.F7nice span[aria-label]'), "aria-label"
            )
            nums = re.findall(r'\d[\d,]*', aria)
            if nums:
                data["Reviews"] = nums[0].replace(",", "")
        except Exception:
            pass

        # ── Phone  (via tel: href — language-independent) ─────────────────
        try:
            tel_link = page.locator('a[href^="tel:"]').first
            await tel_link.wait_for(timeout=ELEM_TIMEOUT)
            raw = (await tel_link.get_attribute("href") or "").replace("tel:", "").strip()
            data["Phone"] = raw
        except Exception:
            pass

        # ── Website  (data-item-id="authority" is reliable) ───────────────
        try:
            wl = page.locator('a[data-item-id="authority"]').first
            await wl.wait_for(timeout=ELEM_TIMEOUT)
            data["Website"] = (await wl.get_attribute("href") or "").strip()
        except Exception:
            pass

        # ── Address  (button with data-item-id containing "address") ──────
        try:
            addr_btn = page.locator(
                'button[data-item-id*="address"], '
                'button[aria-label*="ddress"]'       # covers "Address", "Adres", etc.
            ).first
            await addr_btn.wait_for(timeout=ELEM_TIMEOUT)
            data["Address"] = _clean_text(await addr_btn.inner_text(timeout=ELEM_TIMEOUT))
        except Exception:
            # Fallback: look for copy-address tooltip
            try:
                addr_btn = page.locator('[data-tooltip*="ddress"]').first
                await addr_btn.wait_for(timeout=1500)
                data["Address"] = _clean_text(await addr_btn.inner_text(timeout=1500))
            except Exception:
                pass

    finally:
        await page.close()   # ← always close; no state survives

    return data


# ── Concurrency wrapper ──────────────────────────────────────────────────────

async def _process_url(context, url, sem, website_filter,
                       max_leads, results, lock, progress_callback, counters):
    async with sem:
        try:
            # Stop early if quota reached
            async with lock:
                if len(results) >= max_leads:
                    return

            biz = await extract_detail(context, url)
            
            # Skip if invalid/empty detail page payload
            if not biz or not biz.get("Name"):
                async with lock:
                    counters["checked"] += 1
                return

            has_website = bool(biz["Website"].strip()) if biz["Name"] else False
            matched_filter = bool(biz["Name"])
            if website_filter == "with" and not has_website:
                matched_filter = False
            elif website_filter == "without" and has_website:
                matched_filter = False

            async with lock:
                accepted = matched_filter and len(results) < max_leads
                if accepted:
                    results.append(biz)
                counters["checked"] += 1
                checked = counters["checked"]
                matched = len(results)

            if accepted:
                _emit_progress(
                    progress_callback, matched, max_leads, biz["Name"],
                    stage="lead", checked=checked, raw_total=counters["total"],
                    has_website=has_website,
                )

            _emit_progress(
                progress_callback, matched, max_leads,
                biz["Name"] or "Skipped business",
                stage="checking", checked=checked, raw_total=counters["total"],
                has_website=has_website, accepted=accepted,
            )
        except Exception as e:
            print(f"Error processing URL {url}: {e}")
            # Ensure the check counters increment even on failures to prevent hanging
            async with lock:
                counters["checked"] += 1


# ── Public API ───────────────────────────────────────────────────────────────

async def scrape_async(
    niche: str,
    location: str,
    max_leads: int,
    website_filter: str,          # "with" | "without" | "all"
    progress_callback=None,
) -> list[dict]:

    # Collect more raw URLs than needed to survive filter attrition.
    # "No website" leads are usually much rarer, so overfetch more aggressively.
    if website_filter == "without":
        fetch_count = max_leads * 12
    elif website_filter == "with":
        fetch_count = max_leads * 4
    else:
        fetch_count = max_leads + 10

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--js-flags=--max-old-space-size=256"
            ]
        )

        # ── Shared browser context (one jar of cookies, saves memory) ─────
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=USER_AGENT,
            locale="en-GB",
        )
        context.set_default_timeout(NAV_TIMEOUT)

        # ── Phase 1: collect URLs ─────────────────────────────────────────
        search_page = await context.new_page()
        await _goto_maps(search_page, build_search_url(niche, location))
        await asyncio.sleep(2.5)

        # Dismiss cookie / consent banner
        for sel in ['button[aria-label*="Accept"]', 'form button[type="submit"]', 'button[aria-label*="Agree"]', 'button[aria-label*="consent"]']:
            try:
                btn = search_page.locator(sel).first
                if await btn.is_visible(timeout=2000):
                    await btn.click()
                    await asyncio.sleep(0.8)
                    break
            except Exception:
                pass

        try:
            await search_page.locator(
                'a[href*="/maps/place/"]'
            ).first.wait_for(timeout=15000)
        except PWTimeout:
            await browser.close()
            return []

        urls = await collect_urls(search_page, fetch_count, progress_callback)
        await search_page.close()

        if not urls:
            await browser.close()
            return []

        # ── Phase 2: parallel detail fetch ────────────────────────────────
        results: list[dict] = []
        lock = asyncio.Lock()
        sem  = asyncio.Semaphore(CONCURRENT_PAGES)
        counters = {"checked": 0, "total": len(urls)}

        tasks = [
            _process_url(context, url, sem, website_filter,
                         max_leads, results, lock, progress_callback, counters)
            for url in urls
        ]
        try:
            # Wrap in wait_for to prevent infinite hanging at 100%
            await asyncio.wait_for(asyncio.gather(*tasks), timeout=300) 
        except asyncio.TimeoutError:
            pass # Return whatever we got so far

        try:
            await browser.close()
        except:
            pass

    # ── Final deduplication safety net ────────────────────────────────────
    seen_keys: set[str] = set()
    unique: list[dict]  = []
    for biz in results:
        key = (biz["Name"].lower().strip(), biz["Address"].lower().strip())
        if key not in seen_keys:
            seen_keys.add(key)
            unique.append(biz)

    return unique[:max_leads]


def save_to_csv(data: list[dict], filepath: str) -> str:
    cols = ["Name", "Category", "Address", "Phone",
            "Website", "Rating", "Reviews", "Source"]
    pd.DataFrame(data, columns=cols).to_csv(
        filepath, index=False, encoding="utf-8-sig"
    )
    return filepath


def scrape(niche, location, max_leads, website_filter,
           progress_callback=None) -> list[dict]:
    """Sync entry point — wraps the async engine."""
    return asyncio.run(
        scrape_async(niche, location, max_leads, website_filter, progress_callback)
    )
