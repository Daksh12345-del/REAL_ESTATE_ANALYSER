"""
clean_data.py  -  Real Estate Market Analysis Tool
Run from the backend/ folder:   python clean_data.py

Reads raw files from  data/raw/   (subfolders are fine)
Writes to             data/processed/
    sales.csv   city, locality, price_lakh, area_sqft, price_per_sqft, bhk, source
    rents.csv   city, locality, rent_monthly, area_sqft, rent_per_sqft, bhk, source
    hpi.csv     city, quarter, quarter_end, hpi, provisional   (RBI, base 2022-23 = 100)
    nhb.csv     city, quarter, quarter_end, composite_price, small, medium, large   (NHB Residex, Rs/sqft)
    report.txt  row counts before/after cleaning, per source and per city
"""
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAW = Path("data/raw")
OUT = Path("data/processed")
OUT.mkdir(parents=True, exist_ok=True)

LOG = []


def log(msg):
    print(msg)
    LOG.append(msg)


# ----------------------------------------------------------------- helpers
def find(*names):
    """Find a raw file by name (case-insensitive, searches subfolders)."""
    wanted = [n.lower() for n in names]
    for p in RAW.rglob("*"):
        if p.is_file() and p.name.lower() in wanted:
            return p
    log(f"  [skip] not found: {names}")
    return None


def read(*names, **kw):
    p = find(*names)
    if p is None:
        return None
    try:
        return pd.read_csv(p, low_memory=False, **kw)
    except UnicodeDecodeError:
        return pd.read_csv(p, low_memory=False, encoding="latin1", **kw)


def num(x):
    """First number in a string ('₹ 30,000' -> 30000, '1,250.5 sqft' -> 1250.5)."""
    if pd.isna(x):
        return np.nan
    m = re.search(r"\d[\d,]*\.?\d*", str(x))
    return float(m.group().replace(",", "")) if m else np.nan


def money_to_lakh(x):
    """'1.75 Cr' -> 175, '45 Lac' -> 45, '45 Lakh' -> 45. Plain rupees handled elsewhere."""
    if pd.isna(x):
        return np.nan
    s = str(x).lower()
    v = num(s)
    if "cr" in s:
        return v * 100
    if "lac" in s or "lakh" in s or re.search(r"\bl\b", s):
        return v
    return np.nan


def money_to_rupees(x):
    """'70,000' -> 70000, '1.4 Lac' -> 140000, '2 Cr' -> 20000000."""
    if pd.isna(x):
        return np.nan
    s = str(x).lower()
    v = num(s)
    if "cr" in s:
        return v * 1e7
    if "lac" in s or "lakh" in s:
        return v * 1e5
    return v


def bhk_from(x):
    """'3 BHK', '4 Bedroom', 'BHK3', '2 Bedrooms' -> int."""
    v = num(x)
    return v if pd.notna(v) and 0 <= v <= 15 else np.nan


def sqft_range(x):
    """'2100 - 2850' -> midpoint; '1200' -> 1200; '34.46Sq. Meter' -> sqft."""
    if pd.isna(x):
        return np.nan
    s = str(x).lower()
    nums = [float(n.replace(",", "")) for n in re.findall(r"\d[\d,]*\.?\d*", s)]
    if not nums:
        return np.nan
    v = float(np.mean(nums[:2])) if "-" in s and len(nums) >= 2 else nums[0]
    if "meter" in s or "sq.m" in s:
        v *= 10.7639
    elif "yard" in s:
        v *= 9
    elif "acre" in s:
        v *= 43560
    return v


def title(s):
    return s.astype(str).str.strip().str.replace(r"\s+", " ", regex=True).str.title()


