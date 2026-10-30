"""Loads the cleaned CSVs once and keeps them in memory."""
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent.parent
SEARCH_DIRS = [BASE / "data" / "processed", BASE / "data" / "raw"]


def _find(name: str) -> Path:
    for d in SEARCH_DIRS:
        p = d / name
        if p.exists():
            return p
    raise FileNotFoundError(f"{name} not found in {[str(d) for d in SEARCH_DIRS]}")


@dataclass
class Data:
    sales: pd.DataFrame
    rents: pd.DataFrame
    hpi: pd.DataFrame
    nhb: pd.DataFrame
    catalysts: pd.DataFrame


@lru_cache(maxsize=1)
def load_data() -> Data:
    hpi = pd.read_csv(_find("hpi.csv"), parse_dates=["quarter_end"])
    nhb = pd.read_csv(_find("nhb.csv"), parse_dates=["quarter_end"])
    return Data(
        sales=pd.read_csv(_find("sales.csv")),
        rents=pd.read_csv(_find("rents.csv")),
        hpi=hpi.sort_values(["city", "quarter_end"]),
        nhb=nhb.sort_values(["city", "quarter_end"]),
        catalysts=pd.read_csv(_find("catalysts.csv")).set_index("city", drop=False),
    )