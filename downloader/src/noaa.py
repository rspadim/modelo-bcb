"""Cliente NOAA — ONI (Oceanic Niño Index)."""
from __future__ import annotations

import io
from datetime import datetime, timezone

import pandas as pd
import requests

from .io_utils import raw_cache_path, read_cached, write_json

URL = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"

_SEASONS = {
    "DJF": (12, 1, 2), "JFM": (1, 2, 3), "FMA": (2, 3, 4), "MAM": (3, 4, 5),
    "AMJ": (4, 5, 6), "MJJ": (5, 6, 7), "JJA": (6, 7, 8), "JAS": (7, 8, 9),
    "ASO": (8, 9, 10), "SON": (9, 10, 11), "OND": (10, 11, 12), "NDJ": (11, 12, 1),
}


def _season_end(season: str, year: int) -> tuple[int, int]:
    months = _SEASONS[season]
    last = max(months)
    end_year = year
    if last <= 2:
        end_year = year + 1
    return end_year, last


def download_noaa(cfg: dict, dirs: dict, force: bool = False,
                  max_age_days: int | None = None) -> dict:
    max_age_days = cfg.get("cache_max_age_days") if max_age_days is None else max_age_days
    path = raw_cache_path(dirs, "noaa", "oni")
    cached, fresh = read_cached(path, max_age_days)
    if cached is not None and fresh and not force:
        return cached

    r = requests.get(URL, timeout=30)
    r.raise_for_status()
    payload = {
        "source": "noaa",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "text": r.text,
    }
    write_json(path, payload)
    return payload


def noaa_to_frame(payload: dict) -> pd.DataFrame:
    df = pd.read_csv(io.StringIO(payload.get("text", "")), sep=r"\s+")
    rows = []
    for _, row in df.iterrows():
        season = str(row["SEAS"]).strip()
        year = int(row["YR"])
        ey, em = _season_end(season, year)
        rows.append(
            {
                "source": "noaa",
                "series": "oni",
                "ref_date": f"{ey:04d}-{em:02d}-01",
                "value": row["ANOM"],
                "total": row["TOTAL"],
            }
        )
    return pd.DataFrame(rows)
