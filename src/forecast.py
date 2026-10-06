"""
Forecast children in temporary accommodation in London.

    python3 src/forecast.py

Reads  data/processed/ta_london_official_total.csv   (official London totals)
Writes outputs/backtest_results.csv                  (how accurate each model was)
       outputs/forecasts.json                        (what the website reads)
       outputs/charts/forecast_children.png          (chart for the post)

The steps, in order:
  1. Load the series
  2. Define candidate models (2 baselines + 2 exponential smoothing models)
  3. Backtest: test every model on the past, using only data it would have had
  4. Pick the most accurate model
  5. Refit it on all the data and forecast 8 quarters ahead, with a range
  6. Save everything
"""
import json
import os
import warnings

import numpy as np
import pandas as pd
from statsmodels.tsa.exponential_smoothing.ets import ETSModel

warnings.filterwarnings("ignore")          # statsmodels prints optimiser chatter

TARGET = "children_in_ta"
HORIZON = 8                                # forecast 8 quarters = 2 years ahead
MAX_BACKTEST_H = 4                         # test forecasts up to 4 quarters ahead
FIRST_ORIGIN = "2023 Q2"                   # earliest point we pretend to stand at


# ---------------------------------------------------------------- 1. load

def load():
    df = pd.read_csv("data/processed/ta_london_official_total.csv")
    df = df.sort_values("quarter").reset_index(drop=True)
    if df[TARGET].isna().any():
        raise ValueError("The official London series has gaps; fix the data first.")
    return df["quarter"].tolist(), df[TARGET].astype(float).to_numpy()


def next_quarters(last, k):
    """'2026 Q1' -> ['2026 Q2', '2026 Q3', ...]"""
    year, q = int(last[:4]), int(last[-1])
    out = []
    for _ in range(k):
        q += 1
        if q == 5:
            year, q = year + 1, 1
        out.append(f"{year} Q{q}")
    return out


# ---------------------------------------------------------------- 2. models
# Every model takes the training data (only the past) and a number of steps h,
# and returns h forecasts. Keeping them the same shape means we can test them
# all in exactly the same way.

def naive(train, h):
    """Baseline 1: next quarters = the last value. 'Nothing changes.'"""
    return np.repeat(train[-1], h)


def drift_recent(train, h):
    """Baseline 2: carry on the average change of the last 8 quarters (2 years)."""
    step = (train[-1] - train[-9]) / 8
    return train[-1] + step * np.arange(1, h + 1)


def holt(train, h):
    """Exponential smoothing with a trend (Holt's method). It tracks a level and
    a trend, updating both each quarter, with recent quarters weighted more."""
    fit = ETSModel(train, error="add", trend="add").fit(disp=False)
    return fit.forecast(h)


def holt_damped(train, h):
    """Holt's method, but the trend gradually flattens out further ahead."""
    fit = ETSModel(train, error="add", trend="add", damped_trend=True).fit(disp=False)
    return fit.forecast(h)


MODELS = {"naive": naive, "drift_recent": drift_recent, "holt": holt, "holt_damped": holt_damped}


# ---------------------------------------------------------------- 3. backtest

def backtest(quarters, y):
    """
    Rolling-origin evaluation. We stand at several points in the past
    (2023 Q2, 2023 Q3, ... ), train each model using ONLY data up to that point,
    forecast up to 4 quarters ahead, and compare with what actually happened.
    Using only past data at each point is what prevents leakage.
    """
    rows = []
    first = quarters.index(FIRST_ORIGIN) + 1
    for cut in range(first, len(y)):                      # train on y[:cut]
        h = min(MAX_BACKTEST_H, len(y) - cut)
        for name, model in MODELS.items():
            pred = model(y[:cut], h)
            for step in range(h):
                actual = y[cut + step]
                rows.append({"model": name, "trained_up_to": quarters[cut - 1],
                             "forecast_for": quarters[cut + step], "quarters_ahead": step + 1,
                             "forecast": round(float(pred[step])), "actual": int(actual),
                             "abs_error": round(abs(float(pred[step]) - actual))})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- 5. forecast

def final_forecast(name, quarters, y, errors):
    """Refit the chosen model on ALL data and forecast HORIZON quarters ahead."""
    future = next_quarters(quarters[-1], HORIZON)
    if name in ("holt", "holt_damped"):
        series = pd.Series(y)          # get_prediction needs a pandas Series, not a plain array
        fit = ETSModel(series, error="add", trend="add", damped_trend=(name == "holt_damped")).fit(disp=False)
        pred = fit.get_prediction(start=len(y), end=len(y) + HORIZON - 1)
        f80, f95 = pred.summary_frame(alpha=0.20), pred.summary_frame(alpha=0.05)
        mean = f80["mean"].to_numpy()
        lo80, hi80 = f80["pi_lower"].to_numpy(), f80["pi_upper"].to_numpy()
        lo95, hi95 = f95["pi_lower"].to_numpy(), f95["pi_upper"].to_numpy()
    else:
        # Baselines: build the range from how wrong they were in the backtest,
        # growing with the square root of how far ahead we look.
        mean = MODELS[name](y, HORIZON)
        mae1 = errors.query("model == @name and quarters_ahead == 1")["abs_error"].mean()
        spread = mae1 * np.sqrt(np.arange(1, HORIZON + 1))
        lo80, hi80 = mean - 1.6 * spread, mean + 1.6 * spread
        lo95, hi95 = mean - 2.5 * spread, mean + 2.5 * spread
    return [{"quarter": q, "forecast": round(float(m)),
             "low_80": round(float(a)), "high_80": round(float(b)),
             "low_95": round(float(c)), "high_95": round(float(d))}
            for q, m, a, b, c, d in zip(future, mean, lo80, hi80, lo95, hi95)]


