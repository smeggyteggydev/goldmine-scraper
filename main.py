"""
main.py - Interactive CLI entry point for the Business Lead Scraper
"""

import os
import sys
import time
from datetime import datetime

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt, IntPrompt
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
    from rich import print as rprint
    from rich.rule import Rule
    from rich.style import Style
except ImportError:
    print("Missing dependencies. Please run setup.bat or: pip install -r requirements.txt")
    sys.exit(1)

try:
    from scraper import scrape_google_maps, save_to_csv
except ImportError as e:
    print(f"Could not import scraper: {e}")
    sys.exit(1)


console = Console()

BANNER = """
[bold cyan]╔══════════════════════════════════════════════╗
║   🕷️  Business Lead Scraper — Google Maps    ║
║           Free · Fast · No API Key           ║
╚══════════════════════════════════════════════╝[/bold cyan]
"""

FILTER_CHOICES = {
    "1": ("with",    "✅  With Website    — businesses that have a website"),
    "2": ("without", "🚫  Without Website — businesses with NO website (best for cold outreach)"),
    "3": ("all",     "📋  All             — include every result"),
}


def prompt_inputs() -> dict:
    """Collect user inputs interactively."""
    console.print(BANNER)
    console.print(Rule("[bold yellow]Configure Your Scrape[/bold yellow]"))
    console.print()

    location = Prompt.ask("[bold green]📍 Enter location[/bold green]  [dim](e.g. London, New York, Dubai)[/dim]").strip()
    niche    = Prompt.ask("[bold green]🔍 Enter niche[/bold green]     [dim](e.g. plumbers, restaurants, dentists)[/dim]").strip()

    console.print()
    console.print("[bold]🌐 Website Filter:[/bold]")
    for key, (_, desc) in FILTER_CHOICES.items():
        console.print(f"  [bold cyan][{key}][/bold cyan]  {desc}")
    console.print()

    while True:
        choice = Prompt.ask("   [bold]Choose filter[/bold]", choices=["1", "2", "3"], default="2")
        website_filter, desc = FILTER_CHOICES[choice][0], FILTER_CHOICES[choice][1]
        break

    console.print()
    max_leads = IntPrompt.ask("[bold green]📊 How many leads do you want?[/bold green]  [dim](e.g. 50)[/dim]", default=50)
    max_leads = max(1, min(max_leads, 500))  # clamp between 1 and 500

    headless_choice = Prompt.ask(
        "\n[bold]🖥️  Run browser invisibly (headless)?[/bold]  [dim](say 'no' only if you get blocked)[/dim]",
        choices=["yes", "no"],
        default="yes",
    )
    headless = headless_choice == "yes"

    return {
        "location": location,
        "niche": niche,
        "website_filter": website_filter,
        "max_leads": max_leads,
        "headless": headless,
    }


def show_preview(cfg: dict) -> None:
    """Show a summary table of what will be scraped."""
    console.print()
    console.print(Rule("[bold yellow]Scrape Summary[/bold yellow]"))

    _, filter_desc = FILTER_CHOICES[
        next(k for k, v in FILTER_CHOICES.items() if v[0] == cfg["website_filter"])
    ]

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Field", style="bold cyan")
    table.add_column("Value", style="white")
    table.add_row("Query",       f"{cfg['niche']} in {cfg['location']}")
    table.add_row("Filter",      filter_desc)
    table.add_row("Target Leads",str(cfg["max_leads"]))
    table.add_row("Browser",     "Invisible (headless)" if cfg["headless"] else "Visible window")
    console.print(table)
    console.print()


