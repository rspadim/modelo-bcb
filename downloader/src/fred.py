"""Cliente FRED (Fed) — melhor esforço. Pode ficar indisponível (não fatal)."""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import requests

from .io_utils import raw_cache_path, read_cached, write_json

URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"


def download_fred(series_cfg: dict, cfg: dict, dirs: dict,
                  force: bool = False, max_age_days: int | None = None) -> dict:
    max_age_days = cfg.get("cache_max_age_days") if max_age_days is None else max_age_days
    out: dict = {}
    for key, spec in series_cfg.items():
        path = raw_cache_path(dirs, "fred", key)
        cached, fresh = read_cached(path, max_age_days)
        if cached is not None and fresh and not force:
            out[key] = cached
            continue
        try:
            r = requests.get(URL, params={"id": spec["id"], "cosd": "1996-01-01"},
                             headers={"User-Agent": "python-requests"}, timeout=20)
            if r.status_code != 200:
                out[key] = {"key": key, "id": spec["id"], "error": f"HTTP {r.status_code}"}
                continue
            lines = r.text.splitlines()
            values = [l.split(",") for l in lines[1:] if l.strip()]
            payload = {
                "key": key,
                "id": spec["id"],
                "name": spec["name"],
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "values": [{"data": v[0], "valor": v[1]} for v in values],
            }
            write_json(path, payload)
            out[key] = payload
        except Exception as e:  # noqa: BLE001
            out[key] = {"key": key, "id": spec["id"], "error": str(e)}
    return out


def fred_to_frame(payloads: dict) -> pd.DataFrame:
    rows = []
    for key, payload in payloads.items():
        if "error" in payload:
            continue
        for v in payload.get("values", []):
            rows.append(
                {
                    "source": "fred",
                    "series": key,
                    "ref_date": v["data"],
                    "value": v["valor"],
                }
            )
    return pd.DataFrame(rows)
