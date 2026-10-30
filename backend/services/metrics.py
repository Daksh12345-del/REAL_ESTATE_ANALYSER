"""City-level metrics computed from the cleaned data."""
import numpy as np
import pandas as pd

MIN_ROWS_FOR_YIELD = 100  # need enough rent listings to trust a city-level median rent


def _hpi_stats(hpi: pd.DataFrame) -> pd.DataFrame:
    """YoY growth, volatility and latest index per city. Provisional quarters are ignored."""
    out = {}
    for city, g in hpi[~hpi["provisional"]].groupby("city"):
        g = g.sort_values("quarter_end")
        if len(g) < 5:
            continue
        qoq = g["hpi"].pct_change().dropna() * 100
        out[city] = {
            "hpi_latest": g["hpi"].iloc[-1],
            "hpi_latest_quarter": g["quarter"].iloc[-1],
            "hpi_yoy_pct": (g["hpi"].iloc[-1] / g["hpi"].iloc[-5] - 1) * 100,
            "hpi_volatility": qoq.std(),
        }
    return pd.DataFrame.from_dict(out, orient="index")


def _nhb_stats(nhb: pd.DataFrame) -> pd.DataFrame:
    """Latest price and annualised momentum. NHB gives only 4 quarters, so momentum is short-window."""
    out = {}
    for city, g in nhb.groupby("city"):
        g = g.sort_values("quarter_end")
        if len(g) < 2:
            continue
        first, last = g["composite_price"].iloc[0], g["composite_price"].iloc[-1]
        quarters = len(g) - 1
        out[city] = {
            "nhb_price": last,
            "nhb_momentum_pct": ((last / first) ** (4 / quarters) - 1) * 100,
        }
    return pd.DataFrame.from_dict(out, orient="index")


def build_city_metrics(data) -> pd.DataFrame:
    cat = data.catalysts
    m = pd.DataFrame(index=cat.index)
    m["state"] = cat["state"]
    m["tier_type"] = cat["tier_type"]
    m["catalyst_score"] = cat["catalyst_score_1to10"].astype(float)

    s = data.sales.groupby("city").agg(sale_rows=("price_per_sqft", "size"), median_price_psf=("price_per_sqft", "median"))
    r = data.rents.groupby("city").agg(rent_rows=("rent_per_sqft", "size"), median_rent_psf=("rent_per_sqft", "median"))
    m = m.join(s).join(r).join(_hpi_stats(data.hpi)).join(_nhb_stats(data.nhb))

    # Yield = annual rent per sqft / NHB carpet-area price per sqft (recent, same basis as rents).
    # Listing sale medians are from different years/samples and gave unrealistic yields (6%+).
    ok = m["rent_rows"] >= MIN_ROWS_FOR_YIELD
    m["gross_yield_pct"] = np.where(ok, m["median_rent_psf"] * 12 / m["nhb_price"] * 100, np.nan)
    for c in ["sale_rows", "rent_rows"]:
        m[c] = m[c].fillna(0).astype(int)
    return m