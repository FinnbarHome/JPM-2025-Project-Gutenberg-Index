"""
Dump all parsed entries to a CSV for inspection/debugging.

Usage: python print_parsed_entries.py
"""

import csv
import sys
from pathlib import Path

from parser_helpers import fetch_gutindex_text, parse_all_entries


OUTPUT_CSV_PATH = Path("parsed_entries.csv")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("Fetching GUTINDEX.2025 ...")
    raw_index_text = fetch_gutindex_text()
    print(f"Downloaded {len(raw_index_text)} characters.")

    print("Parsing entries ...")
    parsed_entries = parse_all_entries(raw_index_text)
    print(f"Collected {len(parsed_entries)} GutenbergEntry objects.")

    with OUTPUT_CSV_PATH.open("w", encoding="utf-8", newline="") as output_file:
        csv_writer = csv.writer(output_file)
        csv_writer.writerow(["ebook_number", "title", "author", "language", "indexed_month", "raw_text"])

        for entry in parsed_entries:
            csv_writer.writerow([
                entry.ebook_number,
                entry.title,
                entry.author,
                entry.language,
                entry.indexed_month,
                entry.raw_text,
            ])

    print(f"Wrote parsed entries to {OUTPUT_CSV_PATH}")


if __name__ == "__main__":
    main()
