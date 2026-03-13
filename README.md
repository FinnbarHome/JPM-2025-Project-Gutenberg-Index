# Project Gutenberg 2025 Index - Exploratory Analysis

Analyses the [GUTINDEX.2025](https://www.gutenberg.org/dirs/GUTINDEX.2025) plain-text index to find:

1. Frequency distribution of languages
2. Frequency distribution of texts by month
3. Most common non-stop-words in titles (stretch goal)

## Setup

```
pip install -r requirements.txt
```

## Usage

```
python gutenberg_index_analysis.py
```

## Outputs

Creates an `outputs/` folder with:

- `language_distribution` - CSV + PNG
- `month_distribution` - CSV + PNG
- `title_word_distribution` - CSV + PNG
- `summary.md`
