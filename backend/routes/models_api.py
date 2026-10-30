"""Day 4 endpoints: forecasts, scenarios, fair-price valuation, undervalued listings."""
import json

import pandas as pd
from flask import Blueprint, jsonify, request

from routes.api import ApiError, _state, clean, get_city
from services import valuation
from services.forecast import forecast_city, scenario_projection

bp = Blueprint("models_api", __name__, url_prefix="/api")

METRICS_PATH = valuation.BASE / "models" / "valuation_metrics.json"


@bp.get("/forecast")
def forecast():
    """?city=Pune&quarters=4 (1-8). HPI cities get a backtested model forecast with confidence bands;
    every city with NHB prices also gets bull/base/bear scenarios (?years=1-10)."""
    data, metrics = _state()
    city = get_city(request.args.get("city", ""), metrics)
    quarters = request.args.get("quarters", 4, type=int)
    years = request.args.get("years", 5, type=int)
    if not 1 <= quarters <= 8:
        raise ApiError("quarters must be between 1 and 8")
    if not 1 <= years <= 10:
        raise ApiError("years must be between 1 and 10")

    model = forecast_city(data.hpi, city, quarters)
    scen = scenario_projection(data.nhb, data.hpi, city, years)
    if model is None and scen is None:
        raise ApiError(f"No price history for {city}; nothing to forecast.", 404)
    return jsonify(clean({
        "city": city,
        "model_forecast": model if model else {"available": False, "reason": "City is not in the RBI HPI (18 cities)."},
        "scenarios": scen if scen else {"available": False, "reason": "City is not in NHB Residex."},
    }))


@bp.get("/valuate")
def valuate():
    """?city=Gurugram&locality=Sector 65&area_sqft=1800&bhk=3&asking_price_lakh=220 (asking price optional)"""
    _, metrics = _state()
    city = get_city(request.args.get("city", ""), metrics)
    area = request.args.get("area_sqft", type=float)
    if not area or not 200 <= area <= 10000:
        raise ApiError("area_sqft is required and must be between 200 and 10000")
    try:
        est = valuation.valuate(city, request.args.get("locality"), area, request.args.get("bhk", type=float))
    except FileNotFoundError as e:
        raise ApiError(str(e), 503)
    ask = request.args.get("asking_price_lakh", type=float)
    if ask:
        diff = (1 - ask / est["fair_price_lakh"]) * 100
        lo, hi = est["likely_range_lakh"]
        est["asking_price_lakh"] = ask
        est["vs_fair_pct"] = round(diff, 1)
        est["verdict"] = ("inside the model's likely range: no clear signal" if lo <= ask <= hi else
                          "below the likely range: worth verifying (could be a deal, or something the model can't see)"
                          if ask < lo else "above the likely range: looks expensive versus similar listings")
    return jsonify(clean(est))


@bp.get("/undervalued")
def undervalued():
    """?city=Noida&limit=20&min_discount=15  -> listings priced below the model's out-of-fold fair price."""
    deals = valuation.load_deals()
    if deals is None:
        raise ApiError("Deals file missing. Run: python train_model.py", 503)
    city = request.args.get("city")
    df = deals
    if city:
        df = df[df["city"].str.lower() == city.strip().lower()]
    df = df[df["discount_pct"] >= request.args.get("min_discount", 15, type=float)]
    limit = min(request.args.get("limit", 20, type=int), 100)
    return jsonify(clean({
        "count_matching": int(len(df)), "listings": df.sort_values("discount_pct", ascending=False).head(limit).to_dict("records"),
        "warning": "These are candidates to verify, not recommendations. Sources and years differ, and the model has a "
                   "typical error of ~15%. Discounts above 35% are excluded because they are mostly data errors."}))


@bp.get("/model-info")
def model_info():
    if not METRICS_PATH.exists():
        raise ApiError("Metrics file missing. Run: python train_model.py", 503)
    return jsonify(json.loads(METRICS_PATH.read_text()))