"""
goldmine.py — Definitive Google Maps Lead Scraper v4
=====================================================
Two modes:
  [1] Quick Scrape  — scrape one query, export whatever is found
  [2] Target Hunt   — keep trying query variations until target count is met,
                      no matter how long it takes

Usage:
    python goldmine.py
"""

import asyncio
import csv
import os
import re
import sys
import threading
from datetime import datetime

try:
    from rich.console import Console
    from rich.prompt import Prompt, IntPrompt
    from rich.panel import Panel
    from rich.rule import Rule
    from rich.live import Live
    from rich.text import Text
    from rich.table import Table
except ImportError:
    print("Missing dependency. Run:  python -m pip install rich")
    sys.exit(1)

try:
    from playwright.async_api import async_playwright, TimeoutError as PWTimeout
except ImportError:
    print("Missing dependency. Run:  python -m pip install playwright")
    sys.exit(1)

console = Console()

# ═══════════════════════════════ CONFIG ══════════════════════════════════════

CONCURRENT   = 6
SCROLL_PAUSE = 0.6
NAV_TIMEOUT  = 0       # 0 = no timeout — slow pages are retried, never crash
ELEM_TIMEOUT = 3000
USER_AGENT   = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# ═══════════════════════════ QUERY VARIATIONS ════════════════════════════════

def generate_queries(niche: str, location: str) -> list[str]:
    """
    Auto-generate search query variations so Target Hunt can
    pull from multiple Maps result pages to meet the target.
    """
    n = niche.strip()
    l = location.strip()

    # Strip trailing 's' to get root word (roofers → roofer)
    root = n.rstrip("s") if n.lower().endswith("s") else n

    variations = []
    seen = set()

    candidates = [
        f"{n} in {l}",
        f"{root}ing in {l}",
        f"{root}ing company in {l}",
        f"{root}ing contractor in {l}",
        f"{root}ing service in {l}",
        f"{root}ing specialist in {l}",
        f"{n} company in {l}",
        f"{n} contractor in {l}",
        f"{n} service in {l}",
        f"{n} near {l}",
        f"best {n} in {l}",
        f"top {n} {l}",
        f"{n} {l}",
        f"{root} repair {l}",
        f"{root} maintenance {l}",
        f"{root} installation {l}",
    ]

    for c in candidates:
        key = c.lower().strip()
        if key not in seen:
            seen.add(key)
            variations.append(c)

    return variations


# ═════════════════════════════ UTILITIES ═════════════════════════════════════

def build_url(query: str) -> str:
    return "https://www.google.com/maps/search/" + query.replace(" ", "+")


def place_id(url: str) -> str:
    m = re.search(r'!1s(ChIJ[A-Za-z0-9_\-]+)', url)
    if m:
        return m.group(1)
    m = re.search(r'(0x[0-9a-f]+:0x[0-9a-f]+)', url)
    if m:
        return m.group(1)
    m = re.search(r'/maps/place/([^/@?]+)', url)
    return m.group(1) if m else url


async def _text(loc, timeout=ELEM_TIMEOUT) -> str:
    try:
        return (await loc.first.inner_text(timeout=timeout)).strip()
    except Exception:
        return ""


async def _attr(loc, attr: str, timeout=ELEM_TIMEOUT) -> str:
    try:
        return (await loc.first.get_attribute(attr, timeout=timeout) or "").strip()
    except Exception:
        return ""


# ═══════════════════════════ PHASE 1: URL COLLECTION ═════════════════════════

async def collect_urls_from_page(page, cap: int, status_fn,
                                 global_seen: set) -> list[str]:
    """
    Scroll until Maps runs out of results OR we have `cap` NEW unique URLs.
    Uses `global_seen` to avoid duplicates across multiple query runs.
    """
    urls: list[str] = []
    stale = 0

    for i in range(250):
        cards = await page.locator('a[href*="/maps/place/"]').all()
        new_this_round = 0
        for card in cards:
            href = (await card.get_attribute("href") or "").strip()
            if not href:
                continue
            pid = place_id(href)
            if pid not in global_seen:
                global_seen.add(pid)
                urls.append(href)
                new_this_round += 1

        status_fn(
            f"Phase 1 — {len(urls)} new URLs this query  "
            f"(total checked so far: {len(global_seen)})"
        )

        if len(urls) >= cap:
            break

        # End-of-list detection
        end_count = await page.locator(
            'span.HlvSq, div[class*="PbZDve"]'
        ).count()
        if end_count > 0 and new_this_round == 0:
            break

        if new_this_round == 0:
            stale += 1
            if stale >= 10:
                break
        else:
            stale = 0

        await page.evaluate(
            '(function(){'
            '  var p = document.querySelector(\'div[role="feed"]\');'
            '  if(p) p.scrollBy(0, 1400);'
            '})()'
        )
        await asyncio.sleep(SCROLL_PAUSE)

    return urls


