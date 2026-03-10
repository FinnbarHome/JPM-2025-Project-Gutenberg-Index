"""
Download and parse the 2025 Gutenberg index, then write every parsed entry to a CSV file.

Usage:
    python print_parsed_entries.py
"""

import csv
import sys
from pathlib import Path

from parser_helpers import fetch_gutindex_text, parse_all_entries


OUTPUT_FILE = Path("parsed_entries.csv")


def main() -> None:
    # Ensure Unicode output works cleanly on Windows terminals
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("Fetching GUTINDEX.2025 ...")
    raw_text = fetch_gutindex_text()
    print(f"Downloaded {len(raw_text)} characters.")

    print("Parsing entries ...")
    entries = parse_all_entries(raw_text)
    print(f"Collected {len(entries)} GutenbergEntry objects.")

    # Overwrite the CSV on every run 
    with OUTPUT_FILE.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["ebook_number", "title", "author", "language", "indexed_month", "raw_text"])

        for entry in entries:
            writer.writerow([
                entry.ebook_number,
                entry.title,
                entry.author,
                entry.language,
                entry.indexed_month,
                entry.raw_text,
            ])

    print(f"Wrote parsed entries to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
