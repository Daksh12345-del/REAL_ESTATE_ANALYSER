"""Day 6 endpoints: locality scores, locality comparison (radar), rent vs buy."""
import pandas as pd
from flask import Blueprint, jsonify, request

from routes.api import ApiError, _state, city_record, clean, get_city, get_weights
from services import rentbuy
from services.forecast import scenario_projection
from services.locality import RADAR_AXES, RADAR_LABELS, radar_values, score_localities
from services.scoring import score_cities

bp = Blueprint("tools_api", __name__, url_prefix="/api")

SORTS = {"score": ("score", False), "price": ("median_price_psf", False), "cheapest": ("median_price_psf", True),
         "yield": ("yield_vs_city_pct", False), "listings": ("listings", False)}


def _city_rec(city, profile_weights):
    data, metrics = _state()
    scores = score_cities(metrics, profile_weights)
    return city_record(city, metrics, scores, data)


# ---------------------------------------------------------------- localities
@bp.get("/locality-scores")
def locality_scores():
    """?city=Pune&profile=balanced&min_listings=20&sort=score|price|cheapest|yield|listings&limit=50"""
    _, metrics = _state()
    city = get_city(request.args.get("city", ""), metrics)
    profile, weights = get_weights()
    min_n = request.args.get("min_listings", 20, type=int)
    limit = min(request.args.get("limit", 50, type=int), 200)
    sort = request.args.get("sort", "score")
    if sort not in SORTS:
        raise ApiError(f"sort must be one of {list(SORTS)}")

    rec = _city_rec(city, weights)
    t = score_localities(city, rec, min_n)
    if t.empty:
        raise ApiError(f"No locality data for {city} with at least {min_n} listings.", 404)
    col, asc = SORTS[sort]
    t = t.sort_values(col, ascending=asc, na_position="last").head(limit)
    rows = [{
        "locality": r.locality, "score": r.score, "rank": r.rank, "listings": r.listings,
        "median_price_psf": r.median_price_psf, "median_price_lakh": r.median_price_lakh, "median_area": r.median_area,
        "price_vs_city_pct": r.price_vs_city_pct, "median_rent_psf": r.median_rent_psf,
        "rent_listings": r.rent_listings, "yield_vs_city_pct": r.yield_vs_city_pct,
        "components": {"affordability": r.c_affordability, "yield": r.c_yield, "depth": r.c_depth},
        "local_score": r.local_score,
    } for r in t.itertuples()]
    return jsonify(clean({
        "city": city, "profile": profile, "city_score": rec["score"], "min_listings": min_n,
        "count": int(len(t)), "localities": rows,
        "method": "Score = 50% city score + 50% locality score (affordability 40%, rental yield vs city 40%, "
                  "market depth 20%; percentile ranks inside the city). Listing data is a snapshot, so there is no "
                  "locality-level price growth."}))


@bp.get("/locality-compare")
def locality_compare():
    """?item=Pune|Baner&item=Pune|Wakad&item=Noida|Sector 62  (2 to 5 items, may mix cities)"""
    # repeated ?item=City|Locality is safest (locality names can contain commas); ?items=a,b also works
    raw = request.args.getlist("item") or [x for x in request.args.get("items", "").split(",") if x.strip()]
    if not 2 <= len(raw) <= 5:
        raise ApiError("Pass 2 to 5 items as City|Locality, e.g. ?item=Pune|Baner&item=Pune|Wakad")
    _, metrics = _state()
    profile, weights = get_weights()
    min_n = request.args.get("min_listings", 20, type=int)   # same threshold as the ranking, so ranks match
    out = []
    for item in raw:
        if "|" not in item:
            raise ApiError(f"'{item}' must look like City|Locality")
        city_name, loc = item.split("|", 1)
        city = get_city(city_name, metrics)
        rec = _city_rec(city, weights)
        t = score_localities(city, rec, min_n)
        row = t[t["locality"].str.lower() == loc.strip().lower()] if not t.empty else t
        if row.empty:
            raise ApiError(f"'{loc}' not found in {city} with at least {min_n} listings. Lower the minimum listings in the Ranking tab.", 404)
        r = row.iloc[0]
        out.append({
            "city": city, "locality": r["locality"], "score": r["score"], "rank_in_city": r["rank"],
            "localities_in_city": int(len(t)), "listings": r["listings"], "median_price_psf": r["median_price_psf"],
            "median_price_lakh": r["median_price_lakh"], "price_vs_city_pct": r["price_vs_city_pct"],
            "median_rent_psf": r["median_rent_psf"], "yield_vs_city_pct": r["yield_vs_city_pct"],
            "radar": radar_values(r, rec)})
    return jsonify(clean({"profile": profile, "axes": [{"key": k, "label": RADAR_LABELS[k]} for k in RADAR_AXES],
                          "items": out,
                          "note": "Affordability, yield and depth compare a locality with its own city. City growth, "
                                  "catalysts and stability are inherited from the city and are identical for localities in the same city."}))


# ---------------------------------------------------------------- rent vs buy
def _num(name, default, lo, hi):
    v = request.args.get(name, type=float)
    v = default if v is None else v
    if not lo <= v <= hi:
        raise ApiError(f"{name} must be between {lo} and {hi}")
    return v


