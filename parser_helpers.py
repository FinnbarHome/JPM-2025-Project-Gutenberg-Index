"""Parsing helpers for the Project Gutenberg GUTINDEX format."""

import re
import urllib.error
import urllib.request
from dataclasses import dataclass

import pandas as pd

# Url of the GUTINDEX file
GUTINDEX_URL = "https://www.gutenberg.org/dirs/GUTINDEX.2025"

# Marker for start of the listings
LISTINGS_MARKER = "<===LISTINGS===>"

# As stated in the file header, entries without a [Language:] tag are English
DEFAULT_LANGUAGE = "English"


# -- Regex patterns --


#  Pattern for the monthly sections, it matches the lines like: ~ ~ ~ ~ Posting Dates for the below eBooks:  1 Mar 2026 to 8 Mar 2026 ~ ~ ~ ~
MONTH_HEADER_RE = re.compile(
    r"~\s+~\s+~\s+~\s+Posting Dates.*?:\s+\d+\s+(\w{3})\s+(\d{4})"
)

# Ebook number = 4-6 digits on the first line of each entry
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
    author: str
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
        if month_header_match is not None:
            if current_month is not None:
                print(f"Saving section for {current_month} with {len(current_lines)} lines")
                # Build tuple with current month, and all the lines for that month
                sections.append((current_month, "\n".join(current_lines)))

            # Group 1 is the month, Group 2 = year of month
            current_month = f"{month_header_match.group(1)} {month_header_match.group(2)}"
            print(f"Found month header: {current_month}")

            current_lines = []

        # If line is not a month header + in a month section + add line to current lines
        elif current_month is not None:
            current_lines.append(line)

    # Save final section
    if current_month is not None:
        print(f"Saving final section for {current_month} with {len(current_lines)} lines")
        sections.append((current_month, "\n".join(current_lines)))

    return sections


def _split_into_entries(section_text: str) -> list[str]:
    """Split a month section into candidate entry blocks on blank lines."""
    candidates: list[str] = []
    block_counter = 0

    # Split the section into blocks on blank lines
    for block in re.split(r"\n\s*\n", section_text):
        block = block.strip()

        if not block:
            continue
        block_counter += 1

        # Skip non-entry blocks: column headers and informational notes
        if TITLE_HEADER_RE.match(block): # e.g. TITLE and AUTHOR
            continue
        if NOTE_LINE_RE.match(block): # e.g. ****
            continue

        first_line = block.splitlines()[0]
        if EBOOK_NUMBER_RE.search(first_line):
            # print(f"Appending candidate block: {first_line}")
            candidates.append(block)

    print(
        f"Non-empty blocks: {block_counter} | "
        f"Candidate entry blocks: {len(candidates)} | "
        f"Skipped: {block_counter - len(candidates)}"
    )
    return candidates


# --- Field extraction ---


def extract_ebook_number(entry_text: str) -> int | None:
    """Extract the ebook number from the first line."""
    # Split entry text into lines + search for the ebook number
    ebook_number_match = EBOOK_NUMBER_RE.search(entry_text.splitlines()[0])

    if ebook_number_match is not None:
        ebook_number = int(ebook_number_match.group(1))
    else:
        ebook_number = None

    # print(f"Extracted ebook number: {ebook_number}")
    return ebook_number


def _extract_title_author_text(entry_text: str) -> str:
    """Extract the combined title/author text before metadata begins."""
    # Split entry text into lines
    lines = entry_text.splitlines()

    title_lines: list[str] = []
    for line in lines:
        # If line is a metadata line, break the loop
        if METADATA_LINE_RE.match(line):
            break
        title_lines.append(line)

    if not title_lines:
        return ""

    # Ebook number sits at end of first line, strip it
    title_lines[0] = EBOOK_NUMBER_RE.sub("", title_lines[0]).rstrip()

    # Join the multi-line title/author block into a single string
    cleaned_parts: list[str] = []
    for part in title_lines:
        cleaned_part = part.strip()
        if cleaned_part:
            cleaned_parts.append(cleaned_part)

    return " ".join(cleaned_parts)


def extract_title(entry_text: str) -> str:
    """Extract title, splitting from author on last ', by '."""
    full_title = _extract_title_author_text(entry_text)

    # Author follows the last ", by " -- keep only the title portion
    author_separator_index = full_title.rfind(", by ")

    if author_separator_index > 0:
        # Return the title portion (before the author)
        return full_title[:author_separator_index].strip()

    return full_title.strip()


def extract_author(entry_text: str) -> str:
    """Extract author, using last ', by ' as the split point."""

    # Extract the title/author text
    full_title = _extract_title_author_text(entry_text)

    # Find the index of the author separator
    author_separator_index = full_title.rfind(", by ")

    if author_separator_index > 0:
        return full_title[author_separator_index + len(", by "):].strip()

    return ""


def extract_language(entry_text: str) -> str:
    """Extract [Language: ...] tag, defaulting to English."""
    # Search for the language tag
    language_max = LANGUAGE_RE.search(entry_text)

    # If language tag is found, return language else return default language
    if language_max is not None:
        return language_max.group(1).strip().title()
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
        author=extract_author(entry_text),
        language=extract_language(entry_text),
        indexed_month=month,
        raw_text=entry_text,
    )


def parse_all_entries(raw_text: str) -> list[GutenbergEntry]:
    """Parse raw GUTINDEX text into structured entry records."""
    # Extract listings from raw text
    listings = _extract_listings(raw_text)

    entries: list[GutenbergEntry] = []

    for month, section in _split_by_month(listings):
        # Split section into candidate entry blocks
        for block in _split_into_entries(section):
            # Parse entry
            entry = parse_entry(block, month)

            # If entry is not None, add it to list
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
            "author": e.author.strip(),
            "language": e.language.strip(),
            "indexed_month": e.indexed_month,
        }
        for e in entries
    ])
