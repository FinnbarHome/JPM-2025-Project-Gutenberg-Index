"""Parsing helpers for the Project Gutenberg GUTINDEX format."""

import re
import urllib.error
import urllib.request
from dataclasses import dataclass

import pandas as pd

GUTINDEX_URL = "https://www.gutenberg.org/dirs/GUTINDEX.2025"
LISTINGS_MARKER = "<===LISTINGS===>"

# per file header, untagged entries default to English
DEFAULT_LANGUAGE = "English"


# -- Regex patterns --

# monthly section headers, e.g. ~ ~ ~ ~ Posting Dates ... ~ ~ ~ ~
MONTH_HEADER_RE = re.compile(
    r"~\s+~\s+~\s+~\s+Posting Dates.*?:\s+\d+\s+(\w{3})\s+(\d{4})"
)

# 4-6 digit ebook number at end of first line, optional trailing C = copyrighted
EBOOK_NUMBER_RE = re.compile(r"\b(\d{4,6})\s*C?\s*$")

LANGUAGE_RE = re.compile(r"\[Language:\s*(.+?)\s*\]", re.IGNORECASE)
# indented bracket lines = metadata ([Subtitle:], [Illustrator:] etc)
METADATA_LINE_RE = re.compile(r"^\s+\[")

# column headers + note lines between entry blocks
TITLE_HEADER_RE = re.compile(r"^\s*TITLE and AUTHOR", re.IGNORECASE)
NOTE_LINE_RE = re.compile(r"^\s*\*{4}")


@dataclass
class GutenbergEntry:
    """One parsed record from the index."""
    ebook_number: int
    title: str
    author: str
    language: str
    indexed_month: str
    raw_text: str  # for debugging / spot-checking


# --- Data acquisition ---


def fetch_gutindex_text(url: str = GUTINDEX_URL) -> str:
    """Download raw GUTINDEX file. Returns full text, BOM stripped."""
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            # utf-8-sig strips BOM which can break parsing
            return response.read().decode("utf-8-sig")
    except urllib.error.URLError as url_error:
        raise RuntimeError(f"Failed to download {url}") from url_error


# --- Splitting raw text into entry blocks ---


def _extract_listings(raw_index_text: str) -> str:
    """Return everything after the listings marker, stripping the preamble."""
    marker_position = raw_index_text.find(LISTINGS_MARKER)

    if marker_position == -1:
        raise ValueError(f"Listings marker not found: {LISTINGS_MARKER!r}")

    return raw_index_text[marker_position + len(LISTINGS_MARKER):]


def _split_by_month(listings_text: str) -> list[tuple[str, str]]:
    """Split listings into (month_label, section_text) pairs."""
    month_sections: list[tuple[str, str]] = []
    current_month_label: str | None = None
    current_section_lines: list[str] = []

    for line in listings_text.splitlines():
        month_header_match = MONTH_HEADER_RE.search(line)
        if month_header_match is not None:
            if current_month_label is not None:
                month_sections.append((current_month_label, "\n".join(current_section_lines)))

            # group(1) = month abbrev, group(2) = year
            current_month_label = f"{month_header_match.group(1)} {month_header_match.group(2)}"
            current_section_lines = []

        elif current_month_label is not None:
            current_section_lines.append(line)

    # flush last section
    if current_month_label is not None:
        month_sections.append((current_month_label, "\n".join(current_section_lines)))

    return month_sections


def _split_into_entries(section_text: str) -> list[str]:
    """Split a month section into candidate entry blocks on blank lines."""
    candidate_entries: list[str] = []

    for text_block in re.split(r"\n\s*\n", section_text):
        text_block = text_block.strip()
        if not text_block:
            continue

        # skip non-entry blocks (column headers, notes)
        if TITLE_HEADER_RE.match(text_block):  # e.g. TITLE and AUTHOR
            continue
        if NOTE_LINE_RE.match(text_block):  # e.g. ****
            continue

        first_line = text_block.splitlines()[0]
        if EBOOK_NUMBER_RE.search(first_line):
            candidate_entries.append(text_block)

    return candidate_entries


# --- Field extraction ---


def extract_ebook_number(entry_text: str) -> int | None:
    """Extract the ebook number from the first line."""
    ebook_number_match = EBOOK_NUMBER_RE.search(entry_text.splitlines()[0])

    if ebook_number_match is not None:
        return int(ebook_number_match.group(1))

    return None


def _extract_title_author_text(entry_text: str) -> str:
    """Extract the combined title/author text before metadata begins."""
    entry_lines = entry_text.splitlines()

    title_author_lines: list[str] = []
    for line in entry_lines:
        # stop at first metadata line ([Subtitle:], [Language:] etc)
        if METADATA_LINE_RE.match(line):
            break
        title_author_lines.append(line)

    if not title_author_lines:
        return ""

    # strip ebook number from end of first line
    title_author_lines[0] = EBOOK_NUMBER_RE.sub("", title_author_lines[0]).rstrip()

    # join multi-line title/author into single string
    cleaned_parts: list[str] = []
    for part in title_author_lines:
        stripped_part = part.strip()
        if stripped_part:
            cleaned_parts.append(stripped_part)

    return " ".join(cleaned_parts)


def extract_title(entry_text: str) -> str:
    """Extract title, splitting from author on last ', by '."""
    full_title_author = _extract_title_author_text(entry_text)

    # split on last ", by " to separate title from author
    author_split_position = full_title_author.rfind(", by ")

    if author_split_position > 0:
        return full_title_author[:author_split_position].strip()

    return full_title_author.strip()


def extract_author(entry_text: str) -> str:
    """Extract author, using last ', by ' as the split point."""
    full_title_author = _extract_title_author_text(entry_text)
    author_split_position = full_title_author.rfind(", by ")

    if author_split_position > 0:
        return full_title_author[author_split_position + len(", by "):].strip()

    return ""


def extract_language(entry_text: str) -> str:
    """Extract [Language: ...] tag, defaulting to English."""
    language_match = LANGUAGE_RE.search(entry_text)

    if language_match is not None:
        return language_match.group(1).strip().title()
    return DEFAULT_LANGUAGE


# --- Entry parsing ---


def parse_entry(entry_text: str, month_label: str) -> GutenbergEntry | None:
    """Parse one candidate block. Returns None if unparseable."""
    ebook_number = extract_ebook_number(entry_text)

    if ebook_number is None:
        return None

    return GutenbergEntry(
        ebook_number=ebook_number,
        title=extract_title(entry_text),
        author=extract_author(entry_text),
        language=extract_language(entry_text),
        indexed_month=month_label,
        raw_text=entry_text,
    )


def parse_all_entries(raw_index_text: str) -> list[GutenbergEntry]:
    """Parse raw GUTINDEX text into structured entry records."""
    listings_text = _extract_listings(raw_index_text)

    parsed_entries: list[GutenbergEntry] = []

    for month_label, section_text in _split_by_month(listings_text):
        for entry_block in _split_into_entries(section_text):
            parsed_entry = parse_entry(entry_block, month_label)

            if parsed_entry is not None:
                parsed_entries.append(parsed_entry)

    return parsed_entries


# --- DataFrame construction ---


def build_dataframe(entries: list[GutenbergEntry]) -> pd.DataFrame:
    """Build a tidy DataFrame from parsed entries (excludes raw text)."""
    return pd.DataFrame([
        {
            "ebook_number": entry.ebook_number,
            "title": entry.title.strip(),
            "author": entry.author.strip(),
            "language": entry.language.strip(),
            "indexed_month": entry.indexed_month,
        }
        for entry in entries
    ])
