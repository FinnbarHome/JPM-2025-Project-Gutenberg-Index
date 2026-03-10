"""Parsing helpers for the Project Gutenberg GUTINDEX format."""

import re
import urllib.error
import urllib.request
from dataclasses import dataclass

import pandas as pd

# Url of the GUTINDEX file
GUTINDEX_URL = "https://www.gutenberg.org/dirs/GUTINDEX.2025"

# Marker for the start of the listings, everything above this marker is not part of the listings
LISTINGS_MARKER = "<===LISTINGS===>"

# As stated in the file header, entries without a [Language:] tag are English
DEFAULT_LANGUAGE = "English"


# -- Regex patterns --


#  Pattern for the monthly sections, it matches the lines like: ~ ~ ~ ~ Posting Dates for the below eBooks:  1 Mar 2026 to 8 Mar 2026 ~ ~ ~ ~
MONTH_HEADER_RE = re.compile(
    r"~\s+~\s+~\s+~\s+Posting Dates.*?:\s+\d+\s+(\w{3})\s+(\d{4})"
)

# Ebook numbers appear right-aligned on the first line of each entry
# An optional trailing 'C' marks copyrighted works
EBOOK_NUMBER_RE = re.compile(r"\b(\d{4,6})\s*C?\s*$")

# Matches the lines like: [Language: Finnish]
LANGUAGE_RE = re.compile(r"\[Language:\s*(.+?)\s*\]", re.IGNORECASE)
# Matches the lines like: [Subtitle: ...], [Illustrator: ...] etc
METADATA_LINE_RE = re.compile(r"^\s+\[")

# Matches the lines like: TITLE and AUTHOR
TITLE_HEADER_RE = re.compile(r"^\s*TITLE and AUTHOR", re.IGNORECASE)
# Matches the lines like: ****
NOTE_LINE_RE = re.compile(r"^\s*\*{4}")


@dataclass
class GutenbergEntry:
    """One parsed record from the index."""
    ebook_number: int
    title: str
    language: str
    indexed_month: str
    # Mainly used for debugging
    raw_text: str


# --- Data acquisition ---


def fetch_gutindex_text(url: str = GUTINDEX_URL) -> str:
    """Download raw GUTINDEX file. Returns full text, Byte-Order-Mark stripped."""
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            # Byte-Order-Mark stripped, not needed here + can cause issues with parser
            return response.read().decode("utf-8-sig")
    except urllib.error.URLError as error:
        raise RuntimeError(f"Failed to download {url}") from error


# --- Splitting raw text into entry blocks ---


def _extract_listings(raw_text: str) -> str:
    """Strip the intro header, return everything after the listings marker."""
    position = raw_text.find(LISTINGS_MARKER)

    if position == -1:
        raise ValueError(f"Listings marker not found: {LISTINGS_MARKER!r}")

    # Return everything after the listings marker
    return raw_text[position + len(LISTINGS_MARKER):]


def _split_by_month(listings_text: str) -> list[tuple[str, str]]:
    """Split listings into (month_label, section_text) pairs."""
    sections: list[tuple[str, str]] = []
    current_month: str | None = None
    current_lines: list[str] = []

    for line in listings_text.splitlines():
        month_header_match = MONTH_HEADER_RE.search(line)
        if month_header_match:
            if current_month is not None:
                # Build tuple with current month, and all the lines 
                print(f"Saving section for {current_month} with {len(current_lines)} lines")
                sections.append((current_month, "\n".join(current_lines)))

            # Start accumulating lines for the new month, e.g. "Jan 2025"
            current_month = f"{month_header_match.group(1)} {month_header_match.group(2)}"
            print(f"Found month header: {current_month}")
            current_lines = []
        elif current_month is not None:
            current_lines.append(line)

    # Flush the last section
    if current_month is not None:
        print(f"Saving final section for {current_month} with {len(current_lines)} lines")
        sections.append((current_month, "\n".join(current_lines)))

    return sections


def _split_into_entries(section_text: str) -> list[str]:
    """Split a month section into candidate entry blocks on blank lines."""
    candidates: list[str] = []

    for block in re.split(r"\n\s*\n", section_text):
        block = block.strip()
        if not block:
            continue

        # Skip non-entry blocks: column headers and informational notes
        if TITLE_HEADER_RE.match(block):
            continue
        if NOTE_LINE_RE.match(block):
            continue

        # A valid entry always has an ebook number on its first line
        if EBOOK_NUMBER_RE.search(block.splitlines()[0]):
            candidates.append(block)

    return candidates


# --- Field extraction ---


def extract_ebook_number(entry_text: str) -> int | None:
    """Extract the ebook number from the first line."""
    match = EBOOK_NUMBER_RE.search(entry_text.splitlines()[0])
    return int(match.group(1)) if match else None


def extract_title(entry_text: str) -> str:
    """Extract title, splitting from author on last ', by '."""
    lines = entry_text.splitlines()

    # Title (and author) can span multiple lines before the metadata.
    # Collect everything up to the first bracketed metadata line.
    title_lines: list[str] = []
    for line in lines:
        if METADATA_LINE_RE.match(line):
            break
        title_lines.append(line)

    if not title_lines:
        return ""

    # The ebook number sits at the end of the first line -- strip it
    title_lines[0] = EBOOK_NUMBER_RE.sub("", title_lines[0]).rstrip()

    # Join the multi-line title into a single string
    full = " ".join(part.strip() for part in title_lines if part.strip())

    # Author follows the last ", by " -- keep only the title portion
    sep = full.rfind(", by ")
    if sep > 0:
        return full[:sep].strip()

    return full.strip()


def extract_language(entry_text: str) -> str:
    """Extract [Language: ...] tag, defaulting to English."""
    match = LANGUAGE_RE.search(entry_text)
    if match:
        return match.group(1).strip().title()
    return DEFAULT_LANGUAGE


# --- Entry parsing ---


def parse_entry(entry_text: str, month: str) -> GutenbergEntry | None:
    """Parse one candidate block. Returns None if unparseable."""
    ebook_number = extract_ebook_number(entry_text)
    if ebook_number is None:
        return None

    return GutenbergEntry(
        ebook_number=ebook_number,
        title=extract_title(entry_text),
        language=extract_language(entry_text),
        indexed_month=month,
        raw_text=entry_text,
    )


def parse_all_entries(raw_text: str) -> list[GutenbergEntry]:
    """Parse raw GUTINDEX text into structured entry records."""
    listings = _extract_listings(raw_text)

    entries: list[GutenbergEntry] = []
    for month, section in _split_by_month(listings):
        for block in _split_into_entries(section):
            entry = parse_entry(block, month)
            if entry is not None:
                entries.append(entry)

    return entries


# --- DataFrame construction ---


def build_dataframe(entries: list[GutenbergEntry]) -> pd.DataFrame:
    """Build a tidy DataFrame from parsed entries (excludes raw text)."""
    return pd.DataFrame([
        {
            "ebook_number": e.ebook_number,
            "title": e.title.strip(),
            "language": e.language.strip(),
            "indexed_month": e.indexed_month,
        }
        for e in entries
    ])