# ═══════════════════════════ PHASE 2: DETAIL SCRAPE ══════════════════════════

async def scrape_detail(context, url: str) -> dict:
    """Fresh page per business — zero SPA state bleed."""
    data = {
        "Name": "", "Category": "", "Address": "",
        "Phone": "", "Website": "", "Rating": "", "Reviews": "",
        "Source": "Google Maps",
    }

    page = await context.new_page()
    try:
        # No timeout (0) — retry once if the network stalls
        for attempt in range(2):
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=0)
                break
            except Exception:
                if attempt == 1:
                    return data
                await asyncio.sleep(2)
        try:
            await page.locator(
                'h1.DUwDvf, h1[class*="fontHeadlineLarge"]'
            ).first.wait_for(timeout=10000)
        except PWTimeout:
            return data

        data["Name"] = await _text(
            page.locator('h1.DUwDvf, h1[class*="fontHeadlineLarge"]')
        )

        for sel in ['button[jsaction*="category"]',
                    'span[jsan*="t-category-text"]',
                    'div.skqShb button']:
            v = await _text(page.locator(sel))
            if v:
                data["Category"] = v
                break

        data["Rating"] = await _text(
            page.locator('div.F7nice span[aria-hidden="true"]')
        )

        for sel in ['div.F7nice span[aria-label*="review"]',
                    'div.F7nice span[aria-label*="Rezension"]',
                    'div.F7nice span[aria-label]']:
            aria = await _attr(page.locator(sel), "aria-label")
            nums = re.findall(r'[\d,]+', aria)
            if nums:
                data["Reviews"] = nums[0].replace(",", "")
                break

        # Phone via tel: href (language-independent)
        try:
            tel = page.locator('a[href^="tel:"]').first
            await tel.wait_for(timeout=ELEM_TIMEOUT)
            data["Phone"] = (
                await tel.get_attribute("href") or ""
            ).replace("tel:", "").strip()
        except Exception:
            pass

        # Website
        try:
            wl = page.locator('a[data-item-id="authority"]').first
            await wl.wait_for(timeout=ELEM_TIMEOUT)
            data["Website"] = (await wl.get_attribute("href") or "").strip()
        except Exception:
            pass

        # Address
        try:
            ab = page.locator(
                'button[data-item-id*="address"], button[aria-label*="dress"]'
            ).first
            await ab.wait_for(timeout=ELEM_TIMEOUT)
            data["Address"] = (await ab.inner_text(timeout=ELEM_TIMEOUT)).strip()
        except Exception:
            try:
                ab = page.locator('[data-tooltip*="ddress"]').first
                await ab.wait_for(timeout=1500)
                data["Address"] = (await ab.inner_text(timeout=1500)).strip()
            except Exception:
                pass

    finally:
        await page.close()

    return data


# ═══════════════════════════ WORKER ══════════════════════════════════════════

async def process_batch(context, urls: list[str], wfilter: str,
                        max_leads: int, results: list, counters: dict,
                        results_dedup: set, lock: asyncio.Lock,
                        sem: asyncio.Semaphore, prog_fn):
    """Process a list of URLs concurrently, stopping when max_leads reached."""

    async def _worker(url):
        async with sem:
            async with lock:
                if len(results) >= max_leads:
                    return

            biz = await scrape_detail(context, url)

            async with lock:
                counters["fetched"] += 1

            if not biz["Name"]:
                return

            has_site = bool(biz["Website"].strip())

            async with lock:
                if has_site:
                    counters["had_site"] += 1
                else:
                    counters["no_site"] += 1

            if wfilter == "with"    and not has_site:
                return
            if wfilter == "without" and has_site:
                return

            # Dedup by name+address across all queries
            key = (biz["Name"].lower().strip(), biz["Address"].lower().strip())
            async with lock:
                if key in results_dedup or len(results) >= max_leads:
                    return
                results_dedup.add(key)
                results.append(biz)
                prog_fn(len(results), max_leads, biz["Name"])

    tasks = [_worker(url) for url in urls]
    await asyncio.gather(*tasks)


