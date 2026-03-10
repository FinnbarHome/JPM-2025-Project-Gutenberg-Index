"""
Exploratory analysis of the 2025 Project Gutenberg index.

Usage: python q4_analysis.py
"""

import re
import sys
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from parser_helpers import fetch_gutindex_text, parse_all_entries, build_dataframe


# -- Configuration --   

OUTPUT_DIR = Path("outputs")
TOP_N_LANGUAGES = 15
TOP_N_WORDS = 25
MIN_WORD_LENGTH = 3

# Calendar ordering for "Mon YYYY" labels
MONTH_ORDER = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}

# Common English stop-words, plus a few corpus-specific terms (vol, iii)
# that appear frequently in Gutenberg titles but carry no topical meaning
STOP_WORDS = frozenset({
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "it", "as", "was", "are", "be",
    "been", "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "shall", "can", "not",
    "no", "nor", "so", "if", "then", "than", "that", "this", "these",
    "those", "its", "his", "her", "their", "our", "my", "your", "all",
    "each", "every", "both", "few", "more", "most", "other", "some",
    "such", "only", "own", "same", "too", "very", "just", "about",
    "above", "after", "again", "against", "before", "below", "between",
    "through", "during", "into", "out", "over", "under", "up", "down",
    "off", "once", "here", "there", "when", "where", "why", "how",
    "what", "which", "who", "whom", "he", "him", "she", "they", "them",
    "we", "me", "you", "vol", "iii",
})

WORD_RE = re.compile(r"[a-z]+")
SEP = "-" * 60


# --- Aggregation ---


def count_languages(df: pd.DataFrame) -> pd.DataFrame:
    """Count entries per language, descending."""
    counts = df["language"].value_counts().reset_index()
    counts.columns = ["language", "count"]
    return counts


def _month_sort_key(label: str) -> tuple[int, int]:
    """Sort key for 'Mon YYYY' labels in calendar order."""
    # Labels look like "Jan 2025" -- sort by year first, then month
    parts = label.split()
    year = int(parts[1]) if len(parts) > 1 else 0
    month = MONTH_ORDER.get(parts[0], 0)
    return (year, month)


def count_by_month(df: pd.DataFrame) -> pd.DataFrame:
    """Count entries per month, sorted chronologically."""
    counts = df["indexed_month"].value_counts().reset_index()
    counts.columns = ["month", "count"]

    # Sort chronologically rather than by count
    counts = counts.sort_values(by="month", key=lambda s: s.map(_month_sort_key))
    return counts.reset_index(drop=True)


def count_title_words(titles: pd.Series, top_n: int = TOP_N_WORDS) -> pd.DataFrame:
    """Count the most common non-stop-words across all titles."""
    word_counts: Counter[str] = Counter()

    for title in titles:
        # Lowercase and extract alphabetic tokens only
        words = WORD_RE.findall(title.lower())

        # Drop stop-words and very short words (likely abbreviations or noise)
        meaningful = [w for w in words if w not in STOP_WORDS and len(w) >= MIN_WORD_LENGTH]
        word_counts.update(meaningful)

    return pd.DataFrame(word_counts.most_common(top_n), columns=["word", "count"])


# --- Plotting ---


def save_language_chart(lang_counts: pd.DataFrame, path: Path) -> None:
    """Save horizontal bar chart of top languages."""
    # Reverse so the largest bar is at the top of the chart
    top = lang_counts.head(TOP_N_LANGUAGES).iloc[::-1]

    fig, ax = plt.subplots(figsize=(8, max(4, TOP_N_LANGUAGES * 0.35)))
    ax.barh(top["language"], top["count"])
    ax.set_xlabel("Number of texts")
    ax.set_title(f"Top {TOP_N_LANGUAGES} Languages in the 2025 Gutenberg Index")

    # Label each bar with its count for readability
    for i, count in enumerate(top["count"]):
        ax.text(count + 0.5, i, str(count), va="center", fontsize=9)

    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def save_month_chart(month_counts: pd.DataFrame, path: Path) -> None:
    """Save vertical bar chart of texts per month."""
    fig, ax = plt.subplots(figsize=(10, 5))

    x = range(len(month_counts))
    ax.bar(x, month_counts["count"])
    ax.set_xticks(list(x))
    ax.set_xticklabels(month_counts["month"], rotation=45, ha="right")
    ax.set_xlabel("Month")
    ax.set_ylabel("Number of texts")
    ax.set_title("Texts Indexed by Month — 2025 Gutenberg Index")

    for i, count in enumerate(month_counts["count"]):
        ax.text(i, count + 2, str(count), ha="center", fontsize=9)

    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def save_word_chart(word_counts: pd.DataFrame, path: Path, top_n: int = 20) -> None:
    """Save horizontal bar chart of top title words."""
    top = word_counts.head(top_n).iloc[::-1]

    fig, ax = plt.subplots(figsize=(8, max(4, top_n * 0.3)))
    ax.barh(top["word"], top["count"])
    ax.set_xlabel("Frequency")
    ax.set_title(f"Top {top_n} Non-Stop-Words in Titles")

    for i, count in enumerate(top["count"]):
        ax.text(count + 0.3, i, str(count), va="center", fontsize=9)

    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


