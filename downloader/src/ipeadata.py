"""Cliente IpeaData — séries setoriais longas (melhor esforço, não fatal).

O host é lento/instável; cada série usa timeout curto e falha sem derrubar
o pipeline. Os dados são "acumulado 12 meses" de IPCA por setor.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import requests

from .io_utils import raw_cache_path, read_cached, write_json

URL = "http://www.ipeadata.gov.br/api/odata4/ValoresSerie(SERCODIGO=%27{code}%27)?$format=json"


def download_ipeadata(series_cfg: dict, cfg: dict, dirs: dict,
                      force: bool = False, max_age_days: int | None = None) -> dict:
    max_age_days = cfg.get("cache_max_age_days") if max_age_days is None else max_age_days
    out: dict = {}
    for key, spec in series_cfg.items():
        path = raw_cache_path(dirs, "ipeadata", key)
        cached, fresh = read_cached(path, max_age_days)
        if cached is not None and fresh and not force:
            out[key] = cached
            continue
        try:
            r = requests.get(URL.format(code=spec["code"]),
                             headers={"User-Agent": "python-requests"}, timeout=15)
            if r.status_code != 200:
                out[key] = {"key": key, "error": f"HTTP {r.status_code}"}
                continue
            vals = r.json().get("value", [])
            payload = {
                "key": key,
                "code": spec["code"],
                "name": spec["name"],
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "values": [{"data": v["VALDATA"][:10], "valor": v["VALVALOR"]} for v in vals],
            }
            write_json(path, payload)
            out[key] = payload
        except Exception as e:  # noqa: BLE001
            out[key] = {"key": key, "error": f"{type(e).__name__}: {e}"}
    return out


def ipeadata_to_frame(payloads: dict) -> pd.DataFrame:
    rows = []
    for key, payload in payloads.items():
        if "error" in payload:
            continue
        for v in payload.get("values", []):
            rows.append({"source": "ipeadata", "series": key,
                         "ref_date": v["data"], "value": v["valor"]})
    return pd.DataFrame(rows)