# ═══════════════════════════════ ENGINES ═════════════════════════════════════

async def quick_scrape_async(niche, location, max_leads, wfilter,
                             status_fn, prog_fn):
    """Single query, scroll to end, filter, done."""
    queries  = [f"{niche} in {location}"]
    overfetch = 15 if wfilter == "without" else (5 if wfilter == "with" else 2)
    url_cap  = min(max_leads * overfetch, 800)

    return await _multi_query_engine(
        queries, url_cap, max_leads, wfilter,
        status_fn, prog_fn, stop_when_full=False
    )


async def target_hunt_async(niche, location, max_leads, wfilter,
                            status_fn, prog_fn):
    """
    Tries every query variation in sequence.
    Stops as soon as max_leads matching results are collected.
    """
    queries  = generate_queries(niche, location)
    url_cap_per_query = 300   # collect up to 300 URLs per variation

    status_fn(
        f"Target Hunt — will try up to {len(queries)} query variations"
    )
    return await _multi_query_engine(
        queries, url_cap_per_query, max_leads, wfilter,
        status_fn, prog_fn, stop_when_full=True
    )


async def _multi_query_engine(queries, url_cap_per_query, max_leads, wfilter,
                               status_fn, prog_fn, stop_when_full: bool):
    results:       list[dict] = []
    counters = {"fetched": 0, "had_site": 0, "no_site": 0}
    results_dedup: set[str]   = set()
    global_url_seen: set[str] = set()   # dedups URLs across all queries

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=USER_AGENT,
            locale="en-US",
        )
        context.set_default_timeout(NAV_TIMEOUT)

        lock = asyncio.Lock()
        sem  = asyncio.Semaphore(CONCURRENT)

        for q_idx, query in enumerate(queries, 1):
            async with lock:
                done_already = len(results) >= max_leads

            if done_already and stop_when_full:
                break

            status_fn(
                f"[{q_idx}/{len(queries)}] Searching: \"{query}\"  "
                f"({len(results)}/{max_leads} leads so far)"
            )

            sp = await context.new_page()
            try:
                await sp.goto(build_url(query), wait_until="domcontentloaded")
                await asyncio.sleep(2.5)

                # Dismiss consent banners
                for sel in [
                    'button[aria-label*="Accept"]',
                    'button[aria-label*="Agree"]',
                    'form[action*="consent"] button',
                ]:
                    try:
                        btn = sp.locator(sel).first
                        if await btn.is_visible(timeout=2000):
                            await btn.click()
                            await asyncio.sleep(0.8)
                            break
                    except Exception:
                        pass

                try:
                    await sp.locator(
                        'a[href*="/maps/place/"]'
                    ).first.wait_for(timeout=12000)
                except PWTimeout:
                    await sp.close()
                    continue

                # Collect URLs for this query (skips already-seen place IDs)
                new_urls = await collect_urls_from_page(
                    sp, url_cap_per_query, status_fn, global_url_seen
                )

            finally:
                await sp.close()

            if not new_urls:
                continue

            status_fn(
                f"Phase 2 — processing {len(new_urls)} new URLs "
                f"({CONCURRENT} concurrent)…"
            )

            await process_batch(
                context, new_urls, wfilter, max_leads,
                results, counters, results_dedup,
                lock, sem, prog_fn
            )

            if stop_when_full:
                async with lock:
                    if len(results) >= max_leads:
                        break

        await browser.close()

    return results, counters


# ═══════════════════════════════ CSV EXPORT ══════════════════════════════════

def export_csv(data: list[dict], niche: str, location: str) -> str:
    cols = ["Name", "Category", "Address", "Phone",
            "Website", "Rating", "Reviews", "Source"]
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = (
        f"leads_{niche.replace(' ','_')}_"
        f"{location.replace(' ','_')}_{ts}.csv"
    )
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), fname)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(data)
    return path


# ═══════════════════════════════ CLI ═════════════════════════════════════════

FILTER_MAP = {
    "1": ("with",    "✅  With Website"),
    "2": ("without", "🚫  Without Website  (best for cold outreach)"),
    "3": ("all",     "📋  All results"),
}

BANNER = """\
[bold cyan]
╔═══════════════════════════════════════════════╗
║      💎  GoldMine — Lead Scraper v4           ║
║   Google Maps · Multi-Query · Headless · Free ║
╚═══════════════════════════════════════════════╝[/bold cyan]"""


