"""
Clean the TA1 (temporary accommodation) sheet from the government's quarterly
homelessness files into one tidy table: one row per London borough per quarter.

    python clean_ta.py data/raw/ta_*        # any number of quarterly files, wildcards OK
    -> writes data/processed/ta_london_clean.csv

Each quarterly file holds a snapshot for the END of that quarter, so you need
one file per quarter for the time series.
"""
import glob
import os
import re
import sys

import pandas as pd

# The columns we keep, found by keywords in their headers rather than by
# position, because column order and wording change between releases.
# Each column has a list of alternatives: ALL words in one alternative must match.
COLUMNS = {
    "households_in_ta":          [["households in ta total"], ["total number of households in ta"]],
    "households_thousands":      [["households in area", "thousand"], ["households in area", "000"]],
    "households_with_children":  [["households in ta with children"]],
    "children_in_ta":            [["children in ta"]],
    "bnb_with_children":         [["b&b", "with children"], ["bed and breakfast", "with children"]],
    "bnb_children_over_6_weeks": [["b&b", "with children", "more than 6 weeks"],
                                  ["bed and breakfast", "with children", "more than 6 weeks"]],
    "ta_in_another_area":        [["ta duty in another la"], ["in ta in another local authority"]],
}
# Headers that contain our keywords but are NOT the column we want
EXCLUDE = {
    "households_in_ta":          ["per thousand", "per (000", "with children", "another"],
    "households_with_children":  ["b&b", "breakfast", "per"],
    "children_in_ta":            ["households in ta with"],
    "bnb_with_children":         ["6 weeks", "16 or 17", "16/17"],
    "bnb_children_over_6_weeks": ["pending"],
}

LONDON_REGION = "E12000007"                      # official London total row
LONDON_CODE = re.compile(r"^E09\d{6}$")          # London boroughs: E09000001-E09000033
SPECIAL = {"[c]": "confidential", "[x]": "missing", "[z]": "not applicable"}


def quarter_from_title(title):
    """
    Work out the quarter from the sheet title. Handles the styles used over the years:
      '... as at 31 March 2026 ...'        (snapshot date: March -> Q1)
      '... England, 30th September 2019'
      '... January to March 2026 ...'
    Returns None if no date is found.
    """
    t = " ".join(title.lower().split())          # also flattens line breaks
    end_months = {"march": 1, "june": 2, "september": 3, "december": 4}
    m = re.search(r"\d{1,2}(?:st|nd|rd|th)? (march|june|september|december),? (20\d\d)", t)
    if m:
        return f"{m.group(2)} Q{end_months[m.group(1)]}"
    start_months = {"january": 1, "april": 2, "july": 3, "october": 4}
    m = re.search(r"(january|april|july|october) to \w+,? (20\d\d)", t)
    if m:
        return f"{m.group(2)} Q{start_months[m.group(1)]}"
    return None


def quarter_from_filename(path):
    """Files from download_ta.py are named like ta_2019_Q3.xlsx."""
    m = re.search(r"(20\d\d)_Q([1-4])", os.path.basename(path))
    return f"{m.group(1)} Q{m.group(2)}" if m else None


def get_quarter(path, title):
    """Prefer the file name; use the title as a cross-check."""
    from_name, from_title = quarter_from_filename(path), quarter_from_title(title)
    if from_name and from_title and from_name != from_title:
        print(f"  WARNING: {os.path.basename(path)} is named {from_name} but its title says {from_title}")
    quarter = from_name or from_title
    if not quarter:
        raise ValueError(f"Couldn't work out the quarter for {path} from its name or title: {title!r}")
    return quarter


def normalise(text):
    """Lower-case, tidy spaces, fix a known typo and strip footnote numbers glued to
    words (e.g. 'TA1,2,3,4' -> 'TA', 'area5' -> 'area'), so keywords match."""
    t = " ".join(str(text).lower().split())
    t = t.replace("bedand", "bed and")
    return re.sub(r"(?<=[a-z\)])\d+(?:,\d+)*", "", t)


