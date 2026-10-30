import numpy as np
import pandas as pd
from flask import Blueprint, jsonify, request

from services.data_loader import load_data
from services.metrics import build_city_metrics
from services.scoring import COMPONENTS, LABELS, MIN_COMPONENTS, PROFILES, normalise_weights, score_cities

bp = Blueprint("api", __name__, url_prefix="/api")


# ---------------------------------------------------------------- helpers
def clean(obj):
    """Make pandas/numpy values JSON-safe (NaN -> None)."""
    if isinstance(obj, dict):
        return {k: clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        return None if pd.isna(obj) else round(float(obj), 2)
    if isinstance(obj, (pd.Timestamp,)):
        return obj.strftime("%Y-%m-%d")
    if obj is pd.NaT:
        return None
    return obj


class ApiError(Exception):
    def __init__(self, message, status=400):
        self.message, self.status = message, status


@bp.errorhandler(ApiError)
def _api_error(e):
    return jsonify({"error": e.message}), e.status


def get_city(name: str, metrics: pd.DataFrame) -> str:
    lookup = {c.lower(): c for c in metrics.index}
    city = lookup.get((name or "").strip().lower())
    if city is None:
        raise ApiError(f"Unknown city '{name}'. Valid: {sorted(metrics.index)}", 404)
    return city


def get_weights() -> tuple[str, dict]:
    """?profile=balanced  or custom sliders ?w_growth=30&w_yield=20&..."""
    custom = {c: request.args.get(f"w_{c}", type=float) for c in COMPONENTS}
    if any(v is not None for v in custom.values()):
        return "custom", normalise_weights({c: (v or 0) for c, v in custom.items()})
    profile = request.args.get("profile", "balanced").lower()
    if profile not in PROFILES:
        raise ApiError(f"profile must be one of {list(PROFILES)}")
    return profile, PROFILES[profile]


def _state():
    data = load_data()
    return data, build_city_metrics(data)


def city_record(city, metrics, scores, data):
    m, s = metrics.loc[city], scores.loc[city]
    cat = data.catalysts.loc[city]
    sc = s["score"]
    return {
        "city": city, "state": m["state"], "tier_type": m["tier_type"],
        "score": None if pd.isna(sc) else sc,
        "rank": None if pd.isna(s["rank"]) else int(s["rank"]),
        "status": "ok" if pd.notna(sc) else "insufficient_data",
        "components_available": int(s["components_available"]),
        "component_scores": {c: s[f"c_{c}"] for c in COMPONENTS},
        "contributions": s["contributions"],
        "metrics": {k: m[k] for k in ["median_price_psf", "median_rent_psf", "gross_yield_pct", "hpi_yoy_pct",
                                      "hpi_latest", "hpi_latest_quarter", "hpi_volatility", "nhb_price",
                                      "nhb_momentum_pct", "catalyst_score", "sale_rows", "rent_rows"]},
        "catalysts": {"summary": cat["key_catalysts"], "risks": cat["risks_and_setbacks"],
                      "sources": str(cat["source_urls"]).split("; "), "last_checked": cat["last_checked"]},
    }


# ---------------------------------------------------------------- endpoints
@bp.get("/health")
def health():
    return jsonify({"status": "ok"})


@bp.get("/cities")
def cities():
    """All cities with metrics and scores. ?profile=balanced|conservative|aggressive or ?w_growth=..&w_yield=.."""
    data, metrics = _state()
    profile, weights = get_weights()
    scores = score_cities(metrics, weights)
    recs = [city_record(c, metrics, scores, data) for c in metrics.index]
    recs.sort(key=lambda r: (r["rank"] is None, r["rank"] or 0))
    return jsonify(clean({"profile": profile, "weights": weights, "cities": recs}))


@bp.get("/opportunities")
def opportunities():
    """Ranked cities. ?top=10&tier=metro|emerging&profile=..."""
    data, metrics = _state()
    profile, weights = get_weights()
    scores = score_cities(metrics, weights)
    tier = request.args.get("tier")
    top = request.args.get("top", 10, type=int)
    recs = [city_record(c, metrics, scores, data) for c in metrics.index]
    recs = [r for r in recs if r["status"] == "ok" and (not tier or r["tier_type"] == tier)]
    recs.sort(key=lambda r: r["rank"])
    skipped = [c for c in metrics.index if pd.isna(scores.loc[c, "score"])]
    return jsonify(clean({"profile": profile, "weights": weights, "results": recs[:top],
                          "not_scored": skipped,
                          "note": f"A city needs at least {MIN_COMPONENTS} of 5 score components to be ranked."}))


@bp.get("/city/<name>")
def city_detail(name):
    data, metrics = _state()
    city = get_city(name, metrics)
    profile, weights = get_weights()
    scores = score_cities(metrics, weights)
    rec = city_record(city, metrics, scores, data)
    rec["profile"], rec["weights"] = profile, weights
    rec["explanation"] = [
        {"component": c, "label": LABELS[c], "score_0_100": rec["component_scores"][c],
         "points_added": rec["contributions"].get(c)} for c in COMPONENTS]
    missing = [LABELS[c] for c in COMPONENTS if rec["component_scores"][c] is None or pd.isna(rec["component_scores"][c])]
    rec["data_gaps"] = missing
    return jsonify(clean(rec))


@bp.get("/trends")
def trends():
    """RBI HPI (quarterly, base 2022-23=100) and NHB Residex price series for one city."""
    data, metrics = _state()
    city = get_city(request.args.get("city", ""), metrics)
    hpi = data.hpi[data.hpi["city"] == city]
    nhb = data.nhb[data.nhb["city"] == city]
    return jsonify(clean({
        "city": city,
        "hpi": hpi[["quarter", "quarter_end", "hpi", "provisional"]].to_dict("records"),
        "nhb": nhb[["quarter", "quarter_end", "composite_price", "small", "medium", "large"]].to_dict("records"),
        "notes": ["RBI HPI: base 2022-23 = 100, last quarter is provisional.",
                  "NHB Residex: Rs per sq ft of carpet area, only 4 quarters available."],
        "has_hpi": not hpi.empty, "has_nhb": not nhb.empty}))


@bp.get("/compare")
def compare():
    """?cities=Pune,Nagpur,Noida  -> metrics side by side + HPI rebased to 100 at the first common quarter."""
    data, metrics = _state()
    names = [n for n in request.args.get("cities", "").split(",") if n.strip()]
    if not 2 <= len(names) <= 6:
        raise ApiError("Pass 2 to 6 cities, e.g. ?cities=Pune,Nagpur")
    cities_ = [get_city(n, metrics) for n in names]
    profile, weights = get_weights()
    scores = score_cities(metrics, weights)
    recs = [city_record(c, metrics, scores, data) for c in cities_]

    h = data.hpi[data.hpi["city"].isin(cities_)].pivot(index="quarter_end", columns="city", values="hpi").dropna(how="all")
    common = h.dropna(axis=1, how="all").dropna()
    rebased = (common / common.iloc[0] * 100) if not common.empty else common
    series = {c: [{"quarter_end": d, "value": v} for d, v in rebased[c].items()] for c in rebased.columns}
    return jsonify(clean({"profile": profile, "cities": recs, "hpi_rebased_100": series,
                          "no_hpi_for": [c for c in cities_ if c not in rebased.columns]}))


@bp.get("/localities")
def localities():
    """Localities inside a city. ?city=Gurugram&min_listings=30&sort=price|listings|yield&limit=20"""
    data, metrics = _state()
    city = get_city(request.args.get("city", ""), metrics)
    min_n = request.args.get("min_listings", 30, type=int)
    sort = request.args.get("sort", "listings")
    limit = min(request.args.get("limit", 20, type=int), 100)

    s = data.sales[data.sales["city"] == city]
    if s.empty:
        raise ApiError(f"No listing data for {city}; only city-level data is available.", 404)
    g = s.groupby("locality").agg(listings=("price_per_sqft", "size"), median_price_psf=("price_per_sqft", "median"),
                                  median_price_lakh=("price_lakh", "median"), median_area=("area_sqft", "median"))
    g = g[g["listings"] >= min_n]
    city_median = s["price_per_sqft"].median()
    g["vs_city_median_pct"] = (g["median_price_psf"] / city_median - 1) * 100

    r = data.rents[data.rents["city"] == city].groupby("locality").agg(rent_listings=("rent_per_sqft", "size"),
                                                                       median_rent_psf=("rent_per_sqft", "median"))
    g = g.join(r[r["rent_listings"] >= 10])
    # Locality yield vs the city's own rent/price ratio (both from listings, so the same basis). Absolute listing
    # yields are inflated by mixing sample years, so only the relative figure is shown.
    city_rent = data.rents.loc[data.rents["city"] == city, "rent_per_sqft"].median()
    city_ratio = city_rent / city_median if pd.notna(city_rent) else np.nan
    g["yield_vs_city_pct"] = (g["median_rent_psf"] / g["median_price_psf"] / city_ratio - 1) * 100

    key = {"price": "median_price_psf", "listings": "listings", "yield": "yield_vs_city_pct"}.get(sort)
    if key is None:
        raise ApiError("sort must be price, listings or yield")
    g = g.sort_values(key, ascending=False).head(limit).reset_index()
    return jsonify(clean({"city": city, "city_median_price_psf": city_median, "min_listings": min_n,
                          "localities": g.to_dict("records")}))


@bp.get("/methodology")
def methodology():
    return jsonify({
        "components": LABELS, "profiles": PROFILES,
        "scoring": "Each component is scaled to 0-100 across cities (clipped at the 10th and 90th percentile so one outlier city cannot dominate). Score = weighted average of the "
                   "components a city has; missing components are dropped and weights renormalised. "
                   f"A city needs at least {MIN_COMPONENTS} of 5 components to get a score.",
        "limitations": [
            "Listing data comes from different sources and years (2022 to 2024); absolute prices are not directly comparable.",
            "RBI HPI has only 17 quarters for most cities; provisional latest quarter is excluded from growth/volatility.",
            "NHB Residex covers only 4 quarters, so momentum is annualised from a short window.",
            "Rental yield = median listing rent per sq ft x 12 / NHB Residex price per sq ft; only for cities with 100+ rent listings. It is an indicative, relative measure, not an exact yield.",
            "Catalyst scores are the author's judgement based on cited public sources.",
            "Hosur has no price data at all, so it is shown but not ranked.",
        ]})