CITY_MAP = {
    "bangalore": "Bengaluru", "bengaluru": "Bengaluru", "new delhi": "Delhi", "delhi": "Delhi",
    "gurgaon": "Gurugram", "gurugram": "Gurugram", "mumbai": "Mumbai", "pune": "Pune",
    "nagpur": "Nagpur", "noida": "Noida", "gautam buddha nagar": "Noida",
    "hyderabad": "Hyderabad", "chennai": "Chennai", "ahmedabad": "Ahmedabad",
}


def std_city(s):
    return s.astype(str).str.strip().str.lower().map(CITY_MAP).fillna(s.astype(str).str.strip().str.title())


SALE_COLS = ["city", "locality", "price_lakh", "area_sqft", "price_per_sqft", "bhk", "source"]
RENT_COLS = ["city", "locality", "rent_monthly", "area_sqft", "rent_per_sqft", "bhk", "source"]


def mk_sale(df, source):
    df = df.copy()
    df["source"] = source
    df["price_per_sqft"] = df["price_lakh"] * 1e5 / df["area_sqft"]
    return df[SALE_COLS]


def mk_rent(df, source):
    df = df.copy()
    df["source"] = source
    df["rent_per_sqft"] = df["rent_monthly"] / df["area_sqft"]
    return df[RENT_COLS]


# ----------------------------------------------------------------- SALE loaders
def sale_gurgaon():
    df = read("gurgaon_10k.csv")
    if df is None:
        return None
    df = df[df["TRANSACT_TYPE"] == 1]
    out = pd.DataFrame({
        "city": "Gurugram",
        "locality": df["LOCALITY_WO_CITY"],
        "price_lakh": pd.to_numeric(df["MIN_PRICE"], errors="coerce") / 1e5,
        "area_sqft": df["AREA"].map(num),
        "bhk": pd.to_numeric(df["BEDROOM_NUM"], errors="coerce"),
    })
    return mk_sale(out, "gurgaon_10k")


def sale_gurgaon_flats():
    df = read("flats.csv")
    if df is None:
        return None
    out = pd.DataFrame({
        "city": "Gurugram",
        "locality": df["address"].astype(str).str.split(",").str[0],
        "price_lakh": df["price"].map(money_to_lakh),
        "area_sqft": df["areaWithType"].map(num),
        "bhk": df["bedRoom"].map(bhk_from),
    })
    return mk_sale(out, "flats_99acres")


def sale_hyderabad():
    df = read("Hyderbad_House_price.csv")
    if df is None:
        return None
    out = pd.DataFrame({
        "city": "Hyderabad", "locality": df["location"],
        "price_lakh": pd.to_numeric(df["price(L)"], errors="coerce"),
        "area_sqft": pd.to_numeric(df["area_insqft"], errors="coerce"),
        "bhk": df["title"].map(bhk_from),
    })
    return mk_sale(out, "hyderabad_kaggle")


def sale_ahmedabad():
    df = read("99acres_desc.csv")
    if df is None:
        return None
    loc = df["location"].astype(str).str.lower()
    df = df[loc.str.contains("ahmedabad|sanand")]
    out = pd.DataFrame({
        "city": "Ahmedabad",
        "locality": df["location"].astype(str).str.replace(r",?\s*ahmedabad.*$", "", regex=True),
        "price_lakh": pd.to_numeric(df["price_in_cr"], errors="coerce") * 100,
        "area_sqft": pd.to_numeric(df["area_in_sqft"], errors="coerce"),
        "bhk": pd.to_numeric(df["bhk_type"], errors="coerce"),
    })
    return mk_sale(out, "99acres_ahmedabad")


def sale_delhi_magicbricks():
    df = read("MagicBricks.csv")
    if df is None:
        return None
    out = pd.DataFrame({
        "city": "Delhi", "locality": df["Locality"],
        "price_lakh": pd.to_numeric(df["Price"], errors="coerce") / 1e5,
        "area_sqft": pd.to_numeric(df["Area"], errors="coerce"),
        "bhk": pd.to_numeric(df["BHK"], errors="coerce"),
    })
    return mk_sale(out, "magicbricks_delhi")


