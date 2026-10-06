"""
Number of children (aged 0-17) in each London borough, from the ONS mid-year
population estimates.

    python3 src/child_population.py

Reads  data/raw/mye25tablesew.xlsx    (ONS "Mid-2025: 2023 local authority boundaries")
Writes data/processed/child_population.csv

The ONS workbook has one sheet per table. The one we want has persons (not
males/females separately) by single year of age, with a row per area and
columns for each age 0, 1, 2 ... 90. Like the cleaning script, this finds the
sheet and columns by their labels rather than fixed positions.
"""
import os
import re
import sys

import pandas as pd

SOURCE = "data/raw/mye25tablesew.xlsx"
OUT = "data/processed/child_population.csv"
LONDON_CODE = re.compile(r"^E09\d{6}$")
LONDON_REGION = "E12000007"


def find_table(path):
    """Return (sheet name, grid, header row index) for the persons-by-age table."""
    sheets = pd.ExcelFile(path).sheet_names
    # Prefer a sheet named like 'MYE2 - Persons'; otherwise try every sheet
    preferred = [s for s in sheets if re.search(r"mye\s*2", s, re.I) and re.search(r"person", s, re.I)]
    for name in preferred + [s for s in sheets if s not in preferred]:
        grid = pd.read_excel(path, sheet_name=name, header=None, dtype=str)
        for i in range(min(30, len(grid))):
            cells = [str(v).strip().lower() for v in grid.iloc[i] if pd.notna(v)]
            if "code" in cells and any(c in ("all ages", "all_ages") for c in cells) and "0" in cells:
                return name, grid, i
    raise ValueError(f"Couldn't find a persons-by-single-year-of-age table in {path}. Sheets: {sheets}")


def main():
    if not os.path.exists(SOURCE):
        sys.exit(f"Missing {SOURCE}. Download the ONS mid-2025 file and save it there.")
    name, grid, h = find_table(SOURCE)
    headers = [str(v).strip().lower() for v in grid.iloc[h]]
    code_col = headers.index("code")
    name_col = headers.index("name") if "name" in headers else code_col + 1
    # Age columns: headers that are whole numbers 0-17 (ages 18+ are ignored)
    age_cols = [i for i, v in enumerate(headers) if re.fullmatch(r"\d+(\.0)?", v) and int(float(v)) <= 17]
    ages_found = sorted(int(float(headers[i])) for i in age_cols)
    if ages_found != list(range(18)):
        raise ValueError(f"Expected age columns 0-17 in sheet '{name}', found {ages_found}")

    rows = grid.iloc[h + 1:]
    codes = rows[code_col].astype(str).str.strip()
    keep = rows[codes.str.match(LONDON_CODE) | (codes == LONDON_REGION)]
    values = keep[age_cols].apply(pd.to_numeric, errors="coerce")
    out = pd.DataFrame({
        "ons_code": keep[code_col].str.strip().values,
        "area": keep[name_col].str.strip().values,
        "children_0_17": values.sum(axis=1, min_count=18).values,
    })
    out = out.drop_duplicates("ons_code")

    boroughs = out[out["ons_code"] != LONDON_REGION]
    london = out[out["ons_code"] == LONDON_REGION]
    if len(boroughs) != 33:
        raise ValueError(f"Expected 33 London boroughs, found {len(boroughs)}")
    if boroughs["children_0_17"].isna().any():
        raise ValueError("Some boroughs have missing age values")
    if len(london):
        diff = abs(boroughs["children_0_17"].sum() - london["children_0_17"].iloc[0])
        status = "matches" if diff < 50 else f"differs by {diff:,.0f} (check!)"
        print(f"Borough total {boroughs['children_0_17'].sum():,.0f} vs London row "
              f"{london['children_0_17'].iloc[0]:,.0f}: {status}")

    os.makedirs("data/processed", exist_ok=True)
    out.to_csv(OUT, index=False)
    print(f"Sheet used: '{name}'. Wrote {OUT} ({len(boroughs)} boroughs"
          f"{' + London total' if len(london) else ''})")
    top = boroughs.sort_values("children_0_17", ascending=False).head(3)
    print("Most children:", ", ".join(f"{a} ({c:,.0f})" for a, c in zip(top.area, top.children_0_17)))


if __name__ == "__main__":
    main()