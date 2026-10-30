"""Train the fair-price model and precompute undervalued listings.

Run once (and again whenever sales.csv changes):
    python train_model.py

Outputs
    models/valuation.joblib            model + locality stats used by /api/valuate
    models/valuation_metrics.json      honest holdout metrics shown by /api/model-info
    data/processed/undervalued.csv     listings priced well below the model's out-of-fold estimate
"""
import json
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import KFold

from services.valuation import (SMOOTH_K, apply_encoding, encode_localities, make_features)

BASE = Path(__file__).resolve().parent
SALES = BASE / "data" / "processed" / "sales.csv"
OUT_MODEL = BASE / "models" / "valuation.joblib"
OUT_METRICS = BASE / "models" / "valuation_metrics.json"
OUT_DEALS = BASE / "data" / "processed" / "undervalued.csv"

MIN_LOCALITY_LISTINGS = 20     # a deal is only flagged if its locality has this many other listings
DEAL_MIN_DISCOUNT, DEAL_MAX_DISCOUNT = 15, 35   # model error is ~15% median (80% of listings within ~+-30%), so bigger gaps are mostly noise
TOP_PER_CITY = 300


def new_model():
    return HistGradientBoostingRegressor(max_iter=300, learning_rate=0.08, max_leaf_nodes=31,
                                         min_samples_leaf=40, random_state=42)


def main():
    t0 = time.time()
    df = pd.read_csv(SALES)
    df["locality"] = df["locality"].astype(str).str.strip().str.title()
    df = df.dropna(subset=["city", "locality", "area_sqft", "price_per_sqft"]).reset_index(drop=True)
    df["log_psf"] = np.log(df["price_per_sqft"])
    cities = sorted(df["city"].unique())
    print(f"{len(df):,} listings, {len(cities)} cities")

    # ---- out-of-fold predictions (every listing is predicted by a model that never saw it) ----
    oof = np.full(len(df), np.nan)
    oof_n = np.zeros(len(df))
    kf = KFold(n_splits=5, shuffle=True, random_state=42)
    for i, (tr, te) in enumerate(kf.split(df), 1):
        train, test = df.iloc[tr], df.iloc[te]
        loc, cmean = encode_localities(train)
        # encode the training rows out-of-fold too, otherwise the model just memorises its own target
        train_enc = train.copy()
        inner = KFold(n_splits=5, shuffle=True, random_state=1)
        parts = []
        for itr, ite in inner.split(train):
            l2, c2 = encode_localities(train.iloc[itr])
            parts.append(apply_encoding(train.iloc[ite], l2, c2))
        train_enc = pd.concat(parts).loc[train.index]
        test_enc = apply_encoding(test, loc, cmean)
        model = new_model().fit(make_features(train_enc, cities), train["log_psf"])
        oof[te] = model.predict(make_features(test_enc, cities))
        oof_n[te] = np.expm1(test_enc["loc_n"].to_numpy())
        print(f"  fold {i}/5 done ({time.time() - t0:.0f}s)")

    resid = df["log_psf"].to_numpy() - oof
    actual, pred = df["price_per_sqft"].to_numpy(), np.exp(oof)

    # baseline: just the locality mean (what a naive analyst would use), also out-of-fold
    base = np.full(len(df), np.nan)
    for tr, te in kf.split(df):
        l, c = encode_localities(df.iloc[tr])
        base[te] = apply_encoding(df.iloc[te], l, c)["loc_enc"].to_numpy()
    base_resid = df["log_psf"].to_numpy() - base

    def metrics(r, p):
        return {"mape_pct": round(float(np.mean(np.abs(actual - p) / actual) * 100), 2),
                "median_ape_pct": round(float(np.median(np.abs(actual - p) / actual) * 100), 2),
                "r2_log_price": round(float(1 - np.var(r) / np.var(df["log_psf"])), 3)}

    m_model, m_base = metrics(resid, pred), metrics(base_resid, np.exp(base))
    per_city = {c: round(float(np.median(np.abs(actual[df.city == c] - pred[df.city == c]) / actual[df.city == c]) * 100), 1)
                for c in cities}
    print("model   :", m_model, "\nbaseline:", m_base, "\nper-city median APE %:", per_city)

    # ---- final model on all data ----
    loc, cmean = encode_localities(df)
    parts = []
    for itr, ite in KFold(n_splits=5, shuffle=True, random_state=7).split(df):
        l2, c2 = encode_localities(df.iloc[itr])
        parts.append(apply_encoding(df.iloc[ite], l2, c2))
    full_enc = pd.concat(parts).loc[df.index]
    final = new_model().fit(make_features(full_enc, cities), df["log_psf"])

    OUT_MODEL.parent.mkdir(exist_ok=True)
    joblib.dump({"model": final, "loc_stats": loc, "city_mean": cmean, "cities": cities,
                 "residual_q10": float(np.quantile(resid, 0.10)), "residual_q90": float(np.quantile(resid, 0.90))},
                OUT_MODEL, compress=3)
    OUT_METRICS.write_text(json.dumps({
        "listings": int(len(df)), "cities": cities, "validation": "5-fold out-of-fold (each listing predicted by a model that never saw it)",
        "model": m_model, "baseline_locality_mean": m_base, "median_ape_pct_by_city": per_city,
        "caveats": ["Listings come from different sources/years, so 'fair price' is relative to those samples, not today's market.",
                    "Discounted listings are candidates to verify (could be old, different property type, or data errors).",
                    "Random split: near-duplicate listings can flatter the scores a little."]}, indent=2))

    # ---- undervalued listings ----
    d = df.copy()
    d["fair_price_per_sqft"] = pred
    d["discount_pct"] = (1 - d["price_per_sqft"] / d["fair_price_per_sqft"]) * 100
    d["locality_listings"] = oof_n.round().astype(int)
    d["fair_price_lakh"] = d["fair_price_per_sqft"] * d["area_sqft"] / 1e5
    deals = d[(d["locality_listings"] >= MIN_LOCALITY_LISTINGS) &
              d["discount_pct"].between(DEAL_MIN_DISCOUNT, DEAL_MAX_DISCOUNT)]
    deals = (deals.sort_values("discount_pct", ascending=False).groupby("city").head(TOP_PER_CITY)
             [["city", "locality", "bhk", "area_sqft", "price_lakh", "price_per_sqft", "fair_price_lakh",
               "fair_price_per_sqft", "discount_pct", "locality_listings", "source"]].round(1))
    deals.to_csv(OUT_DEALS, index=False)
    print(f"saved model, metrics and {len(deals):,} candidate deals in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()