def _rvb_args():
    price, rent = request.args.get("price_lakh", type=float), request.args.get("monthly_rent", type=float)
    if price is None or rent is None:
        raise ApiError("price_lakh and monthly_rent are required")
    if not 5 <= price <= 5000:
        raise ApiError("price_lakh must be between 5 and 5000")
    if not 1000 <= rent <= 2_000_000:
        raise ApiError("monthly_rent must be between 1000 and 2000000")
    return dict(
        price_lakh=price, monthly_rent=rent,
        down_payment_pct=_num("down_payment_pct", 20, 0, 90), loan_rate_pct=_num("loan_rate_pct", 8.0, 0, 20),
        tenure_years=int(_num("tenure_years", 20, 1, 30)), appreciation_pct=_num("appreciation_pct", 5.0, -10, 25),
        rent_growth_pct=_num("rent_growth_pct", 5.0, -10, 25), investment_return_pct=_num("investment_return_pct", 8.0, 0, 25),
        buying_cost_pct=_num("buying_cost_pct", 6.0, 0, 15), upkeep_pct=_num("upkeep_pct", 0.75, 0, 5),
        selling_cost_pct=_num("selling_cost_pct", 2.0, 0, 10), horizon_years=int(_num("horizon_years", 25, 1, 35)))


@bp.get("/rent-vs-buy")
def rent_vs_buy():
    """?price_lakh=80&monthly_rent=22000&down_payment_pct=20&loan_rate_pct=8&tenure_years=20 ...
    Also returns how the break-even changes with the price-growth assumption (the biggest driver)."""
    args = _rvb_args()
    out = rentbuy.simulate(**args)
    sens = []
    for g in (0, 2, 4, 6, 8, 10):
        r = rentbuy.simulate(**{**args, "appreciation_pct": g})
        sens.append({"appreciation_pct": g, "break_even_years": r["break_even_years"], "final_gap_lakh": r["final_gap_lakh"]})
    out["sensitivity"] = sens
    return jsonify(clean(out))


def _defaults_for(city, area_sqft):
    data, metrics = _state()
    m = metrics.loc[city]
    price_psf = m["nhb_price"] if pd.notna(m["nhb_price"]) else m["median_price_psf"]
    if pd.isna(price_psf):
        return None
    rent_psf = m["median_rent_psf"]
    scen = scenario_projection(data.nhb, data.hpi, city)
    appreciation = scen["assumptions"]["base_growth_pct"] if scen else 5.0
    return {
        "city": city, "area_sqft": area_sqft,
        "price_lakh": round(price_psf * area_sqft / 1e5, 1),
        "price_basis": "NHB Residex carpet-area price" if pd.notna(m["nhb_price"]) else "listing median",
        "monthly_rent": None if pd.isna(rent_psf) else round(rent_psf * area_sqft / 100) * 100,
        "rent_rows": int(m["rent_rows"]),
        "appreciation_pct": round(float(min(max(appreciation, 3.0), 9.0)), 1),
        "note": "Rent comes from older listing samples (2022 to 2024) while price is 2025-26, so rent is probably "
                "understated. Adjust it if you know the current market rent."}


@bp.get("/rent-vs-buy/defaults")
def rent_vs_buy_defaults():
    _, metrics = _state()
    city = get_city(request.args.get("city", ""), metrics)
    area = _num("area_sqft", 1000, 200, 5000)
    d = _defaults_for(city, area)
    if d is None:
        raise ApiError(f"No price data for {city}.", 404)
    return jsonify(clean(d))


@bp.get("/rent-vs-buy/cities")
def rent_vs_buy_cities():
    """Break-even per city with default assumptions for a home of ?area_sqft=1000."""
    _, metrics = _state()
    area = _num("area_sqft", 1000, 200, 5000)
    rows = []
    for city in metrics.index:
        d = _defaults_for(city, area)
        if not d or not d["monthly_rent"] or d["rent_rows"] < 100:
            continue
        sim = rentbuy.simulate(d["price_lakh"], d["monthly_rent"], appreciation_pct=d["appreciation_pct"])
        flat = rentbuy.simulate(d["price_lakh"], d["monthly_rent"], appreciation_pct=5.0)
        rows.append({"city": city, "price_lakh": d["price_lakh"], "monthly_rent": d["monthly_rent"],
                     "appreciation_pct": d["appreciation_pct"], "gross_rental_yield_pct": sim["gross_rental_yield_pct"],
                     "price_to_annual_rent": sim["price_to_annual_rent"], "emi": sim["emi"],
                     "break_even_years": sim["break_even_years"], "buyer_wins_at_25y": sim["buyer_wins_at_horizon"],
                     "break_even_years_at_5pct": flat["break_even_years"], "final_gap_lakh_at_5pct": flat["final_gap_lakh"],
                     "final_gap_lakh": sim["final_gap_lakh"]})
    rows.sort(key=lambda r: (r["break_even_years"] is None, r["break_even_years"] or 0, -r["final_gap_lakh"]))
    return jsonify(clean({"area_sqft": area, "cities": rows,
                          "assumptions": "20% down, 8% loan for 20 years, 6% buying cost, 5% rent growth, 8% return on "
                                         "invested money, city's own base price growth (3% to 9%). Tax benefits ignored."}))
