# 1) End2 End 
Great question. Think of it as a **pipeline** that gradually transforms messy text into structured rows.

## End-to-end flow

1. `fetch_gutindex_text()`  
   downloads one huge raw text file from Gutenberg.

2. `parse_all_entries(raw_text)`  
   breaks that big text into month sections, then entry blocks, then parses each block into a `GutenbergEntry` object.

3. `build_dataframe(entries)`  
   converts the list of `GutenbergEntry` objects into a pandas DataFrame (table).

---

## Method-by-method input/output (`parser_helpers.py`)

### Data acquisition

- `fetch_gutindex_text(url: str = GUTINDEX_URL) -> str`
  - **Input:** optional URL string.
  - **Output:** full raw index text (`str`), decoded as UTF-8.

---

### Splitting raw text

- `_extract_listings(raw_index_text: str) -> str`
  - **Input:** entire downloaded file text.
  - **Output:** only the listings portion (everything after `"<===LISTINGS===>"`).

- `_split_by_month(listings_text: str) -> list[tuple[str, str]]`
  - **Input:** listings text.
  - **Output:** list of pairs like:
    - `("Mar 2026", "<all lines for that month>")`
  - So each item is `(month_label, section_text)`.

- `_split_into_entries(section_text: str) -> list[str]`
  - **Input:** one month’s text section.
  - **Output:** list of candidate entry blocks (`list[str]`), each block is one potential book record.
  - Filters out headers/notes and keeps blocks whose first line ends with an ebook number.

---

### Field extraction (from one entry block)

- `extract_ebook_number(entry_text: str) -> int | None`
  - **Input:** one entry block string.
  - **Output:** ebook number as `int`, or `None` if not found.

- `_extract_title_author_text(entry_text: str) -> str`
  - **Input:** one entry block.
  - **Output:** cleaned combined title+author string (still one string).

- `extract_title_and_author(entry_text: str) -> tuple[str, str]`
  - **Input:** one entry block.
  - **Output:** `(title, author)` tuple.
  - Splits on the last `", by "`; if no match, author is empty string.

- `extract_language(entry_text: str) -> str`
  - **Input:** one entry block.
  - **Output:** language string from `[Language: ...]`, else defaults to `"English"`.

---

### Parsing records

- `parse_entry(entry_text: str, month_label: str) -> GutenbergEntry | None`
  - **Input:** one entry block + month label.
  - **Output:** `GutenbergEntry` dataclass (structured object), or `None` if unparseable.

- `parse_all_entries(raw_index_text: str) -> list[GutenbergEntry]`
  - **Input:** full raw text from download.
  - **Output:** list of parsed `GutenbergEntry` objects.

---

### DataFrame construction

- `build_dataframe(entries: list[GutenbergEntry]) -> pd.DataFrame`
  - **Input:** list of parsed entry objects.
  - **Output:** DataFrame with columns:
    - `ebook_number`, `title`, `author`, `language`, `indexed_month`
  - `raw_text` is intentionally excluded.

---

## Data types as it flows

- Start: `str` (big raw file)
- Mid: `list[(month_label, section_text)]`
- Mid: `list[str]` (entry blocks)
- Mid: `GutenbergEntry` objects
- End: `pd.DataFrame` (table)

---

## Mental model of the DataFrame step

`build_dataframe` does this conceptually:

- For each `GutenbergEntry`, create a dictionary:
  - `{"ebook_number": ..., "title": ..., ...}`
- Collect all dicts into a list (`entry_records`)
- `pd.DataFrame(entry_records)` turns that list into rows/columns.

If you want, I can also diagram this as a small “function call graph” so you can visualize exactly which function calls which.









# 2 Examples

Absolutely — here’s the same pipeline, but now with **concrete example inputs and outputs** for each step.

## End-to-end flow with a real-ish mini sample

Assume Gutenberg raw text contains (simplified):

```text
... preamble ...
<===LISTINGS===>

~ ~ ~ ~ Posting Dates for Mar 2026 ~ ~ ~ ~

Jubilee Hall, by Mrs. (Louisa Lilias) Greene  78214
[Language: English]

Aimée, by Jacques Rivière  78207
[Language: French]

TITLE and AUTHOR
****
```

---

## Method-by-method with example I/O

### `fetch_gutindex_text(url=...) -> str`
- **Example input:**  
  `"https://www.gutenberg.org/dirs/GUTINDEX.2025"`
- **Example output (string):**  
  Full file text (entire document), e.g. starts with preamble then `<===LISTINGS===> ...`
- **Why:** network download + decode only (no parsing yet)

---

### `_extract_listings(raw_index_text: str) -> str`
- **Example input:**  
  Full raw text containing preamble + marker + listings
- **Example output:**  
  Only text after marker:
  ```text
  ~ ~ ~ ~ Posting Dates for Mar 2026 ~ ~ ~ ~

  Jubilee Hall, by Mrs. (Louisa Lilias) Greene  78214
  [Language: English]

  Aimée, by Jacques Rivière  78207
  [Language: French]
  ...
  ```

