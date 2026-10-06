"""
Bundle everything the website needs into one file: outputs/site_data.json

    python3 src/build_site_data.py

Reads  data/processed/ta_london_official_total.csv   (official London totals)
       data/processed/ta_london_clean.csv            (borough table)
       outputs/forecasts.json                        (from forecast.py)
       data/processed/child_population.csv           (from child_population.py, optional)
"""
import os
import json
import math

import pandas as pd

# Department for Education, Schools, pupils and their characteristics 2025/26:
# average state-funded primary class size.
CLASS_SIZE = 26.1
CLASS_SIZE_SOURCE = ("Department for Education, Schools, pupils and their characteristics "
                     "2025/26: average primary class size")


def clean(v, digits=None):
    """Make a value safe for JSON: missing or infinite -> null, numpy -> plain Python."""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return v
    if math.isnan(f) or math.isinf(f):
        return None
    if digits is None:
        return int(round(f))
    return round(f, digits)


def classrooms(children):
    return None if children is None else int(round(children / CLASS_SIZE))


official = pd.read_csv("data/processed/ta_london_official_total.csv").sort_values("quarter")
boroughs = pd.read_csv("data/processed/ta_london_clean.csv").sort_values(["borough", "quarter"])
with open("outputs/forecasts.json") as fh:
    fc = json.load(fh)

# Children aged 0-17 per borough (ONS mid-2025). Needed for "X in every 100 children".
POP_FILE = "data/processed/child_population.csv"
pop = pd.read_csv(POP_FILE).set_index("ons_code")["children_0_17"] if os.path.exists(POP_FILE) else None
if pop is None:
    print("  NOTE: no child population file, so 'per 100 children' figures are left out")


def per_100(children, code):
    """Children in temporary accommodation per 100 children living in the area."""
    if pop is None or children is None or code not in pop.index or not pop[code]:
        return None
    return round(children / pop[code] * 100, 2)

latest_q = official["quarter"].iloc[-1]
latest = official.iloc[-1]
low_i = official["children_in_ta"].idxmin()
bnb_peak_i = official["bnb_children_over_6_weeks"].idxmax()

# ---------------------------------------------------------------- headline
headline = {
    "quarter": latest_q,
    "children_in_ta": clean(latest["children_in_ta"]),
    "households_in_ta": clean(latest["households_in_ta"]),
    "households_with_children": clean(latest["households_with_children"]),
    "classrooms": classrooms(latest["children_in_ta"]),
    "low_quarter": official.loc[low_i, "quarter"],
    "low_children": clean(official.loc[low_i, "children_in_ta"]),
    "change_since_low_pct": clean((latest["children_in_ta"] / official.loc[low_i, "children_in_ta"] - 1) * 100, 1),
    "forecast_end_quarter": fc["forecast"][-1]["quarter"],
    "forecast_end_children": fc["forecast"][-1]["forecast"],
    "forecast_end_low_80": fc["forecast"][-1]["low_80"],
    "forecast_end_high_80": fc["forecast"][-1]["high_80"],
    "forecast_end_classrooms": classrooms(fc["forecast"][-1]["forecast"]),
    "london_children_0_17": clean(pop["E12000007"]) if pop is not None and "E12000007" in pop.index else None,
    "per_100_children": per_100(clean(latest["children_in_ta"]), "E12000007"),
}

# ---------------------------------------------------------------- London over time
london_series = [{
    "quarter": r.quarter,
    "children_in_ta": clean(r.children_in_ta),
    "households_in_ta": clean(r.households_in_ta),
    "households_with_children": clean(r.households_with_children),
    "bnb_children_over_6_weeks": clean(r.bnb_children_over_6_weeks),
    "classrooms": classrooms(clean(r.children_in_ta)),
} for r in official.itertuples()]

forecast = [{**f, "classrooms": classrooms(f["forecast"])} for f in fc["forecast"]]

bnb = {
    "peak_quarter": official.loc[bnb_peak_i, "quarter"],
    "peak_families": clean(official.loc[bnb_peak_i, "bnb_children_over_6_weeks"]),
    "latest_families": clean(latest["bnb_children_over_6_weeks"]),
}