def build_headers(grid, first_data):
    """
    Combine up to 3 header rows above the first data row into one label per column.
    Older files put a group heading (e.g. 'Bed and breakfast hotels') in a merged
    cell above several sub-columns, so in the upper rows a heading is carried
    across to the right until the next heading. Rows with only one filled cell are
    titles or notes, not headers, and are skipped.
    """
    top = grid.iloc[max(0, first_data - 3):first_data]
    top = top[top.notna().sum(axis=1) >= 2]
    rows = list(top.itertuples(index=False))
    labels = []
    carried = [None] * len(rows)
    for col in range(grid.shape[1]):
        parts = []
        for r, row in enumerate(rows):
            v = row[col]
            if pd.notna(v) and str(v).strip():
                carried[r] = str(v).strip()
                parts.append(carried[r])
            elif r < len(rows) - 1 and carried[r]:      # carry merged headings, upper rows only
                parts.append(carried[r])
        labels.append(normalise(" ".join(parts)))
    return labels


def clean_ta1(path):
    # 1. Find the TA1 sheet (older files name it e.g. 'TA1_-_Jul_21-Sep_21' or 'TA1 ')
    #    and read it as raw text, with no header interpretation
    engine = "odf" if path.endswith(".ods") else None
    sheets = pd.ExcelFile(path, engine=engine).sheet_names
    matches = [n for n in sheets if re.match(r"^\s*ta\s*1(?!\d)", n, flags=re.IGNORECASE)]
    if not matches:
        raise ValueError(f"{path}: no TA1 sheet found. Sheets in this file: {sheets}")
    grid = pd.read_excel(path, sheet_name=matches[0], engine=engine, header=None, dtype=str)

    # 2. The quarter comes from the file name, cross-checked with the title
    quarter = get_quarter(path, str(grid.iloc[0, 0]))

    # 3. Find the column of area codes (the one with the most London codes),
    #    the first data row, and the header label for every column
    counts = grid.apply(lambda c: c.astype(str).str.strip().str.match(LONDON_CODE).sum())
    code_col = counts.idxmax()
    codes = grid[code_col].astype(str).str.strip()
    first_data = codes.str.match(r"^[EWSN]\d{8}$").idxmax()
    headers = build_headers(grid, first_data)

    # 4. Match our columns by keywords
    picked = {}
    for name, alternatives in COLUMNS.items():
        found = None
        for words in alternatives:
            for i, h in enumerate(headers):
                if all(w in h for w in words) and not any(x in h for x in EXCLUDE.get(name, [])):
                    found = i
                    break
            if found is not None:
                break
        if found is None:
            listing = "\n".join(f"    {i:3}: {h}" for i, h in enumerate(headers) if h)
            raise ValueError(f"{path}: couldn't find the '{name}' column.\n"
                             f"  Headers found in this file:\n{listing}")
        picked[name] = found

    # 5. Keep London boroughs only
    london = grid[codes.str.match(LONDON_CODE)]

    # 6. Build the tidy table. Special values ([c], [x], [z]) become missing, not zero
    out = pd.DataFrame({
        "ons_code": london[code_col].str.strip().values,
        "borough": london[code_col + 1].str.strip().str.replace("&", "and", regex=False).values,
        "quarter": quarter,
    })
    for name, i in picked.items():
        out[name] = pd.to_numeric(london[i].replace(SPECIAL.keys(), pd.NA), errors="coerce").values
    out["households"] = (out.pop("households_thousands") * 1000).round()
    # A borough can't have zero households: a 0 here is an error in the source
    # file (e.g. Westminster, 2020 Q2). Treat it as missing so the rate isn't
    # divided by zero (which would give 'infinity').
    bad = out["households"] <= 0
    if bad.any():
        print(f"  WARNING: {quarter}: households given as 0 for "
              f"{', '.join(out.loc[bad, 'borough'])}; treated as missing")
        out.loc[bad, "households"] = pd.NA
    out["ta_per_1000"] = (out["households_in_ta"] / out["households"] * 1000).round(2)

    # 7. The official London total row. Use this for London-wide figures: summing
    #    boroughs undercounts whenever some boroughs didn't report that quarter.
    region = grid[codes == LONDON_REGION]
    total = {"quarter": quarter}
    for name, i in picked.items():
        total[name] = pd.to_numeric(region[i].replace(SPECIAL.keys(), pd.NA), errors="coerce").iloc[0] \
            if len(region) else pd.NA
    total["boroughs_reporting"] = int(out["households_in_ta"].notna().sum())
    return out, {name: headers[i] for name, i in picked.items()}, total


