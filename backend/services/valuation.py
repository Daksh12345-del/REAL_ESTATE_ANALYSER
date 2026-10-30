"""Fair-price model: predicts price per sq ft of a listing from city, locality, area and BHK.

Features
  city_code   : city as a category
  loc_enc     : smoothed mean of log(price/sqft) in that locality (target encoding, computed out-of-fold in training)
  loc_n       : log(1 + listings in that locality)
  log_area    : log(area in sq ft)
  bhk         : bedrooms (NaN allowed)
The model is trained offline by train_model.py; this module only loads and applies it.
"""
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
MODEL_PATH = BASE / "models" / "valuation.joblib"
DEALS_PATH = BASE / "data" / "processed" / "undervalued.csv"
SMOOTH_K = 5.0
FEATURES = ["city_code", "loc_enc", "loc_n", "log_area", "bhk"]


def encode_localities(train: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Locality and city means of log price/sqft from a training frame with columns city, locality, log_psf."""
    city_mean = train.groupby("city")["log_psf"].mean()
    loc = train.groupby(["city", "locality"])["log_psf"].agg(["sum", "count"])
    return loc, city_mean


def apply_encoding(df: pd.DataFrame, loc: pd.DataFrame, city_mean: pd.Series) -> pd.DataFrame:
    """Add loc_enc / loc_n to df using stats from `loc` (smoothed toward the city mean)."""
    idx = pd.MultiIndex.from_arrays([df["city"], df["locality"]])
    s = loc["sum"].reindex(idx).to_numpy()
    n = loc["count"].reindex(idx).fillna(0).to_numpy()
    cm = df["city"].map(city_mean).to_numpy()
    s = np.nan_to_num(s, nan=0.0)
    out = df.copy()
    out["loc_enc"] = (s + SMOOTH_K * cm) / (n + SMOOTH_K)
    out["loc_n"] = np.log1p(n)
    return out


def make_features(df: pd.DataFrame, city_categories: list) -> pd.DataFrame:
    x = df.copy()
    x["city_code"] = pd.Categorical(x["city"], categories=city_categories).codes
    x["log_area"] = np.log(x["area_sqft"].astype(float))
    return x[FEATURES]


@lru_cache(maxsize=1)
def load_artifact() -> dict | None:
    return joblib.load(MODEL_PATH) if MODEL_PATH.exists() else None


@lru_cache(maxsize=1)
def load_deals() -> pd.DataFrame | None:
    return pd.read_csv(DEALS_PATH) if DEALS_PATH.exists() else None


def valuate(city: str, locality: str | None, area_sqft: float, bhk: float | None = None) -> dict:
    art = load_artifact()
    if art is None:
        raise FileNotFoundError("Model not trained. Run: python train_model.py")
    loc_name = (locality or "").strip().title()
    row = pd.DataFrame([{"city": city, "locality": loc_name, "area_sqft": area_sqft, "bhk": bhk if bhk else np.nan}])
    row = apply_encoding(row, art["loc_stats"], art["city_mean"])
    known = (city, loc_name) in art["loc_stats"].index
    pred_log = float(art["model"].predict(make_features(row, art["cities"]))[0])
    q_lo, q_hi = art["residual_q10"], art["residual_q90"]
    psf = float(np.exp(pred_log))
    return {
        "city": city, "locality": loc_name or None, "locality_seen_in_training": bool(known),
        "fair_price_per_sqft": round(psf), "fair_price_lakh": round(psf * area_sqft / 1e5, 1),
        "likely_range_lakh": [round(np.exp(pred_log + q_lo) * area_sqft / 1e5, 1),
                              round(np.exp(pred_log + q_hi) * area_sqft / 1e5, 1)],
        "range_note": "80% of held-out listings had actual prices inside this band around the model's estimate.",
        "warning": None if known else "Locality not found in training data; estimate uses the city average and is less reliable.",
    }