def sale_delhi_ncr():
    df = read("Delhi_v2.csv")
    if df is None:
        return None
    a = df["Address"].astype(str).str.lower()
    city = np.select(
        [a.str.contains("gurgaon|gurugram"), a.str.contains("noida"), a.str.contains("ghaziabad"),
         a.str.contains("faridabad")],
        ["Gurugram", "Noida", "Ghaziabad", "Faridabad"], default="Delhi")
    out = pd.DataFrame({
        "city": city,
        "locality": df["Address"].astype(str).str.split(",").str[0],
        "price_lakh": pd.to_numeric(df["price"], errors="coerce") / 1e5,
        "area_sqft": pd.to_numeric(df["area"], errors="coerce"),
        "bhk": pd.to_numeric(df["Bedrooms"], errors="coerce"),
    })
    return mk_sale(out, "delhi_v2")


def sale_bengaluru():
    df = read("bengaluru_house_prices.csv", "Bengaluru_House_Data.csv")
    if df is None:
        return None
    out = pd.DataFrame({
        "city": "Bengaluru", "locality": df["location"],
        "price_lakh": pd.to_numeric(df["price"], errors="coerce"),  # already in lakh
        "area_sqft": df["total_sqft"].map(sqft_range),
        "bhk": df["size"].map(bhk_from),
    })
    return mk_sale(out, "bengaluru_kaggle")


def sale_noida():
    df = read("clean_dataset.csv")
    if df is None:
        return None
    df = df[df["address"].astype(str).str.contains("noida", case=False)]
    out = pd.DataFrame({
        "city": "Noida",
        "locality": df["address"].astype(str).str.split(",").str[0],
        "price_lakh": pd.to_numeric(df["price_in_lakh"], errors="coerce"),
        "area_sqft": pd.to_numeric(df["size"], errors="coerce"),
        "bhk": pd.to_numeric(df["bedroom"], errors="coerce"),
    })
    return mk_sale(out, "noida_clean_dataset")


def sale_chennai():
    df = read("clean_data.csv")
    if df is None:
        return None
    out = pd.DataFrame({
        "city": "Chennai", "locality": df["location"],
        "price_lakh": pd.to_numeric(df["price"], errors="coerce"),  # already in lakh
        "area_sqft": pd.to_numeric(df["area"], errors="coerce"),
        "bhk": pd.to_numeric(df["bhk"], errors="coerce"),
    })
    return mk_sale(out, "chennai_clean_data")


def sale_mumbai():
    df = read("Mumbai House Prices.csv")
    if df is None:
        return None
    p = pd.to_numeric(df["price"], errors="coerce")
    lakh = np.where(df["price_unit"].astype(str).str.lower().str.startswith("c"), p * 100, p)
    out = pd.DataFrame({
        "city": "Mumbai", "locality": df["region"],
        "price_lakh": lakh,
        "area_sqft": pd.to_numeric(df["area"], errors="coerce"),
        "bhk": pd.to_numeric(df["bhk"], errors="coerce"),
    })
    return mk_sale(out, "mumbai_house_prices")


def sale_maharashtra():
    """analysis_data.csv -> Pune and Nagpur only (Mumbai already covered by the file above)."""
    df = read("analysis_data.csv")
    if df is None:
        return None
    df = df[df["region_name"].astype(str).str.strip().isin(["Pune", "Nagpur"])]
    out = pd.DataFrame({
        "city": df["region_name"].astype(str).str.strip(),
        "locality": df["locality_name"],
        "price_lakh": pd.to_numeric(df["price"], errors="coerce") / 1e5,
        "area_sqft": pd.to_numeric(df["area"], errors="coerce"),
        "bhk": pd.to_numeric(df["total_beds"], errors="coerce"),
    })
    return mk_sale(out, "maharashtra_analysis_data")


