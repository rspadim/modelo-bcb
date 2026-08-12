"""Cliente IBGE/SIDRA — IPCA mensal por subitem (tabela 7060)."""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from .io_utils import http_get, raw_cache_path, read_cached, write_json

BASE = "https://apisidra.ibge.gov.br/values/t/{table}/n1/all/v/{var}/p/{periods}/c315/all?formato=json"
BASE_Q = "https://apisidra.ibge.gov.br/values/t/{table}/n1/all/v/{var}/p/{periods}"


def _month_period(year: int, month: int) -> str:
    return f"{year:04d}{month:02d}"


def _quarter_ref(period_code: str) -> str:
    """'202301' (1º trimestre 2023) -> '20230330' (fim do trimestre)."""
    y = int(period_code[:4])
    q = int(period_code[4:6])
    month = q * 3
    day = 31 if month == 12 else 30
    return f"{y:04d}{month:02d}{day:02d}"


def _quarter_blocks(start_year: int, end_year: int, chunk: int = 5) -> list[str]:
    """Blocos de períodos trimestrais (YYYYQQ), em grupos de anos."""
    blocks = []
    for y in range(start_year, end_year + 1, chunk):
        qs = []
        for yy in range(y, min(y + chunk - 1, end_year) + 1):
            for qq in range(1, 5):
                qs.append(f"{yy:04d}{qq:02d}")
        blocks.append(",".join(qs))
    return blocks


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


def download_sidra_quarterly(spec: dict, cfg: dict, dirs: dict, force: bool = False,
                             max_age_days: int | None = None) -> dict:
    """Baixa tabela trimestral genérica do SIDRA.

    Aceita classificação/categoria opcionais (ex.: PIB 5932, var 6561,
    classif 11255, categoria 90707). ref_date = fim do trimestre (YYYYMMDD)
    para que o lag PIT conte a partir do fim do período.
    """
    max_age_days = cfg.get("cache_max_age_days") if max_age_days is None else max_age_days
    table = spec["table"]
    var = spec["variable"]
    key = spec.get("key", f"t{table}_v{var}")
    path = raw_cache_path(dirs, "sidra", key)
    cached, fresh = read_cached(path, max_age_days)
    if cached is not None and fresh and not force:
        return cached

    start_year = spec.get("start_year", 2012)
    now = datetime.now()
    end_year = now.year
    target_cat = str(spec.get("category", ""))

    all_rows: list[dict] = []
    for block in _quarter_blocks(start_year, end_year):
        url = BASE_Q.format(table=table, var=var, periods=block)
        if spec.get("classification"):
            url += f"/c{spec['classification']}/all"
        url += "?formato=json"
        rows = http_get(url, cfg=cfg, expect_json=True)
        for row in rows:
            d2c = row.get("D2C", "")
            if d2c and str(d2c) != str(var):
                continue
            d4c = row.get("D4C", "")
            if target_cat and str(d4c) != target_cat:
                continue
            period = row.get("D3C", "")
            if not (period.isdigit() and len(period) == 6):
                continue
            all_rows.append({
                "ref_date": _quarter_ref(period),
                "value": row.get("V", ""),
            })

    payload = {
        "table": table,
        "variable": var,
        "key": key,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "values": all_rows,
    }
    write_json(path, payload)
    return payload


def sidra_quarterly_to_frame(payload: dict) -> pd.DataFrame:
    key = payload.get("key", f"t{payload.get('table')}_v{payload.get('variable')}")
    rows = [
        {
            "source": "sidra",
            "series": key,
            "ref_date": v["ref_date"],
            "value": v["value"],
        }
        for v in payload.get("values", [])
    ]
    return pd.DataFrame(rows)