def run_with_live(engine_coro, max_leads: int) -> tuple[list, dict]:
    """Run async engine in a thread, show live progress bar."""
    state = {"status": "Starting…", "count": 0, "last": ""}
    done  = threading.Event()

    def set_status(msg: str):
        state["status"] = msg

    def on_progress(current, _total, name):
        state["count"] = current
        state["last"]  = name[:55]

    def run():
        r, c = asyncio.run(engine_coro)
        state["results"]  = r
        state["counters"] = c
        done.set()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()

    console.print()
    console.print(Rule("[bold green]Scraping ⚡[/bold green]"))
    console.print()

    with Live(console=console, refresh_per_second=4) as live:
        while not done.is_set():
            cnt = state["count"]
            pct = int((cnt / max(max_leads, 1)) * 30)
            bar = "[green]" + "█" * pct + "[/green]" + "░" * (30 - pct)
            txt = (
                f"  {bar}  [bold cyan]{cnt}[/bold cyan]/{max_leads} leads found\n"
                f"  [dim]{state['status']}[/dim]"
                + (f"\n  → [white]{state['last']}[/white]" if state["last"] else "")
            )
            live.update(Text.from_markup(txt))
            done.wait(timeout=0.25)
        live.update(Text.from_markup(
            f"  [bold green]✅  Collection complete — {state.get('count',0)} leads.[/bold green]"
        ))

    thread.join()
    return state.get("results", []), state.get("counters", {})


def print_stats(results, counters, wfilter, max_leads):
    console.print()
    console.print(Rule("[bold yellow]Results[/bold yellow]"))
    fetched  = counters.get("fetched", 0)
    had_site = counters.get("had_site", 0)
    no_site  = counters.get("no_site", 0)
    console.print(
        f"  [dim]Businesses checked :[/dim]  [white]{fetched}[/white]\n"
        f"  [dim]Have a website     :[/dim]  [green]{had_site}[/green]\n"
        f"  [dim]No website         :[/dim]  [yellow]{no_site}[/yellow]\n"
        f"  [dim]Matched filter     :[/dim]  [bold cyan]{len(results)}[/bold cyan]"
    )
    if wfilter == "without" and len(results) < max_leads:
        console.print(
            f"\n  [yellow]⚠  Only {no_site} businesses in this niche/region "
            f"have no website (checked {fetched} total).[/yellow]"
            f"\n  [dim]  The internet penetration for this niche/city is very high.[/dim]"
        )


def print_preview(results):
    if not results:
        return
    console.print()
    tbl = Table(header_style="bold cyan", row_styles=["dim", ""], expand=True)
    tbl.add_column("#",        width=3)
    tbl.add_column("Name",     max_width=26)
    tbl.add_column("Category", max_width=18)
    tbl.add_column("Phone",    max_width=18)
    tbl.add_column("Website",  max_width=24)
    tbl.add_column("⭐",        width=5)
    for i, b in enumerate(results[:12], 1):
        site = b.get("Website", "")
        sd = (
            (f"[green]{site[:22]}…[/green]" if len(site) > 22 else f"[green]{site}[/green]")
            if site else "[red]None[/red]"
        )
        tbl.add_row(
            str(i), b.get("Name","")[:26], b.get("Category","")[:18],
            b.get("Phone","")[:18], sd, b.get("Rating","") or "—"
        )
    if len(results) > 12:
        tbl.add_row("…", f"[dim]+{len(results)-12} more rows in CSV[/dim]","","","","")
    console.print(tbl)


