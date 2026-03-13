"""
Exploratory analysis of the 2025 Project Gutenberg index.

Usage:
    python gutenberg_index_analysis.py
"""

import re
import sys
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
import nltk
import pandas as pd
from nltk.corpus import stopwords

from parser_helpers import build_dataframe, fetch_gutindex_text, parse_all_entries

# download stopwords corpus if not already present
nltk.download("stopwords", quiet=True)


# -- Configuration --

OUTPUT_DIRECTORY = Path("outputs")
TOP_LANGUAGE_COUNT = 15
TOP_TITLE_WORD_COUNT = 25
MINIMUM_TITLE_WORD_LENGTH = 3

MONTH_ORDER = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}

# nltk english stop words + gutenberg-specific noise terms
STOP_WORDS = frozenset(stopwords.words("english")) | {"vol", "iii"}

TITLE_WORD_PATTERN = re.compile(r"[a-z]+")
SECTION_SEPARATOR = "-" * 60


# --- Aggregation ---


def count_languages(entries_dataframe: pd.DataFrame) -> pd.DataFrame:
    """Count entries per language, descending."""
    language_counts = entries_dataframe["language"].value_counts().reset_index()
    language_counts.columns = ["language", "count"]
    return language_counts


def _month_sort_key(month_label: str) -> tuple[int, int]:
    """Sort key for 'Mon YYYY' labels in calendar order."""
    # sort by year first, then month
    month_label_parts = month_label.split()
    year_number = int(month_label_parts[1]) if len(month_label_parts) > 1 else 0
    month_number = MONTH_ORDER.get(month_label_parts[0], 0)
    return (year_number, month_number)


def count_by_month(entries_dataframe: pd.DataFrame) -> pd.DataFrame:
    """Count entries per month, sorted chronologically."""
    month_counts = entries_dataframe["indexed_month"].value_counts().reset_index()
    month_counts.columns = ["month", "count"]

    # chronological order, not by count
    month_counts = month_counts.sort_values(
        by="month",
        key=lambda month_series: month_series.map(_month_sort_key),
    )
    return month_counts.reset_index(drop=True)


def count_title_words(
    title_series: pd.Series,
    top_word_count: int = TOP_TITLE_WORD_COUNT,
) -> pd.DataFrame:
    """Count the most common non-stop-words across all titles."""
    word_frequency_counter: Counter[str] = Counter()

    for title_text in title_series:
        # lowercase + extract alpha tokens only
        extracted_words = TITLE_WORD_PATTERN.findall(title_text.lower())

        # drop stop words and very short words (abbreviations / noise)
        meaningful_words = [
            word
            for word in extracted_words
            if word not in STOP_WORDS and len(word) >= MINIMUM_TITLE_WORD_LENGTH
        ]
        word_frequency_counter.update(meaningful_words)

    return pd.DataFrame(
        word_frequency_counter.most_common(top_word_count),
        columns=["word", "count"],
    )


# --- Plotting ---


def save_language_chart(language_counts: pd.DataFrame, output_path: Path) -> None:
    """Save horizontal bar chart of top languages."""
    # reverse so largest bar sits at top
    top_language_counts = language_counts.head(TOP_LANGUAGE_COUNT).iloc[::-1]

    chart_figure, chart_axes = plt.subplots(
        figsize=(8, max(4, TOP_LANGUAGE_COUNT * 0.35))
    )
    chart_axes.barh(top_language_counts["language"], top_language_counts["count"])
    chart_axes.set_xlabel("Number of texts")
    chart_axes.set_title(f"Top {TOP_LANGUAGE_COUNT} Languages in the 2025 Gutenberg Index")

    # label each bar with its count
    for bar_index, count_value in enumerate(top_language_counts["count"]):
        chart_axes.text(count_value + 0.5, bar_index, str(count_value), va="center", fontsize=9)

    chart_figure.tight_layout()
    chart_figure.savefig(output_path, dpi=150)
    plt.close(chart_figure)


def save_month_chart(month_counts: pd.DataFrame, output_path: Path) -> None:
    """Save vertical bar chart of texts per month."""
    chart_figure, chart_axes = plt.subplots(figsize=(10, 5))

    month_bar_positions = range(len(month_counts))
    chart_axes.bar(month_bar_positions, month_counts["count"])
    chart_axes.set_xticks(list(month_bar_positions))
    chart_axes.set_xticklabels(month_counts["month"], rotation=45, ha="right")
    chart_axes.set_xlabel("Month")
    chart_axes.set_ylabel("Number of texts")
    chart_axes.set_title("Texts Indexed by Month — 2025 Gutenberg Index")

    for bar_index, count_value in enumerate(month_counts["count"]):
        chart_axes.text(bar_index, count_value + 2, str(count_value), ha="center", fontsize=9)

    chart_figure.tight_layout()
    chart_figure.savefig(output_path, dpi=150)
    plt.close(chart_figure)


def save_title_word_chart(
    title_word_counts: pd.DataFrame,
    output_path: Path,
    top_chart_word_count: int = 20,
) -> None:
    """Save horizontal bar chart of top title words."""
    top_title_word_counts = title_word_counts.head(top_chart_word_count).iloc[::-1]

    chart_figure, chart_axes = plt.subplots(
        figsize=(8, max(4, top_chart_word_count * 0.3))
    )
    chart_axes.barh(top_title_word_counts["word"], top_title_word_counts["count"])
    chart_axes.set_xlabel("Frequency")
    chart_axes.set_title(f"Top {top_chart_word_count} Non-Stop-Words in Titles")

    for bar_index, count_value in enumerate(top_title_word_counts["count"]):
        chart_axes.text(count_value + 0.3, bar_index, str(count_value), va="center", fontsize=9)

    chart_figure.tight_layout()
    chart_figure.savefig(output_path, dpi=150)
    plt.close(chart_figure)