---

### `_split_by_month(listings_text: str) -> list[tuple[str, str]]`
- **Example input:**  
  Listings text with one or more month header sections
- **Example output:**  
  ```python
  [
    (
      "Mar 2026",
      "Jubilee Hall, by Mrs. (Louisa Lilias) Greene  78214\n[Language: English]\n\n"
      "Aimée, by Jacques Rivière  78207\n[Language: French]\n\nTITLE and AUTHOR\n****"
    )
  ]
  ```

---

### `_split_into_entries(section_text: str) -> list[str]`
- **Example input (`section_text` for `Mar 2026`):**
  ```text
  Jubilee Hall, by Mrs. (Louisa Lilias) Greene  78214
  [Language: English]

  Aimée, by Jacques Rivière  78207
  [Language: French]

  TITLE and AUTHOR
  ****
  ```
- **Example output:**
  ```python
  [
    "Jubilee Hall, by Mrs. (Louisa Lilias) Greene  78214\n[Language: English]",
    "Aimée, by Jacques Rivière  78207\n[Language: French]"
  ]
  ```
- Header/note blocks are filtered out.

---

### `extract_ebook_number(entry_text: str) -> int | None`
- **Example input:**
  ```text
  Jubilee Hall, by Mrs. (Louisa Lilias) Greene  78214
  [Language: English]
  ```
- **Example output:**  
  `78214`

---

### `_extract_title_author_text(entry_text: str) -> str`
- **Example input:**
  ```text
  Jubilee Hall, by Mrs. (Louisa Lilias) Greene  78214
  [Language: English]
  ```
- **Example output:**  
  `"Jubilee Hall, by Mrs. (Louisa Lilias) Greene"`
- (ebook number stripped, metadata line excluded)

---

### `extract_title_and_author(entry_text: str) -> tuple[str, str]`
- **Example input:** same entry block
- **Example output:**  
  `("Jubilee Hall", "Mrs. (Louisa Lilias) Greene")`

---

### `extract_language(entry_text: str) -> str`
- **Example input:**
  ```text
  Aimée, by Jacques Rivière  78207
  [Language: French]
  ```
- **Example output:**  
  `"French"`
- If `[Language: ...]` missing, output would be default `"English"`.

---

### `parse_entry(entry_text: str, month_label: str) -> GutenbergEntry | None`
- **Example input:**
  - `entry_text` = `"Aimée, by Jacques Rivière  78207\n[Language: French]"`
  - `month_label` = `"Mar 2026"`
- **Example output:**
  ```python
  GutenbergEntry(
      ebook_number=78207,
      title="Aimée",
      author="Jacques Rivière",
      language="French",
      indexed_month="Mar 2026",
      raw_text="Aimée, by Jacques Rivière  78207\n[Language: French]"
  )
  ```

---

### `parse_all_entries(raw_index_text: str) -> list[GutenbergEntry]`
- **Example input:** full downloaded raw text
- **Example output:**
  ```python
  [
    GutenbergEntry(ebook_number=78214, title="Jubilee Hall", author="Mrs. (Louisa Lilias) Greene", language="English", indexed_month="Mar 2026", raw_text="..."),
    GutenbergEntry(ebook_number=78207, title="Aimée", author="Jacques Rivière", language="French", indexed_month="Mar 2026", raw_text="...")
  ]
  ```

---

### `build_dataframe(entries: list[GutenbergEntry]) -> pd.DataFrame`
- **Example input:** list of `GutenbergEntry` objects above
- **Internal transformed records:**
  ```python
  [
    {
      "ebook_number": 78214,
      "title": "Jubilee Hall",
      "author": "Mrs. (Louisa Lilias) Greene",
      "language": "English",
      "indexed_month": "Mar 2026",
    },
    {
      "ebook_number": 78207,
      "title": "Aimée",
      "author": "Jacques Rivière",
      "language": "French",
      "indexed_month": "Mar 2026",
    }
  ]
  ```
- **Example output DataFrame:**

| ebook_number | title        | author                         | language | indexed_month |
|---:|---|---|---|---|
| 78214 | Jubilee Hall | Mrs. (Louisa Lilias) Greene | English | Mar 2026 |
| 78207 | Aimée        | Jacques Rivière              | French  | Mar 2026 |

---

## Type flow (with concrete shapes)

- `str` (huge file)  
-> `str` (listings only)  
-> `list[tuple[str, str]]` (month label + month text)  
-> `list[str]` (entry blocks)  
-> `GutenbergEntry` objects  
-> `list[GutenbergEntry]`  
-> `pd.DataFrame`

If you want, I can next do this as a **call graph diagram** (`fetch -> parse_all -> ...`) plus exactly where each regex is applied.

# Quick easy Breakdown
