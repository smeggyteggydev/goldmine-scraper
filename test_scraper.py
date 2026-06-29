import asyncio
from scraper2 import scrape

def progress(c, m, n):
    print(f"Progress: {c}/{m} - {n}")

try:
    print("Testing scraper...")
    results = scrape("Plumbers", "London", 2, "all", progress)
    print(f"Success! Found {len(results)} leads.")
except Exception as e:
    print(f"Error: {e}")