def sale_pune_scraped():
    df = read("scrapped_data.csv")
    if df is None:
        return None
    parts = df["Title"].astype(str).str.split(",")
    out = pd.DataFrame({
        "city": "Pune",
        "locality": parts.str[-2].fillna(""),
        "price_lakh": df["Price"].map(money_to_lakh),
        "area_sqft": df["Carpet_Area"].map(num),
        "bhk": df["Title"].map(bhk_from),
    })
    return mk_sale(out, "pune_scraped")


# ----------------------------------------------------------------- RENT loaders
def rent_mumbai():
    df = read("Mumbai_property_details.csv")
    if df is None:
        return None
    df = df[df["Transaction Type"].astype(str).str.lower() == "rent"]
    loc = df["Title"].astype(str).str.extract(r"[Rr]ent in (.*)$")[0]
    loc = loc.str.split(" at ").str[-1]
    out = pd.DataFrame({
        "city": "Mumbai", "locality": loc,
        "rent_monthly": df["Price"].map(money_to_rupees),
        "area_sqft": df["Area"].astype(str).str.split().str[0].map(num),  # 2nd token is a code, ignore
        "bhk": pd.to_numeric(df["BHK"], errors="coerce"),
    })
    return mk_rent(out, "mumbai_property_details")


def rent_pune():
    df = read("test.csv")
    if df is None:
        return None
    df = df[df["address"].astype(str).str.contains("Pune", case=False)]
    parts = df["address"].astype(str).str.split(",")
    area = pd.to_numeric(df["area"], errors="coerce").replace(0, np.nan)
    out = pd.DataFrame({
        "city": "Pune", "locality": parts.str[1],
        "rent_monthly": pd.to_numeric(df["rent"], errors="coerce"),
        "area_sqft": area,
        "bhk": pd.to_numeric(df["bedroom"], errors="coerce"),
    })
    return mk_rent(out, "pune_test_csv")


def rent_noida():
    df = read("House_Rent_Dataset_Noida.csv")
    if df is None:
        return None
    loc = df["Rent location"].astype(str).str.split(",").str[0]
    out = pd.DataFrame({
        "city": "Noida", "locality": loc,
        "rent_monthly": df["Rent Price"].map(money_to_rupees),
        "area_sqft": df["Rent Details"].astype(str).str.extract(r"(\d[\d,]*)\s*sq", expand=False).map(num),
        "bhk": df["Rent Details"].map(bhk_from),
    })
    return mk_rent(out, "noida_rent")


def rent_multi():
    df = read("data__1_.csv")
    if df is None:
        return None
    out = pd.DataFrame({
        "city": std_city(df["city"]), "locality": df["locality"],
        "rent_monthly": pd.to_numeric(df["rent"], errors="coerce"),
        "area_sqft": pd.to_numeric(df["area"], errors="coerce"),
        "bhk": pd.to_numeric(df["beds"], errors="coerce"),
    })
    return mk_rent(out, "rent_multicity")


def rent_hyderabad():
    df = read("hyd_v2.csv")
    if df is None:
        return None
    df = df[df["propertyType"].astype(str).str.upper() == "RENT"]
    out = pd.DataFrame({
        "city": "Hyderabad", "locality": df["locality"],
        "rent_monthly": pd.to_numeric(df["rent_amount"], errors="coerce"),
        "area_sqft": pd.to_numeric(df["property_size"], errors="coerce"),
        "bhk": df["type_bhk"].map(bhk_from),
    })
    return mk_rent(out, "hyd_v2")


def rent_chennai():
    df = read("Rental_Dataset.csv")
    if df is None:
        return None
    out = pd.DataFrame({
        "city": "Chennai", "locality": df["LOCALITY"],
        "rent_monthly": pd.to_numeric(df["RENT"], errors="coerce"),
        "area_sqft": pd.to_numeric(df["SQ. FT"], errors="coerce"),
        "bhk": pd.to_numeric(df["BHK"], errors="coerce"),
    })
    return mk_rent(out, "chennai_rental")


