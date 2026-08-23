"""
Fetch publications from Google Scholar and save as publications.json
Uses the `scholarly` Python library with proxy support for CI environments.
"""

import json
import os
import time
import sys
from datetime import datetime

try:
    from scholarly import scholarly, ProxyGenerator
except ImportError:
    print("Error: 'scholarly' package not installed. Run: pip install scholarly")
    sys.exit(1)

SCHOLAR_ID = "Pdd1FaEAAAAJ"  # Harsha Gwalani's Google Scholar ID
OUTPUT_FILE = "publications.json"
MAX_RETRIES = 3


def setup_proxy():
    """Set up a proxy to avoid Google Scholar blocking cloud IPs."""
    # Use ScraperAPI if key is available (most reliable)
    scraper_api_key = os.environ.get("SCRAPER_API_KEY")
    if scraper_api_key:
        print("Using ScraperAPI proxy...")
        pg = ProxyGenerator()
        success = pg.ScraperAPI(scraper_api_key)
        if success:
            scholarly.use_proxy(pg)
            return True
        print("ScraperAPI setup failed, trying free proxies...")

    # Fall back to free proxy rotation
    print("Setting up free proxy rotation...")
    pg = ProxyGenerator()
    try:
        success = pg.FreeProxies()
        scholarly.use_proxy(pg)
        print("Free proxy configured successfully.")
        return True
    except Exception as e:
        print(f"Warning: Could not set up proxy: {e}")
        return False


def load_existing_data():
    """Load existing publications.json as fallback."""
    try:
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def fetch_publications():
    """Fetch all publications for the given Google Scholar author ID."""
    print(f"Fetching author profile for Scholar ID: {SCHOLAR_ID}")

    # Set up proxy for CI environments (GitHub Actions, etc.)
    setup_proxy()

    author = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"  Attempt {attempt}/{MAX_RETRIES}...")
            author = scholarly.search_author_id(SCHOLAR_ID)
            author = scholarly.fill(author, sections=["publications"])
            break
        except Exception as e:
            print(f"  Attempt {attempt} failed: {e}")
            if attempt < MAX_RETRIES:
                wait = attempt * 10
                print(f"  Retrying in {wait}s...")
                time.sleep(wait)
                # Try rotating proxy on retry
                try:
                    pg = ProxyGenerator()
                    pg.FreeProxies()
                    scholarly.use_proxy(pg)
                    print("  Rotated to new proxy.")
                except Exception:
                    pass

    if author is None:
        print("Error: Could not fetch author profile after all retries.")
        existing = load_existing_data()
        if existing:
            print("Keeping existing publications.json unchanged.")
            sys.exit(0)
        else:
            sys.exit(1)

    publications = []

    for i, pub in enumerate(author.get("publications", [])):
        print(f"  Fetching details for publication {i + 1}...")

        try:
            # Fill in detailed info (abstract, full author list, etc.)
            pub_filled = scholarly.fill(pub)
            time.sleep(2)  # Be respectful to Google's servers
        except Exception as e:
            print(f"  Warning: Could not fetch details for pub {i + 1}: {e}")
            pub_filled = pub

        bib = pub_filled.get("bib", {})

        pub_data = {
            "title": bib.get("title", "Untitled"),
            "authors": bib.get("author", ""),
            "year": bib.get("pub_year", ""),
            "venue": bib.get("venue", bib.get("journal", bib.get("conference", ""))),
            "citations": pub_filled.get("num_citations", 0),
            "url": pub_filled.get("pub_url", ""),
            "scholar_url": f"https://scholar.google.com/citations?view_op=view_citation&hl=en&user={SCHOLAR_ID}&citation_for_view={pub_filled.get('author_pub_id', '')}",
        }

        publications.append(pub_data)

    # Sort by year (descending), then by citations (descending)
    publications.sort(key=lambda x: (-(int(x["year"]) if x["year"] else 0), -x["citations"]))

    return {
        "last_updated": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "author": author.get("name", "Harsha Gwalani"),
        "total_citations": author.get("citedby", 0),
        "h_index": author.get("hindex", 0),
        "i10_index": author.get("i10index", 0),
        "publications": publications,
    }


def main():
    data = fetch_publications()

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"\nSaved {len(data['publications'])} publications to {OUTPUT_FILE}")
    print(f"Total citations: {data['total_citations']}")
    print(f"h-index: {data['h_index']}")
    print(f"Last updated: {data['last_updated']}")


if __name__ == "__main__":
    main()
