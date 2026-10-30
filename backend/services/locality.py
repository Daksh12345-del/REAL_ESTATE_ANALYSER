"""Locality-level Investment Score.

Honest scope: our listing data is a snapshot, so there is NO price growth per locality. A locality's score is therefore
    50%  the score of the city it sits in (growth, catalysts, stability, ... from the city model)
  + 50%  how attractive the locality is *within its city*:
           affordability  (cheaper than the city median)      40%
           rental yield   (vs the city's own rent/price ratio) 40%   [only where 10+ rent listings exist]
           market depth   (number of listings)                 20%
The three local parts are percentile ranks inside the city (0-100), so they compare a locality with its neighbours.
"""
from functools import lru_cache

import numpy as np
import pandas as pd

from services.data_loader import load_data

LOCAL_WEIGHTS = {"affordability": 0.4, "yield": 0.4, "depth": 0.2}
CITY_SHARE = 0.5
MIN_RENT_LISTINGS = 10
RADAR_AXES = ["affordability", "yield", "depth", "city_growth", "city_catalyst", "city_stability"]
RADAR_LABELS = {
    "affordability": "Affordability", "yield": "Rental yield", "depth": "Market depth",
    "city_growth": "City growth", "city_catalyst": "City catalysts", "city_stability": "City stability",
}


def _pct_rank(s: pd.Series) -> pd.Series:
    """0-100 percentile rank (lowest = 0, highest = 100); NaN stays NaN."""
    n = int(s.notna().sum())
    if n < 2:
        return s.where(s.isna(), 50.0)
    return (s.rank(method="average") - 1) / (n - 1) * 100


@lru_cache(maxsize=64)
def locality_table(city: str, min_listings: int) -> pd.DataFrame:
    """Per-locality stats and the three local component scores for one city."""
    data = load_data()
    s = data.sales[data.sales["city"] == city]
    if s.empty:
        return pd.DataFrame()
    g = s.groupby("locality").agg(listings=("price_per_sqft", "size"), median_price_psf=("price_per_sqft", "median"),
                                  median_price_lakh=("price_lakh", "median"), median_area=("area_sqft", "median"))
    g = g[g["listings"] >= min_listings].copy()
    if g.empty:
        return g
    city_median = s["price_per_sqft"].median()
    g["price_vs_city_pct"] = (g["median_price_psf"] / city_median - 1) * 100

    rents = data.rents[data.rents["city"] == city]
    if not rents.empty:
        r = rents.groupby("locality").agg(rent_listings=("rent_per_sqft", "size"), median_rent_psf=("rent_per_sqft", "median"))
        g = g.join(r[r["rent_listings"] >= MIN_RENT_LISTINGS])
        city_ratio = rents["rent_per_sqft"].median() / city_median
        g["yield_vs_city_pct"] = (g["median_rent_psf"] / g["median_price_psf"] / city_ratio - 1) * 100
    else:
        g["rent_listings"], g["median_rent_psf"], g["yield_vs_city_pct"] = np.nan, np.nan, np.nan

    g["c_affordability"] = 100 - _pct_rank(g["median_price_psf"])
    g["c_yield"] = _pct_rank(g["yield_vs_city_pct"])
    g["c_depth"] = _pct_rank(g["listings"])

    parts = g[["c_affordability", "c_yield", "c_depth"]].to_numpy()
    w = np.array([LOCAL_WEIGHTS["affordability"], LOCAL_WEIGHTS["yield"], LOCAL_WEIGHTS["depth"]])
    mask = ~np.isnan(parts)
    g["local_score"] = np.nansum(parts * w, axis=1) / (mask * w).sum(axis=1)
    return g.reset_index()


def score_localities(city: str, city_record: dict, min_listings: int = 20) -> pd.DataFrame:
    """Add the final score. city_record is the dict from routes.api.city_record (score + component_scores)."""
    t = locality_table(city, min_listings)
    if t.empty:
        return t
    t = t.copy()
    city_score = city_record.get("score")
    t["city_score"] = city_score
    t["score"] = (CITY_SHARE * city_score + (1 - CITY_SHARE) * t["local_score"]) if city_score is not None else t["local_score"]
    t["rank"] = t["score"].rank(ascending=False, method="min").astype(int)
    return t.sort_values("rank").reset_index(drop=True)


def radar_values(row: pd.Series, city_record: dict) -> dict:
    cs = city_record["component_scores"]
    return {
        "affordability": row["c_affordability"], "yield": row["c_yield"], "depth": row["c_depth"],
        "city_growth": cs.get("growth"), "city_catalyst": cs.get("catalyst"), "city_stability": cs.get("stability"),
    }