# ----------------------------------------------------------------- cleaning
def tidy(df, value_col, area_col="area_sqft"):
    df = df.copy()
    df["city"] = std_city(df["city"])
    df["locality"] = title(df["locality"]).replace({"Nan": np.nan, "": np.nan})
    df = df.drop_duplicates()
    df = df.dropna(subset=["city", "locality", value_col, area_col])
    return df


def drop_outliers(df, metric, abs_lo, abs_hi, lo_mult=0.2, hi_mult=5):
    """Absolute bounds, then relative to each city's median (removes typos / luxury outliers)."""
    df = df[(df[metric] >= abs_lo) & (df[metric] <= abs_hi)].copy()
    med = df.groupby("city")[metric].transform("median")
    return df[(df[metric] >= lo_mult * med) & (df[metric] <= hi_mult * med)]


def build_sales():
    log("\n== SALES ==")
    loaders = [sale_gurgaon, sale_gurgaon_flats, sale_hyderabad, sale_ahmedabad, sale_delhi_magicbricks,
               sale_delhi_ncr, sale_bengaluru, sale_noida, sale_chennai, sale_mumbai, sale_maharashtra,
               sale_pune_scraped]
    frames = []
    for fn in loaders:
        try:
            d = fn()
        except Exception as e:  # keep going if one file has an unexpected format
            log(f"  [ERROR] {fn.__name__}: {e!r}")
            continue
        if d is not None:
            log(f"  {fn.__name__:<24} raw rows: {len(d)}")
            frames.append(d)
    df = pd.concat(frames, ignore_index=True)
    before = len(df)
    df = tidy(df, "price_lakh")
    df = df[(df["area_sqft"].between(200, 10000)) & (df["price_lakh"] >= 5)]
    df = drop_outliers(df, "price_per_sqft", 1500, 150000)
    df["bhk"] = df["bhk"].where(df["bhk"].between(1, 10))
    df = df.round({"price_lakh": 2, "area_sqft": 0, "price_per_sqft": 0})
    log(f"  total: {before} -> {len(df)} after cleaning")
    return df.reset_index(drop=True)


def build_rents():
    log("\n== RENTS ==")
    loaders = [rent_mumbai, rent_pune, rent_noida, rent_multi, rent_hyderabad, rent_chennai]
    frames = []
    for fn in loaders:
        try:
            d = fn()
        except Exception as e:
            log(f"  [ERROR] {fn.__name__}: {e!r}")
            continue
        if d is not None:
            log(f"  {fn.__name__:<24} raw rows: {len(d)}")
            frames.append(d)
    df = pd.concat(frames, ignore_index=True)
    before = len(df)
    df = tidy(df, "rent_monthly")
    df = df[(df["area_sqft"].between(150, 8000)) & (df["rent_monthly"].between(2000, 1_000_000))]
    df = drop_outliers(df, "rent_per_sqft", 5, 500)
    df["bhk"] = df["bhk"].where(df["bhk"].between(1, 10))
    df = df.round({"rent_monthly": 0, "area_sqft": 0, "rent_per_sqft": 1})
    log(f"  total: {before} -> {len(df)} after cleaning")
    return df.reset_index(drop=True)


# ----------------------------------------------------------------- RBI HPI + NHB
def quarter_end(label):
    """'Q1.2022-23' -> 2022-06-30 (Indian FY: Q1 = Apr-Jun)."""
    m = re.match(r"Q(\d)\.(\d{4})-(\d{2})", str(label).strip())
    if not m:
        return pd.NaT
    q, y = int(m.group(1)), int(m.group(2))
    month, year = {1: (6, y), 2: (9, y), 3: (12, y), 4: (3, y + 1)}[q]
    return pd.Timestamp(year=year, month=month, day=1) + pd.offsets.MonthEnd(0)