# --- Console output ---


def print_validation(df: pd.DataFrame) -> None:
    """Print parser coverage metrics."""
    total = len(df)
    non_english = int((df["language"] != "English").sum())
    empty_titles = int((df["title"] == "").sum())

    print(f"\n{SEP}")
    print("  Validation")
    print(SEP)
    print(f"  Total entries:          {total:>6,}")
    print(f"  Explicit language tags: {non_english:>6,}  ({non_english / total * 100:.1f}%)")
    print(f"  Empty titles:           {empty_titles:>6,}")
    print(f"  Unique languages:       {df['language'].nunique():>6}")
    print(f"  Unique months:          {df['indexed_month'].nunique():>6}")

    # Show a few rows so the user can eyeball whether parsing looks right
    print()
    print("  Sample entries:")
    for _, row in df.head(5).iterrows():
        title = row["title"][:50]
        print(f"    [{row['ebook_number']}] {title:<50}  | {row['language']:<10} | {row['indexed_month']}")
    print()


def print_results(
    lang_counts: pd.DataFrame,
    month_counts: pd.DataFrame,
    word_counts: pd.DataFrame,
) -> None:
    """Print key analysis results to the console."""
    print(f"{SEP}")
    print("  Language Distribution (top 10)")
    print(SEP)
    for _, row in lang_counts.head(10).iterrows():
        print(f"    {row['language']:<20} {row['count']:>5}")

    print(f"\n{SEP}")
    print("  Month Distribution")
    print(SEP)
    for _, row in month_counts.iterrows():
        print(f"    {row['month']:<12} {row['count']:>5}")

    print(f"\n{SEP}")
    print("  Title Words (top 10)")
    print(SEP)
    for _, row in word_counts.head(10).iterrows():
        print(f"    {row['word']:<20} {row['count']:>5}")
    print()


# --- Summary file ---


def write_summary(
    df: pd.DataFrame,
    lang_counts: pd.DataFrame,
    month_counts: pd.DataFrame,
    word_counts: pd.DataFrame,
) -> None:
    """Write a markdown summary to outputs/summary.md."""
    lang_rows = "\n".join(
        f"| {r['language']} | {r['count']} |" for _, r in lang_counts.head(10).iterrows()
    )
    month_rows = "\n".join(
        f"| {r['month']} | {r['count']} |" for _, r in month_counts.iterrows()
    )
    word_rows = "\n".join(
        f"| {r['word']} | {r['count']} |" for _, r in word_counts.head(15).iterrows()
    )

    md = f"""\
# Analysis Summary: 2025 Project Gutenberg Index

## Dataset

- **Total entries parsed:** {len(df):,}
- **Unique languages:** {df['language'].nunique()}
- **Unique months:** {df['indexed_month'].nunique()}

## Top 10 Languages

| Language | Count |
|---|---:|
{lang_rows}

## Monthly Distribution

| Month | Count |
|---|---:|
{month_rows}

## Top 15 Title Words

| Word | Count |
|---|---:|
{word_rows}

## Caveats

- The GUTINDEX.2025 file may include entries from early 2026.
- Entries without an explicit [Language: ...] tag default to English.
- Stop-word filter is English-only; non-English function words may appear.
- No stemming applied -- *story* and *stories* count separately.
"""
    (OUTPUT_DIR / "summary.md").write_text(md, encoding="utf-8")


# --- Main ---


def main() -> None:
    # Ensure Unicode output works on Windows
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Fetch the index file from Project Gutenberg
    print("Fetching GUTINDEX.2025 ...")
    raw_text = fetch_gutindex_text()
    print(f"  Downloaded {len(raw_text):,} characters.")

    # Parse the raw text into structured records
    print("Parsing entries ...")
    entries = parse_all_entries(raw_text)
    df = build_dataframe(entries)
    print(f"  Parsed {len(df):,} entries.")

    # Quick sanity check on parser output
    print_validation(df)

    # Language distribution
    lang_counts = count_languages(df)
    lang_counts.to_csv(OUTPUT_DIR / "language_distribution.csv", index=False)
    save_language_chart(lang_counts, OUTPUT_DIR / "language_distribution.png")

    # Monthly distribution
    month_counts = count_by_month(df)
    month_counts.to_csv(OUTPUT_DIR / "month_distribution.csv", index=False)
    save_month_chart(month_counts, OUTPUT_DIR / "month_distribution.png")

    # Most common non-stop-words in titles
    word_counts = count_title_words(df["title"])
    word_counts.to_csv(OUTPUT_DIR / "title_word_distribution.csv", index=False)
    save_word_chart(word_counts, OUTPUT_DIR / "title_word_distribution.png")

    # Print results and write markdown summary
    print_results(lang_counts, month_counts, word_counts)
    write_summary(df, lang_counts, month_counts, word_counts)
    print(f"All outputs saved to {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