def check(df):
    """Sanity checks. Prints problems instead of silently accepting them."""
    problems = []
    for q, g in df.groupby("quarter"):
        if len(g) != 33:
            problems.append(f"{q}: {len(g)} boroughs, expected 33")
    if df.duplicated(["ons_code", "quarter"]).any():
        problems.append("duplicate borough-quarter rows")
    bad = df[df["children_in_ta"] < df["households_with_children"]]
    if len(bad):
        problems.append(f"{len(bad)} rows with fewer children than households with children")
    if (df.select_dtypes("number") < 0).any().any():
        problems.append("negative values")
    numbers = df.select_dtypes("number").astype(float)
    if numbers.isin([float("inf"), float("-inf")]).any().any():
        problems.append("infinite values (division by zero somewhere)")
    return problems


if __name__ == "__main__":
    # Expand wildcards ourselves (PowerShell doesn't), e.g. data/raw/ta_*
    paths = sorted(p for arg in sys.argv[1:] for p in (glob.glob(arg) or [arg]))
    tables, totals = [], []
    for path in paths:
        df, used, total = clean_ta1(path)
        print(f"{os.path.basename(path)}: {df['quarter'].iloc[0]}, "
              f"{total['boroughs_reporting']} of {len(df)} boroughs reported")
        tables.append(df)
        totals.append(total)
    data = pd.concat(tables)
    # If two files cover the same quarter, the one given LAST wins (put revised files last).
    # Remove duplicates BEFORE sorting, so "last" still means "last file given".
    data = data.drop_duplicates(["ons_code", "quarter"], keep="last")
    data = data.sort_values(["ons_code", "quarter"])
    print("\nColumns used (from the last file):")
    for k, v in used.items():
        print(f"  {k:28} <- {v}")
    problems = check(data)
    print("\nChecks:", "all passed" if not problems else "; ".join(problems))
    os.makedirs("data/processed", exist_ok=True)
    data.to_csv("data/processed/ta_london_clean.csv", index=False)
    print(f"Wrote data/processed/ta_london_clean.csv ({len(data)} rows, {data['quarter'].nunique()} quarters)")

    # Official London totals, one row per quarter
    london = pd.DataFrame(totals).drop_duplicates("quarter", keep="last").sort_values("quarter")
    for col in london.columns.drop("quarter"):
        london[col] = pd.to_numeric(london[col], errors="coerce")
    london["households"] = (london.pop("households_thousands") * 1000).round()
    if london["households_in_ta"].isna().any():
        print("  WARNING: no London total row found for:",
              ", ".join(london.loc[london["households_in_ta"].isna(), "quarter"]))
    london.to_csv("data/processed/ta_london_official_total.csv", index=False)
    print(f"Wrote data/processed/ta_london_official_total.csv ({len(london)} quarters)")

    # Which boroughs are missing which quarters (for the methodology page)
    gaps = (data.assign(missing=data["households_in_ta"].isna().astype(int))
                .pivot(index="borough", columns="quarter", values="missing"))
    gaps["quarters_missing"] = gaps.sum(axis=1)
    gaps.sort_values("quarters_missing", ascending=False).to_csv("data/processed/missing_data_report.csv")
    print("Wrote data/processed/missing_data_report.csv")