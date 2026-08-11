"""Cliente BCB/SGS (BCData)."""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from .io_utils import http_get, raw_cache_path, read_cached, write_json

BASE = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados"


def _fetch_code(code: int, cfg: dict) -> list[dict]:
    url = BASE.format(code=code)
    data = http_get(url, params={"formato": "json"}, cfg=cfg, expect_json=True)
    if not isinstance(data, list):
        raise RuntimeError(f"SGS {code}: resposta inesperada")
    return data


def download_sgs(series: dict[str, dict], cfg: dict, dirs: dict, force: bool = False,
                 max_age_days: int | None = None) -> dict[str, dict]:
    """Baixa (ou lê do cache) cada série SGS. Retorna {key: payload}."""
    max_age_days = cfg.get("cache_max_age_days") if max_age_days is None else max_age_days
    out: dict[str, dict] = {}
    errors: dict[str, str] = {}
    for key, spec in series.items():
        code = spec["code"]
        path = raw_cache_path(dirs, "sgs", str(code))
        cached, fresh = read_cached(path, max_age_days)
        if cached is not None and fresh and not force:
            out[key] = cached
            continue
        try:
            values = _fetch_code(code, cfg)
            payload = {
                "key": key,
                "code": code,
                "name": spec["name"],
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "values": values,
            }
            write_json(path, payload)
            out[key] = payload
        except Exception as e:  # noqa: BLE001
            errors[key] = f"{type(e).__name__}: {e}"
    if errors:
        print(f"SGS: falhas em {len(errors)} séries -> {errors}")
    return out, errors


def sgs_to_frame(payloads: dict[str, dict]) -> pd.DataFrame:
    rows = []
    for key, payload in payloads.items():
        for v in payload["values"]:
            rows.append(
                {
                    "source": "sgs",
                    "series": key,
                    "code": payload["code"],
                    "name": payload["name"],
                    "ref_date": v["data"],
                    "value": v["valor"],
                }
            )
    return pd.DataFrame(rows)