# ---------------------------------------------------------------- boroughs
latest_b = boroughs[boroughs["quarter"] == latest_q]
borough_list = []
for r in latest_b.itertuples():
    hist = boroughs[boroughs["ons_code"] == r.ons_code]
    borough_list.append({
        "ons_code": r.ons_code,
        "borough": r.borough,
        "children_in_ta": clean(r.children_in_ta),
        "households_in_ta": clean(r.households_in_ta),
        "households": clean(r.households),
        "ta_per_1000_households": clean(r.ta_per_1000, 2),
        "children_per_1000_households": clean(r.children_in_ta / r.households * 1000, 2) if r.households else None,
        "classrooms": classrooms(clean(r.children_in_ta)),
        "bnb_children_over_6_weeks": clean(r.bnb_children_over_6_weeks),
        "placed_in_another_area": clean(r.ta_in_another_area),
        "pct_households_placed_elsewhere": clean(r.ta_in_another_area / r.households_in_ta * 100, 1)
            if r.households_in_ta else None,
        "children_0_17": clean(pop[r.ons_code]) if pop is not None and r.ons_code in pop.index else None,
        "per_100_children": per_100(clean(r.children_in_ta), r.ons_code),
        "quarters_missing": int(hist["households_in_ta"].isna().sum()),
        "history": [{"quarter": h.quarter, "children_in_ta": clean(h.children_in_ta)} for h in hist.itertuples()],
    })
borough_list.sort(key=lambda b: (b["children_per_1000_households"] is None, -(b["children_per_1000_households"] or 0)))

# ---------------------------------------------------------------- methodology
site = {
    "headline": headline,
    "london_series": london_series,
    "forecast": forecast,
    "forecast_model": {
        "model": "Holt's exponential smoothing" if fc["model"] == "holt" else fc["model"],
        "trained_on": fc["trained_on"],
        "backtest_mae_overall": fc["backtest_mae_overall"],
        "backtest_mae_by_quarters_ahead": fc["backtest_mae_by_quarters_ahead"],
        "baselines_mae_overall": fc["baselines_mae_overall"],
        "note": fc["note"],
    },
    "bnb_over_6_weeks": bnb,
    "boroughs_latest": borough_list,
    "data_quality": {
        "borough_quarters_total": int(len(boroughs)),
        "borough_quarters_missing": int(boroughs["households_in_ta"].isna().sum()),
        "boroughs_with_any_gap": int((boroughs.groupby("borough")["households_in_ta"].apply(lambda s: s.isna().any())).sum()),
        "boroughs_reporting_latest": int(latest_b["households_in_ta"].notna().sum()),
    },
    "sources": {
        "temporary_accommodation": "MHCLG, Statutory homelessness detailed local authority tables (TA1), 2019 Q3 to 2026 Q1",
        "class_size": CLASS_SIZE_SOURCE,
        "class_size_value": CLASS_SIZE,
        "licence": "Open Government Licence v3.0",
        "child_population": "ONS, Population estimates for England and Wales, mid-2025 (children aged 0-17)"
            if pop is not None else None,
    },
}

with open("outputs/site_data.json", "w") as fh:
    json.dump(site, fh, indent=2)

h = headline
print(f"Wrote outputs/site_data.json")
print(f"  {h['quarter']}: {h['children_in_ta']:,} children in TA = about {h['classrooms']:,} primary classrooms")
print(f"  Forecast {h['forecast_end_quarter']}: {h['forecast_end_children']:,} = about {h['forecast_end_classrooms']:,} classrooms")
print(f"  Boroughs in latest quarter: {len(borough_list)}; top by children per 1,000 households: "
      f"{', '.join(b['borough'] for b in borough_list[:3])}")
if pop is not None:
    print(f"  London: {h['per_100_children']} in every 100 children are in temporary accommodation")
    top = sorted([b for b in borough_list if b["per_100_children"]], key=lambda b: -b["per_100_children"])[:3]
    print("  Highest per 100 children:", ", ".join(f"{b['borough']} ({b['per_100_children']})" for b in top))