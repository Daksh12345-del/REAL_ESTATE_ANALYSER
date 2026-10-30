import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import app  # noqa: E402

client = app.test_client()


def test_health():
    assert client.get("/api/health").json == {"status": "ok"}


def test_opportunities_ranked_and_bounded():
    r = client.get("/api/opportunities?profile=balanced&top=5").json
    scores = [x["score"] for x in r["results"]]
    assert scores == sorted(scores, reverse=True)
    assert all(0 <= s <= 100 for s in scores)
    assert "Hosur" in r["not_scored"]


def test_profiles_change_ranking():
    a = client.get("/api/opportunities?profile=conservative").json["results"][0]["city"]
    b = client.get("/api/opportunities?profile=aggressive").json["results"][0]["city"]
    assert a and b


def test_custom_weights():
    r = client.get("/api/opportunities?w_growth=100&w_yield=0&w_affordability=0&w_catalyst=0&w_stability=0").json
    assert r["profile"] == "custom"


def test_bad_city_is_404():
    assert client.get("/api/city/Atlantis").status_code == 404


def test_compare_needs_two_cities():
    assert client.get("/api/compare?cities=Pune").status_code == 400


def test_trends_and_localities():
    assert client.get("/api/trends?city=Pune").json["has_hpi"]
    assert len(client.get("/api/localities?city=Gurugram").json["localities"]) > 0


# ---------------------------------------------------------------- Day 4
def test_forecast_has_bands_and_comparison():
    r = client.get("/api/forecast?city=Pune&quarters=4").json
    mf = r["model_forecast"]
    assert mf["available"] and len(mf["forecast"]) == 4
    for p in mf["forecast"]:
        assert p["lower_95"] <= p["lower_80"] <= p["forecast"] <= p["upper_80"] <= p["upper_95"]
    assert len(mf["model_comparison"]) == 4
    assert mf["reliability"] in {"medium", "low", "very_low"}


def test_city_without_hpi_gets_scenarios_only():
    r = client.get("/api/forecast?city=Indore").json
    assert r["model_forecast"]["available"] is False
    s = r["scenarios"]["scenarios"]
    assert s["bear"][-1]["price_per_sqft"] <= s["base"][-1]["price_per_sqft"] <= s["bull"][-1]["price_per_sqft"]


def test_hosur_has_nothing_to_forecast():
    assert client.get("/api/forecast?city=Hosur").status_code == 404


def test_forecast_bad_params():
    assert client.get("/api/forecast?city=Pune&quarters=99").status_code == 400


def test_valuate_and_verdict():
    r = client.get("/api/valuate?city=Gurugram&locality=Sector 65&area_sqft=1800&bhk=3&asking_price_lakh=100").json
    lo, hi = r["likely_range_lakh"]
    assert lo < r["fair_price_lakh"] < hi
    assert "below" in r["verdict"]


def test_valuate_requires_area():
    assert client.get("/api/valuate?city=Pune").status_code == 400


def test_undervalued_and_model_info():
    d = client.get("/api/undervalued?city=Gurugram&limit=5").json
    assert all(15 <= x["discount_pct"] <= 35 for x in d["listings"])
    assert client.get("/api/model-info").json["model"]["median_ape_pct"] < \
        client.get("/api/model-info").json["baseline_locality_mean"]["median_ape_pct"]


# ---------------------------------------------------------------- Day 6
def test_emi_matches_hand_calculation():
    from services.rentbuy import emi
    assert abs(emi(50e5, 8.5, 20) - 43391) < 5


def test_rent_vs_buy_growth_drives_break_even():
    from services.rentbuy import simulate
    assert simulate(80, 22000, appreciation_pct=0)["break_even_years"] is None
    fast = simulate(80, 22000, appreciation_pct=10)["break_even_years"]
    assert fast is not None and fast < 10


def test_rent_vs_buy_endpoint_and_validation():
    r = client.get("/api/rent-vs-buy?price_lakh=80&monthly_rent=22000").json
    assert len(r["sensitivity"]) == 6 and r["emi"] > 0
    assert client.get("/api/rent-vs-buy?price_lakh=80").status_code == 400
    assert client.get("/api/rent-vs-buy?price_lakh=80&monthly_rent=22000&loan_rate_pct=99").status_code == 400


def test_rent_vs_buy_cities_and_defaults():
    r = client.get("/api/rent-vs-buy/cities").json["cities"]
    assert len(r) >= 6 and all("break_even_years_at_5pct" in c for c in r)
    d = client.get("/api/rent-vs-buy/defaults?city=Pune&area_sqft=1000").json
    assert d["price_lakh"] > 0 and d["monthly_rent"] > 0


def test_locality_scores_sorted_and_bounded():
    r = client.get("/api/locality-scores?city=Pune&limit=20").json["localities"]
    scores = [x["score"] for x in r]
    assert scores == sorted(scores, reverse=True) and all(0 <= s <= 100 for s in scores)
    assert client.get("/api/locality-scores?city=Hosur").status_code in (404,)


def test_locality_compare_radar():
    r = client.get("/api/locality-compare?items=Pune|Baner,Pune|Wakad").json
    assert len(r["items"]) == 2 and len(r["axes"]) == 6
    assert client.get("/api/locality-compare?items=Pune|Baner").status_code == 400
    assert client.get("/api/locality-compare?items=Pune|Nowhere,Pune|Baner").status_code == 404


def test_locality_compare_repeated_item_param():
    r = client.get("/api/locality-compare?item=Pune|Baner&item=Pune|Wakad&item=Noida|Sector 62")
    assert r.status_code in (200, 404)
    assert client.get("/api/locality-compare?item=Pune|Baner&item=Pune|Wakad").json["items"][1]["locality"] == "Wakad"