# --- Console output ---


def print_validation(entries_dataframe: pd.DataFrame) -> None:
    """Print parser coverage metrics."""
    total_entry_count = len(entries_dataframe)
    non_english_count = int((entries_dataframe["language"] != "English").sum())
    empty_title_count = int((entries_dataframe["title"] == "").sum())

    print(f"\n{SECTION_SEPARATOR}")
    print("  Validation")
    print(SECTION_SEPARATOR)
    print(f"  Total entries:          {total_entry_count:>6,}")
    print(
        f"  Explicit language tags: {non_english_count:>6,}  "
        f"({non_english_count / total_entry_count * 100:.1f}%)"
    )
    print(f"  Empty titles:           {empty_title_count:>6,}")
    print(f"  Unique languages:       {entries_dataframe['language'].nunique():>6}")
    print(f"  Unique months:          {entries_dataframe['indexed_month'].nunique():>6}")

    # eyeball check — sample rows to verify parsing looks right
    print()
    print("  Sample entries:")
    for _, sample_row in entries_dataframe.head(5).iterrows():
        truncated_title = sample_row["title"][:50]
        print(
            f"    [{sample_row['ebook_number']}] {truncated_title:<50}  | "
            f"{sample_row['language']:<10} | {sample_row['indexed_month']}"
        )
    print()


def print_results(
    language_counts: pd.DataFrame,
    month_counts: pd.DataFrame,
    title_word_counts: pd.DataFrame,
) -> None:
    """Print key analysis results to the console."""
    print(f"{SECTION_SEPARATOR}")
    print("  Language Distribution (top 10)")
    print(SECTION_SEPARATOR)
    for _, language_row in language_counts.head(10).iterrows():
        print(f"    {language_row['language']:<20} {language_row['count']:>5}")

    print(f"\n{SECTION_SEPARATOR}")
    print("  Month Distribution")
    print(SECTION_SEPARATOR)
    for _, month_row in month_counts.iterrows():
        print(f"    {month_row['month']:<12} {month_row['count']:>5}")

    print(f"\n{SECTION_SEPARATOR}")
    print("  Title Words (top 10)")
    print(SECTION_SEPARATOR)
    for _, word_row in title_word_counts.head(10).iterrows():
        print(f"    {word_row['word']:<20} {word_row['count']:>5}")
    print()


# --- Summary file ---


def write_summary(
    entries_dataframe: pd.DataFrame,
    language_counts: pd.DataFrame,
    month_counts: pd.DataFrame,
    title_word_counts: pd.DataFrame,
) -> None:
    """Write a markdown summary to outputs/summary.md."""
    language_table_rows = "\n".join(
        f"| {language_row['language']} | {language_row['count']} |"
        for _, language_row in language_counts.head(10).iterrows()
    )
    month_table_rows = "\n".join(
        f"| {month_row['month']} | {month_row['count']} |"
        for _, month_row in month_counts.iterrows()
    )
    title_word_table_rows = "\n".join(
        f"| {word_row['word']} | {word_row['count']} |"
        for _, word_row in title_word_counts.head(15).iterrows()
    )

    summary_markdown = f"""\
# Analysis Summary: 2025 Project Gutenberg Index

## Dataset

- **Total entries parsed:** {len(entries_dataframe):,}
- **Unique languages:** {entries_dataframe['language'].nunique()}
- **Unique months:** {entries_dataframe['indexed_month'].nunique()}

## Top 10 Languages

| Language | Count |
|---|---:|
{language_table_rows}

## Monthly Distribution

| Month | Count |
|---|---:|
{month_table_rows}

## Top 15 Title Words

| Word | Count |
|---|---:|
{title_word_table_rows}


"""
    (OUTPUT_DIRECTORY / "summary.md").write_text(summary_markdown, encoding="utf-8")


# --- Main ---


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    OUTPUT_DIRECTORY.mkdir(exist_ok=True)

    print("Fetching GUTINDEX.2025 ...")
    raw_index_text = fetch_gutindex_text()
    print(f"  Downloaded {len(raw_index_text):,} characters.")

    print("Parsing entries ...")
    parsed_entries = parse_all_entries(raw_index_text)
    entries_dataframe = build_dataframe(parsed_entries)
    print(f"  Parsed {len(entries_dataframe):,} entries.")

    print_validation(entries_dataframe)

    # language distribution
    language_counts = count_languages(entries_dataframe)
    language_counts.to_csv(OUTPUT_DIRECTORY / "language_distribution.csv", index=False)
    save_language_chart(language_counts, OUTPUT_DIRECTORY / "language_distribution.png")

    # monthly distribution
    month_counts = count_by_month(entries_dataframe)
    month_counts.to_csv(OUTPUT_DIRECTORY / "month_distribution.csv", index=False)
    save_month_chart(month_counts, OUTPUT_DIRECTORY / "month_distribution.png")

    # most common non-stop-words in titles (stretch goal)
    title_word_counts = count_title_words(entries_dataframe["title"])
    title_word_counts.to_csv(OUTPUT_DIRECTORY / "title_word_distribution.csv", index=False)
    save_title_word_chart(title_word_counts, OUTPUT_DIRECTORY / "title_word_distribution.png")

    print_results(language_counts, month_counts, title_word_counts)
    write_summary(entries_dataframe, language_counts, month_counts, title_word_counts)
    print(f"All outputs saved to {OUTPUT_DIRECTORY}/")


if __name__ == "__main__":
    main()
