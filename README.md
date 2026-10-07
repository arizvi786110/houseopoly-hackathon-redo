# Houseopoly 2.0: children in temporary accommodation in London

**1 in every 18 children in London was living in temporary accommodation in March 2026.**

A rebuild of *Houseopoly*, made with Nika Hamid at the House London data sprint (Newspeak House). The original was a Monopoly-style game that never quite connected to the data. This version starts from the data: a cleaned 2019–2026 time series for every London borough, a tested forecast, and an interactive site.

**Live site:** 
houseopoly-hackathon.netlify.app

## Features
- **Draw your guess:** sketch the trend since 2019, then see the real line and a forecast with its uncertainty range.
- **Your borough:** see its "classroom" from March 2024, guess how full it is now, then watch the desks of families placed outside the borough empty out.
- **Sources:** every data source, cleaning decision and limitation, in plain English.

## Key findings
| | |
|---|---|
| Children in temporary accommodation, London (March 2026) | **101,620** (5.5 in every 100) |
| Change since the low of June 2022 | **+36.5%** |
| Highest per 100 children | Westminster 14.6, Newham 13.8, Lambeth 11.4 |
| Families in B&Bs beyond six weeks | Peak 1,880 (June 2024), now 320 |
| Forecast for March 2028, if trends continue | **about 114,000** (80% range 97,000–131,000) |

## How it works
1. **Cleaning** (`clean_ta.py`): 27 quarterly MHCLG files with changing layouts, merged headers and suppressed values (`[c]`, `[x]`, `[z]` become missing, never zero). 29 of 33 boroughs miss at least one quarter, so London-wide figures use official London totals. Checks run on every build.
2. **Validation:** [Truero](https://truero.ai) caught a division-by-zero bug my checks missed (Westminster's households published as 0 for June 2020), a duplicated row and a leakage risk.
3. **Forecasting** (`forecast.py`): four methods compared with rolling-origin backtesting, training only on data available at each point. Holt's exponential smoothing won (average error 2,201 children, vs 2,320 for a simple trend and 4,407 for "no change"). Boroughs aren't forecast individually because of reporting gaps.
4. **Website** (`site/index.html`): a single self-contained page in plain JavaScript and SVG, with the data and borough map embedded.

## Run it
```bash
pip install pandas odfpy openpyxl statsmodels matplotlib
python src/download_ta.py
# Save the ONS mid-2025 population file as data/raw/mye25tablesew.xlsx
python src/clean_ta.py "data/raw/ta_*"
python src/forecast.py
python src/child_population.py
python src/build_site.py
python src/build_site_html.py
```

## Data sources
- MHCLG, [Statutory homelessness live tables](https://www.gov.uk/government/statistical-data-sets/live-tables-on-homelessness) (TA1), 2019 Q3 to 2026 Q1
- ONS, [Population estimates](https://www.ons.gov.uk/peoplepopulationandcommunity/populationandmigration/populationestimates/datasets/estimatesofthepopulationforenglandandwales), mid-2025, children aged 0–17
- Borough boundaries simplified from [UK-GeoJSON](https://github.com/martinjc/UK-GeoJSON)

Open Government Licence v3.0.

## Lessons
Start with the question and the data, then choose the format. Next, I'd like to try multivariate forecasting: predicting from the factors that drive a trend, not just its past.

## Credits
Nika Hamid, for building the original with me, and Ellie and the Truero team, for the demo and Pro access.
