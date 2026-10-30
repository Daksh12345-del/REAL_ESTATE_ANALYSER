"""Price forecasting from the RBI House Price Index, plus scenario projections from NHB prices.

Honest by design: the RBI series has only ~16 usable quarters per city, so we
  1. fit four simple models on log(HPI),
  2. backtest each one (rolling origin, 1-4 quarters ahead),
  3. use the model with the lowest backtest error, and show ALL model errors in the API,
  4. build the confidence band from that model's own backtest errors (widens with sqrt(horizon)).
A "no change" baseline is included so you can see whether a model beats doing nothing.
"""
import warnings

import numpy as np
import pandas as pd

MIN_TRAIN = 10          # quarters needed before the first backtest origin
MAX_H = 4               # backtest horizon (quarters)
Z = {"80": 1.2816, "95": 1.96}
MAX_ANNUAL_MOVE = 0.25  # forecasts are capped to +/-25% per year and flagged if capped


# ---------------------------------------------------------------- models (all work on log values)
def _naive(y, h):
    return np.repeat(y[-1], h)


def _drift(y, h):
    slope = np.mean(np.diff(y))
    return y[-1] + slope * np.arange(1, h + 1)


def _linear_trend(y, h, window=8):
    yy = y[-window:]
    x = np.arange(len(yy))
    b, a = np.polyfit(x, yy, 1)
    return a + b * np.arange(len(yy), len(yy) + h)


def _damped_holt(y, h):
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fit = ExponentialSmoothing(y, trend="add", damped_trend=True, initialization_method="estimated").fit()
        return np.asarray(fit.forecast(h))


MODELS = {
    "naive_no_change": _naive,       # baseline
    "drift": _drift,                 # random walk with average historical drift
    "linear_trend_8q": _linear_trend,
    "damped_holt": _damped_holt,
}
DESCRIPTIONS = {
    "naive_no_change": "Baseline: next quarters equal the last observed value",
    "drift": "Continues the average historical quarterly change",
    "linear_trend_8q": "Straight-line trend fitted on the last 8 quarters",
    "damped_holt": "Exponential smoothing with a damped trend (trend fades over time)",
}


def _safe_predict(name, y, h):
    try:
        return MODELS[name](y, h)
    except Exception:
        return _naive(y, h)


# ---------------------------------------------------------------- backtest
def backtest(y_log: np.ndarray) -> dict:
    """Rolling-origin backtest. Returns per-model MAE (index points), MAPE % and log errors at h=1."""
    n = len(y_log)
    res = {m: {"abs": [], "pct": [], "err_h1": []} for m in MODELS}
    for t in range(MIN_TRAIN, n):
        h = min(MAX_H, n - t)
        for m in MODELS:
            pred = _safe_predict(m, y_log[:t], h)
            for k in range(h):
                actual, fc = np.exp(y_log[t + k]), np.exp(pred[k])
                res[m]["abs"].append(abs(actual - fc))
                res[m]["pct"].append(abs(actual - fc) / actual * 100)
            res[m]["err_h1"].append(y_log[t] - pred[0])
    return res


def _label(qe: pd.Timestamp) -> str:
    q = {6: 1, 9: 2, 12: 3, 3: 4}[qe.month]
    fy = qe.year if qe.month >= 4 else qe.year - 1
    return f"Q{q}.{fy}-{str(fy + 1)[-2:]}"