def cli_main():
    console.print(BANNER)
    console.print(Rule("[bold yellow]Select Mode[/bold yellow]"))
    console.print()
    console.print("  [bold cyan][1][/bold cyan]  ⚡ Quick Scrape   — scrape one query, done fast")
    console.print("  [bold cyan][2][/bold cyan]  🎯 Target Hunt    — try multiple query variations until target count is met")
    console.print()

    mode = Prompt.ask("   Mode", choices=["1","2"], default="2")
    console.print()
    console.print(Rule("[bold yellow]Configure[/bold yellow]"))
    console.print()

    location = Prompt.ask(
        "[bold green]📍 Location[/bold green]  [dim](e.g. Dubai, London)[/dim]"
    ).strip()
    niche = Prompt.ask(
        "[bold green]🔍 Niche[/bold green]    [dim](e.g. roofers, dentists)[/dim]"
    ).strip()

    console.print()
    console.print("[bold]🌐 Website filter:[/bold]")
    for k, (_, lbl) in FILTER_MAP.items():
        console.print(f"  [bold cyan][{k}][/bold cyan]  {lbl}")
    console.print()
    choice  = Prompt.ask("   Choose", choices=["1","2","3"], default="2")
    wfilter = FILTER_MAP[choice][0]

    console.print()
    max_leads = IntPrompt.ask(
        "[bold green]📊 How many leads?[/bold green]  [dim](1–500)[/dim]", default=50
    )
    max_leads = max(1, min(max_leads, 500))

    # Summary
    console.print()
    console.print(Rule("[bold yellow]Ready[/bold yellow]"))
    t = Table(show_header=False, box=None, padding=(0,2))
    t.add_column("k", style="bold cyan"); t.add_column("v")
    t.add_row("Mode",     "⚡ Quick Scrape" if mode=="1" else "🎯 Target Hunt (multi-query)")
    t.add_row("Query",    f"{niche} in {location}")
    t.add_row("Filter",   FILTER_MAP[choice][1])
    t.add_row("Target",   str(max_leads))
    if mode == "2":
        q_count = len(generate_queries(niche, location))
        t.add_row("Variations", f"Up to {q_count} query variations will be tried")
    console.print(t)
    console.print()

    if Prompt.ask(
        "[bold yellow]▶  Start?[/bold yellow]", choices=["yes","no"], default="yes"
    ) != "yes":
        console.print("[yellow]Aborted.[/yellow]")
        return

    # Run engine
    if mode == "1":
        coro = quick_scrape_async(niche, location, max_leads, wfilter,
                                  lambda s: None, lambda *a: None)
    else:
        # We pass placeholders; actual callbacks wired inside run_with_live
        coro = None

    # Rewire with proper live callbacks
    state_ref: dict = {}

    def make_coro(status_fn, prog_fn):
        if mode == "1":
            return quick_scrape_async(niche, location, max_leads, wfilter,
                                      status_fn, prog_fn)
        else:
            return target_hunt_async(niche, location, max_leads, wfilter,
                                     status_fn, prog_fn)

    # Run with live display
    status_holder = {"v": "Starting…"}
    progress_holder = {"count": 0, "last": ""}
    done = threading.Event()

    def set_status(msg):
        status_holder["v"] = msg

    def on_prog(cur, tot, name):
        progress_holder["count"] = cur
        progress_holder["last"]  = name[:55]

    def run_thread():
        r, c = asyncio.run(make_coro(set_status, on_prog))
        state_ref["results"]  = r
        state_ref["counters"] = c
        done.set()

    thread = threading.Thread(target=run_thread, daemon=True)
    thread.start()

    console.print()
    console.print(Rule("[bold green]Scraping ⚡[/bold green]"))
    console.print()

    with Live(console=console, refresh_per_second=4) as live:
        while not done.is_set():
            cnt = progress_holder["count"]
            pct = int((cnt / max(max_leads, 1)) * 30)
            bar = "[green]" + "█" * pct + "[/green]" + "░" * (30 - pct)
            txt = (
                f"  {bar}  [bold cyan]{cnt}[/bold cyan]/{max_leads}\n"
                f"  [dim]{status_holder['v']}[/dim]"
                + (f"\n  → [white]{progress_holder['last']}[/white]"
                   if progress_holder["last"] else "")
            )
            live.update(Text.from_markup(txt))
            done.wait(timeout=0.25)
        live.update(Text.from_markup(
            f"  [bold green]✅  Done — "
            f"{progress_holder['count']} leads.[/bold green]"
        ))

    thread.join()
    results  = state_ref.get("results", [])
    counters = state_ref.get("counters", {})

    print_stats(results, counters, wfilter, max_leads)

    if not results:
        console.print(Panel(
            "[red bold]No matching leads found.[/red bold]\n\n"
            "• Switch filter to [bold][3] All[/bold]\n"
            "• Use a broader niche\n"
            "• Try Target Hunt mode if you used Quick Scrape",
            title="[red]⚠ No Results[/red]", border_style="red"
        ))
        return

    print_preview(results)

    path = export_csv(results, niche, location)
    console.print()
    console.print(Panel(
        f"[bold green]✅  {len(results)} leads saved![/bold green]\n\n"
        f"📂 [bold cyan]{path}[/bold cyan]",
        title="[green]🎉 Done![/green]", border_style="green"
    ))


if __name__ == "__main__":
    try:
        cli_main()
    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled.[/yellow]")
        sys.exit(0)