def build_hpi():
    log("\n== RBI HPI ==")
    p = find("House_Price_Index_Publication.xlsx")
    if p is None:
        return None
    raw = pd.read_excel(p, header=None)
    # locate the latest block: header row right after the line "Base Year : 2022-23"
    mask = raw[1].astype(str).str.contains("Base Year", na=False) & raw[1].astype(str).str.contains("2022-23", na=False)
    base_row = raw.index[mask][0]
    hdr = base_row + 2
    cities = raw.iloc[hdr, 2:].tolist()
    body = raw.iloc[hdr + 1:, 1:].copy()
    body = body[body[1].astype(str).str.startswith("Q")]
    body.columns = ["quarter"] + cities
    body = body.dropna(axis=1, how="all")
    long = body.melt(id_vars="quarter", var_name="city", value_name="hpi")
    long["hpi"] = pd.to_numeric(long["hpi"], errors="coerce")
    long = long.dropna(subset=["hpi"])
    long["provisional"] = long["quarter"].astype(str).str.contains(r"\(P\)")
    long["quarter"] = long["quarter"].astype(str).str.replace(r"\(P\)\**", "", regex=True).str.strip()
    long["quarter_end"] = long["quarter"].map(quarter_end)
    long["city"] = std_city(long["city"])
    long = long[["city", "quarter", "quarter_end", "hpi", "provisional"]].sort_values(["city", "quarter_end"])
    log(f"  {long['city'].nunique()} cities, {long['quarter'].nunique()} quarters "
        f"({long['quarter'].iloc[0]} .. {long.sort_values('quarter_end')['quarter'].iloc[-1]})")
    return long.round(2).reset_index(drop=True)


def build_nhb():
    log("\n== NHB RESIDEX ==")
    df = read("nhb_residex_carpet_area_prices_wide.csv")
    if df is None:
        return None
    cols = list(df.columns)
    df = df.rename(columns={cols[2]: "composite_price", cols[3]: "small", cols[4]: "medium", cols[5]: "large"})
    df["city"] = std_city(df["City"].replace({"Bengaluru": "Bengaluru"}))
    df["quarter_end"] = pd.to_datetime(df["Quarter"], format="%b %Y") + pd.offsets.MonthEnd(0)
    for c in ["composite_price", "small", "medium", "large"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.rename(columns={"Quarter": "quarter"})
    df = df[["city", "quarter", "quarter_end", "composite_price", "small", "medium", "large"]]
    df = df.sort_values(["city", "quarter_end"]).reset_index(drop=True)
    log(f"  {df['city'].nunique()} cities, {df['quarter'].nunique()} quarters")
    return df


# ----------------------------------------------------------------- main
def main():
    if not RAW.exists():
        sys.exit(f"Folder not found: {RAW.resolve()}  (run this from the backend/ folder)")
    sales, rents, hpi, nhb = build_sales(), build_rents(), build_hpi(), build_nhb()

    sales.to_csv(OUT / "sales.csv", index=False)
    rents.to_csv(OUT / "rents.csv", index=False)
    if hpi is not None:
        hpi.to_csv(OUT / "hpi.csv", index=False)
    if nhb is not None:
        nhb.to_csv(OUT / "nhb.csv", index=False)

    log("\n== FINAL: rows per city ==")
    summary = pd.DataFrame({
        "sale_rows": sales.groupby("city").size(),
        "median_price_per_sqft": sales.groupby("city")["price_per_sqft"].median(),
        "rent_rows": rents.groupby("city").size(),
        "median_rent_per_sqft": rents.groupby("city")["rent_per_sqft"].median(),
    }).sort_values("sale_rows", ascending=False)
    log(summary.round(1).to_string())
    (OUT / "report.txt").write_text("\n".join(LOG), encoding="utf-8")
    log(f"\nDone. Files saved in {OUT.resolve()}")


if __name__ == "__main__":
    main()