# ---------------------------------------------------------------- public: HPI forecast
def forecast_city(hpi: pd.DataFrame, city: str, quarters: int = 4) -> dict | None:
    g = hpi[hpi["city"] == city].sort_values("quarter_end")
    if g.empty:
        return None
    actual = g[~g["provisional"]]
    prov = g[g["provisional"]]
    if len(actual) < MIN_TRAIN + 2:
        return {"available": False, "reason": f"Only {len(actual)} usable quarters; need {MIN_TRAIN + 2}."}

    y = np.log(actual["hpi"].to_numpy(dtype=float))
    bt = backtest(y)
    table = []
    for m, r in bt.items():
        table.append({"model": m, "description": DESCRIPTIONS[m], "mae_index_points": round(float(np.mean(r["abs"])), 2),
                      "mape_pct": round(float(np.mean(r["pct"])), 2), "backtest_points": len(r["abs"])})
    table.sort(key=lambda r: r["mae_index_points"])
    best = table[0]["model"]
    baseline = next(t for t in table if t["model"] == "naive_no_change")
    beats_baseline = best != "naive_no_change"

    sigma1 = float(np.sqrt(np.mean(np.square(bt[best]["err_h1"]))))
    sigma1 = max(sigma1, 0.005)

    raw = _safe_predict(best, y, quarters)
    capped = False
    limit = np.log(1 + MAX_ANNUAL_MOVE) / 4  # per quarter
    for k in range(quarters):
        lo, hi = y[-1] - limit * (k + 1), y[-1] + limit * (k + 1)
        if raw[k] < lo or raw[k] > hi:
            raw[k], capped = float(np.clip(raw[k], lo, hi)), True

    last_qe = actual["quarter_end"].iloc[-1]
    points = []
    for k in range(quarters):
        qe = last_qe + pd.offsets.QuarterEnd(k + 1)
        sd = sigma1 * np.sqrt(k + 1)
        mid = raw[k]
        points.append({
            "quarter": _label(qe), "quarter_end": qe, "forecast": float(np.exp(mid)),
            "lower_80": float(np.exp(mid - Z["80"] * sd)), "upper_80": float(np.exp(mid + Z["80"] * sd)),
            "lower_95": float(np.exp(mid - Z["95"] * sd)), "upper_95": float(np.exp(mid + Z["95"] * sd))})

    best_mape = table[0]["mape_pct"]
    if beats_baseline and best_mape < 3:
        reliability = "medium"
    elif best_mape < 6:
        reliability = "low"
    else:
        reliability = "very_low"
    last_val = float(actual["hpi"].iloc[-1])
    end_val = points[-1]["forecast"]
    return {
        "available": True, "city": city, "model_used": best, "model_description": DESCRIPTIONS[best],
        "beats_no_change_baseline": beats_baseline, "reliability": reliability,
        "best_model_backtest_mape_pct": best_mape,
        "model_comparison": table,
        "history": actual[["quarter", "quarter_end", "hpi"]].to_dict("records"),
        "provisional_actual": prov[["quarter", "quarter_end", "hpi"]].to_dict("records"),
        "forecast": points,
        "forecast_change_pct": round((end_val / last_val - 1) * 100, 2),
        "forecast_change_pct_annualised": round(((end_val / last_val) ** (4 / quarters) - 1) * 100, 2),
        "capped_to_25pct_per_year": capped,
        "interval_note": "Bands come from this model's own one-step backtest errors, scaled by sqrt(horizon). "
                         "With ~16 quarters they are rough, and real shocks (policy, level shifts) are not captured.",
        "baseline_mae": baseline["mae_index_points"],
    }


# ---------------------------------------------------------------- public: scenarios (city-level, from NHB)
def scenario_projection(nhb: pd.DataFrame, hpi: pd.DataFrame, city: str, years: int = 5) -> dict | None:
    """Bull / base / bear price-per-sqft paths. NOT a prediction: assumptions are shown in the output.

    base  = 50% the city's annualised NHB momentum + 50% the All-India HPI YoY (shrinks a short, noisy window
            toward the national trend), clipped to [-2%, 15%]
    spread = median absolute gap between city HPI YoY and All-India YoY across HPI cities (robust to outliers)
    bull/bear = base +/- spread (bear floored at -5%)
    """
    g = nhb[nhb["city"] == city].sort_values("quarter_end")
    if len(g) < 2:
        return None
    first, last = float(g["composite_price"].iloc[0]), float(g["composite_price"].iloc[-1])
    momentum = ((last / first) ** (4 / (len(g) - 1)) - 1) * 100

    nat, spread = _national_and_spread(hpi)
    base = float(np.clip(0.5 * momentum + 0.5 * nat, -2, 15))
    bull, bear = base + spread, max(base - spread, -5.0)

    def path(rate):
        return [{"year": t, "price_per_sqft": round(last * (1 + rate / 100) ** t)} for t in range(0, years + 1)]

    return {
        "city": city, "starting_price_per_sqft": last, "starting_quarter": g["quarter"].iloc[-1],
        "assumptions": {
            "city_nhb_momentum_annualised_pct": round(momentum, 2), "all_india_hpi_yoy_pct": round(nat, 2),
            "spread_pp": round(spread, 2), "base_growth_pct": round(base, 2),
            "bull_growth_pct": round(bull, 2), "bear_growth_pct": round(bear, 2)},
        "scenarios": {"bear": path(bear), "base": path(base), "bull": path(bull)},
        "disclaimer": "Scenario, not a forecast. Growth rates are rule-based from a 4-quarter NHB window and the "
                      "national HPI; they are not fitted to this city's long history.",
    }


def _national_and_spread(hpi: pd.DataFrame) -> tuple[float, float]:
    a = hpi[~hpi["provisional"]]
    yoy = {}
    for c, g in a.groupby("city"):
        g = g.sort_values("quarter_end")
        if len(g) >= 5:
            yoy[c] = (g["hpi"].iloc[-1] / g["hpi"].iloc[-5] - 1) * 100
    nat = yoy.pop("All India", 4.2)
    spread = float(np.median([abs(v - nat) for v in yoy.values()])) if yoy else 3.0
    return float(nat), max(spread, 1.0)