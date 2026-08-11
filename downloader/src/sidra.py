"""Cliente IBGE/SIDRA — IPCA mensal por subitem (tabela 7060)."""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from .io_utils import http_get, raw_cache_path, read_cached, write_json

BASE = "https://apisidra.ibge.gov.br/values/t/{table}/n1/all/v/{var}/p/{periods}/c315/all?formato=json"


def _month_period(year: int, month: int) -> str:
    return f"{year:04d}{month:02d}"


def _chunk_periods(spec: dict, cfg: dict) -> list[str]:
    """Lista de blocos de períodos (anos em grupos de chunk_years)."""
    chunk = spec.get("chunk_years", 5)
    # Tabela 7060 (classificação atual de subitens) só tem dados de 2020 em diante.
    now = datetime.now()
    current_year = now.year
    start_year = 2020
    blocks = []
    for y in range(start_year, current_year + 1, chunk):
        end = min(y + chunk - 1, current_year)
        months = []
        for yy in range(y, end + 1):
            last = 12 if yy < current_year else now.month
            for m in range(1, last + 1):
                months.append(_month_period(yy, m))
        blocks.append(",".join(months))
    return blocks


def download_sidra(spec: dict, cfg: dict, dirs: dict, force: bool = False,
                   max_age_days: int | None = None) -> dict:
    max_age_days = cfg.get("cache_max_age_days") if max_age_days is None else max_age_days
    path = raw_cache_path(dirs, "sidra", "ipca_subitem")
    cached, fresh = read_cached(path, max_age_days)
    if cached is not None and fresh and not force:
        return cached

    table = spec["table"]
    var = spec["variable"]
    wvar = spec.get("weight_variable")
    all_rows: list[dict] = []
    for block in _chunk_periods(spec, cfg):
        for v in [var] + ([wvar] if wvar else []):
            url = BASE.format(table=table, var=v, periods=block)
            rows = http_get(url, cfg=cfg, expect_json=True)
            for row in rows:
                ref = row.get("D3C", "")
                if "D4C" in row and ref.isdigit() and len(ref) == 6:
                    all_rows.append(
                        {
                            "ref_date": ref,
                            "item_code": row["D4C"],
                            "item_name": row["D4N"],
                            "variable": v,
                            "value": row["V"],
                        }
                    )

    payload = {
        "table": table,
        "variable": var,
        "weight_variable": wvar,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "values": all_rows,
    }
    write_json(path, payload)
    return payload


def sidra_to_frame(payload: dict) -> pd.DataFrame:
    rows = [
        {
            "source": "sidra",
            "series": "ipca_subitem",
            "item_code": v["item_code"],
            "item_name": v["item_name"],
            "variable": v.get("variable"),
            "ref_date": v["ref_date"],
            "value": v["value"],
        }
        for v in payload.get("values", [])
    ]
    return pd.DataFrame(rows)