# ---------------------------------------------------------------- chart

def chart(quarters, y, forecast, best, mae, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ink, accent, band = "#2C3A47", "#B4452F", "#86A898"
    n, fq = len(y), [f["quarter"] for f in forecast]
    xs_f = list(range(n - 1, n + len(forecast)))           # forecast starts from the last real point
    mean = [y[-1]] + [f["forecast"] for f in forecast]
    lo80 = [y[-1]] + [f["low_80"] for f in forecast]; hi80 = [y[-1]] + [f["high_80"] for f in forecast]
    lo95 = [y[-1]] + [f["low_95"] for f in forecast]; hi95 = [y[-1]] + [f["high_95"] for f in forecast]
    fig, ax = plt.subplots(figsize=(10, 5.4))
    ax.fill_between(xs_f, lo95, hi95, color=band, alpha=0.18, lw=0, label="95% range")
    ax.fill_between(xs_f, lo80, hi80, color=band, alpha=0.35, lw=0, label="80% range")
    ax.plot(range(n), y, color=ink, lw=2.6, label="Actual (official London total)")
    ax.plot(xs_f, mean, color=accent, lw=2.4, ls="--", label="Forecast if current trends continue")
    ax.annotate(f"{forecast[-1]['forecast']:,}\n({fq[-1]})", (xs_f[-1], mean[-1]), xytext=(-70, 12),
                textcoords="offset points", color=accent, fontsize=10, fontweight="bold")
    labels = quarters + fq
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels([l[:4] if l.endswith("Q1") else "" for l in labels])
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.grid(axis="y", color="#E3E7E2"); ax.set_axisbelow(True)
    ax.set_title("Children in temporary accommodation in London: where it's heading", loc="left",
                 fontsize=15, fontweight="bold", color=ink, pad=22)
    ax.text(0, 1.02, f"Model: {"Holt's" if best == "holt" else best}, tested on past data (average error about {mae:,} children). "
            "Source: MHCLG TA1.", transform=ax.transAxes, fontsize=9, color="#66737D")
    ax.legend(frameon=False, loc="upper left", fontsize=9)
    plt.tight_layout(); plt.savefig(path, dpi=180); plt.close()


# ---------------------------------------------------------------- run

if __name__ == "__main__":
    quarters, y = load()
    print(f"1. Loaded {len(y)} quarters of {TARGET}: {quarters[0]} to {quarters[-1]}")

    errors = backtest(quarters, y)
    summary = (errors.groupby(["model", "quarters_ahead"])["abs_error"].mean()
                     .unstack().round(0))
    summary["overall_mae"] = errors.groupby("model")["abs_error"].mean().round(0)
    summary = summary.sort_values("overall_mae")
    print("\n3. Backtest: average error in children (MAE), by quarters ahead")
    print(summary.to_string())

    best = summary.index[0]
    print(f"\n4. Most accurate model: {best} "
          f"(off by about {int(summary.loc[best, 'overall_mae']):,} children on average)")

    forecast = final_forecast(best, quarters, y, errors)
    print(f"\n5. Forecast with {best} (80% range):")
    for f in forecast:
        print(f"   {f['quarter']}: {f['forecast']:>7,}   ({f['low_80']:,} to {f['high_80']:,})")

    os.makedirs("outputs/charts", exist_ok=True)
    errors.to_csv("outputs/backtest_results.csv", index=False)
    out = {
        "target": TARGET,
        "model": best,
        "trained_on": f"{quarters[0]} to {quarters[-1]}",
        "backtest_mae_by_quarters_ahead": {str(k): int(v) for k, v in summary.loc[best].drop("overall_mae").items()},
        "backtest_mae_overall": int(summary.loc[best, "overall_mae"]),
        "baselines_mae_overall": {m: int(summary.loc[m, "overall_mae"]) for m in summary.index if m != best},
        "history": [{"quarter": q, "value": int(v)} for q, v in zip(quarters, y)],
        "forecast": forecast,
        "note": "If current trends continue. Ranges show 80% and 95% prediction intervals.",
    }
    with open("outputs/forecasts.json", "w") as fh:
        json.dump(out, fh, indent=2)
    chart(quarters, y, forecast, best, int(summary.loc[best, "overall_mae"]),
          "outputs/charts/forecast_children.png")
    print("\n6. Wrote outputs/backtest_results.csv, outputs/forecasts.json and outputs/charts/forecast_children.png")