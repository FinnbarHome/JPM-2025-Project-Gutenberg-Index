# Project Gutenberg 2025 Index — Exploratory Analysis

Analyses the [GUTINDEX.2025](https://www.gutenberg.org/dirs/GUTINDEX.2025)
plain-text index to determine:

1. Frequency distribution of languages of indexed texts
2. Frequency distribution of texts indexed by month
3. Most common non-stop-words in titles (stretch goal)

## Files

| File | Purpose |
|---|---|
| `q4_analysis.py` | Main script — run this |
| `parser_helpers.py` | Parsing logic for the GUTINDEX format |
| `requirements.txt` | Python dependencies |
| `outputs/` | Generated charts, CSVs, and summary (created on first run) |

## Setup

```
pip install -r requirements.txt
```

## Usage

```
python q4_analysis.py
```

## Outputs

Running the script creates an `outputs/` directory containing:

- `language_distribution.csv` and `.png`
- `month_distribution.csv` and `.png`
- `title_word_distribution.csv` and `.png`
- `summary.md` — a Markdown summary of key findings

## Assumptions and Limitations

- Entries without an explicit `[Language: ...]` tag are assumed to be English,
  as stated in the file header.
- The indexed month for each entry is taken from the
  `~ ~ ~ ~ Posting Dates ...` section header, not from the entry itself.
- Title text is separated from the author name by the last `, by ` on the
  title line(s). Entries without `, by ` retain the full line as the title.
- The file is continuously updated and may include entries from early 2026
  despite being named GUTINDEX.2025.
- The stop-word list is English-only; common non-English function words are
  not filtered from the title word analysis.
- No stemming or lemmatisation is applied.