def run_scrape(cfg: dict) -> list:
    """Run the scrape with a live progress display."""
    results = []
    found_so_far = [0]

    console.print(Rule("[bold green]Scraping...[/bold green]"))
    console.print()

    # Start progress bar
    with Progress(
        SpinnerColumn(style="cyan"),
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(bar_width=30, style="green", complete_style="bright_green"),
        TextColumn("[bold white]{task.completed}/{task.total} leads"),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    ) as progress:
        task = progress.add_task(f"[cyan]Scraping {cfg['niche']} in {cfg['location']}...", total=cfg["max_leads"])

        def on_progress(current, total, name):
            found_so_far[0] = current
            progress.update(task, completed=current, description=f"[cyan]Found: [bold]{name[:40]}[/bold]")

        results = scrape_google_maps(
            niche=cfg["niche"],
            location=cfg["location"],
            max_leads=cfg["max_leads"],
            website_filter=cfg["website_filter"],
            headless=cfg["headless"],
            progress_callback=on_progress,
        )

        progress.update(task, completed=len(results))

    return results


def display_results_preview(results: list) -> None:
    """Show a rich table preview of first 10 rows."""
    if not results:
        console.print("[red]No results to display.[/red]")
        return

    console.print()
    console.print(Rule("[bold yellow]Preview (first 10 results)[/bold yellow]"))

    table = Table(show_header=True, header_style="bold cyan", row_styles=["dim", ""], expand=True)
    table.add_column("#",        width=3,  no_wrap=True)
    table.add_column("Name",     max_width=28, no_wrap=True)
    table.add_column("Category", max_width=16, no_wrap=True)
    table.add_column("Phone",    max_width=16, no_wrap=True)
    table.add_column("Website",  max_width=20, no_wrap=True)
    table.add_column("Rating",   width=7,  no_wrap=True)

    for i, biz in enumerate(results[:10], 1):
        website_display = biz.get("Website", "")
        if website_display:
            website_display = website_display[:18] + "…" if len(website_display) > 18 else website_display
            website_display = f"[green]{website_display}[/green]"
        else:
            website_display = "[red]None[/red]"

        table.add_row(
            str(i),
            biz.get("Name", "")[:28],
            biz.get("Category", "")[:16],
            biz.get("Phone", "")[:16],
            website_display,
            biz.get("Rating", "") or "—",
        )

    console.print(table)


def main():
    try:
        cfg = prompt_inputs()
        show_preview(cfg)

        confirm = Prompt.ask("[bold yellow]▶  Start scraping now?[/bold yellow]", choices=["yes", "no"], default="yes")
        if confirm != "yes":
            console.print("[yellow]Aborted.[/yellow]")
            return

        results = run_scrape(cfg)

        if not results:
            console.print()
            console.print(Panel(
                "[red bold]No matching businesses found.[/red bold]\n\n"
                "Tips:\n"
                "• Try a broader niche (e.g. [cyan]plumbers[/cyan] instead of [cyan]emergency plumbers[/cyan])\n"
                "• Try a larger city\n"
                "• If you see a CAPTCHA, rerun and choose [bold]no[/bold] for headless mode",
                title="[red]⚠  No Results[/red]",
                border_style="red",
            ))
            return

        # Save CSV
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_niche    = cfg["niche"].replace(" ", "_").lower()
        safe_location = cfg["location"].replace(" ", "_").lower()
        filename = f"leads_{safe_niche}_{safe_location}_{timestamp}.csv"
        output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
        save_to_csv(results, output_path)

        display_results_preview(results)

        console.print()
        console.print(Panel(
            f"[bold green]✅  {len(results)} leads saved![/bold green]\n\n"
            f"📂 File: [bold cyan]{output_path}[/bold cyan]\n"
            f"🔍 Niche: [white]{cfg['niche']} in {cfg['location']}[/white]\n"
            f"🌐 Website filter: [white]{cfg['website_filter']}[/white]",
            title="[green]🎉 Done![/green]",
            border_style="green",
        ))

    except KeyboardInterrupt:
        console.print("\n[yellow]Scraping cancelled by user.[/yellow]")
        sys.exit(0)


if __name__ == "__main__":
    main()
