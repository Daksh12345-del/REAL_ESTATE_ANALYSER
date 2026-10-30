"""Investment Score: five components, each scaled to 0-100 across cities (10th-90th percentile clipped), then weighted.

If a city is missing a component (no rent data, no RBI HPI ...) its weight is redistributed over the
components it does have. A city needs at least MIN_COMPONENTS to get a score at all.
"""
import numpy as np
import pandas as pd

COMPONENTS = ["growth", "yield", "affordability", "catalyst", "stability"]
MIN_COMPONENTS = 3

PROFILES = {
    "conservative": {"growth": 0.15, "yield": 0.30, "affordability": 0.15, "catalyst": 0.15, "stability": 0.25},
    "balanced":     {"growth": 0.25, "yield": 0.20, "affordability": 0.15, "catalyst": 0.25, "stability": 0.15},
    "aggressive":   {"growth": 0.35, "yield": 0.10, "affordability": 0.10, "catalyst": 0.35, "stability": 0.10},
}

LABELS = {
    "growth": "Price growth (RBI HPI YoY + NHB momentum)",
    "yield": "Rental yield",
    "affordability": "Affordability (lower NHB price/sqft is better)",
    "catalyst": "Infrastructure / industry catalysts",
    "stability": "Price stability (low RBI HPI volatility)",
}


def _minmax(s: pd.Series) -> pd.Series:
    s = s.astype(float)
    if s.notna().sum() < 2:
        return s.where(s.isna(), 50.0)
    # clip to the 10th-90th percentile so one outlier city (e.g. Nagpur HPI) cannot squash everyone else
    lo, hi = s.quantile(0.10), s.quantile(0.90)
    if hi == lo:
        return s.where(s.isna(), 50.0)
    return ((s.clip(lo, hi) - lo) / (hi - lo) * 100)


def component_scores(m: pd.DataFrame) -> pd.DataFrame:
    growth_raw = m[["hpi_yoy_pct", "nhb_momentum_pct"]].mean(axis=1, skipna=True)  # NaN if both missing
    raw = pd.DataFrame({
        "growth": growth_raw,
        "yield": m["gross_yield_pct"],
        "affordability": -np.log(m["nhb_price"]),
        "catalyst": m["catalyst_score"],
        "stability": -m["hpi_volatility"],
    })
    out = raw.apply(_minmax)
    out["catalyst"] = (raw["catalyst"] - 1) / 9 * 100  # already an absolute 1-10 scale, so no cross-city scaling
    return out


def normalise_weights(weights: dict) -> dict:
    w = {k: max(float(weights.get(k, 0)), 0.0) for k in COMPONENTS}
    total = sum(w.values())
    if total == 0:
        raise ValueError("At least one weight must be greater than zero")
    return {k: v / total for k, v in w.items()}


def score_cities(m: pd.DataFrame, weights: dict) -> pd.DataFrame:
    weights = normalise_weights(weights)
    comp = component_scores(m)
    rows = []
    for city in m.index:
        avail = [c for c in COMPONENTS if pd.notna(comp.loc[city, c]) and weights[c] > 0]
        n_avail = int(comp.loc[city].notna().sum())
        if n_avail < MIN_COMPONENTS or not avail:
            rows.append({"city": city, "score": None, "components_available": n_avail, "contributions": {}})
            continue
        wsum = sum(weights[c] for c in avail)
        contrib = {c: round(weights[c] / wsum * comp.loc[city, c], 1) for c in avail}
        rows.append({"city": city, "score": round(sum(contrib.values()), 1),
                     "components_available": n_avail, "contributions": contrib})
    out = pd.DataFrame(rows).set_index("city")
    out = out.join(comp.add_prefix("c_").round(1))
    out["rank"] = out["score"].rank(ascending=False, method="min")
    return out