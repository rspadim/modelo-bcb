"""Motor point-in-time: calcula `available_from` de cada observação."""
from __future__ import annotations

import re

import pandas as pd

from .io_utils import load_yaml


def _parse_date(value) -> pd.Timestamp:
    if pd.isna(value):
        return pd.NaT
    s = str(value).strip()
    if s.isdigit() and len(s) in (6, 8):  # SIDRA YYYYMM / datacompleta YYYYMMDD
        if len(s) == 8:
            return pd.to_datetime(s, format="%Y%m%d")
        return pd.to_datetime(s, format="%Y%m")
    if s.isdigit() and len(s) == 4:  # ano isolado (Focus anuais)
        return pd.Timestamp(year=int(s), month=12, day=31)
    # SGS/outros no padrão dd/mm/aaaa -> dayfirst=True
    return pd.to_datetime(s, format="mixed", dayfirst=True)


def _parse_focus_ref(series: str, value) -> pd.Timestamp:
    """DataReferencia do Focus depende do horizonte:
    - trimestrais: '3/2021' = trimestre (mês do fim do trimestre)
    - mensais:     '03/2021' = mês
    - anuais:      '2021'    = ano
    """
    if pd.isna(value):
        return pd.NaT
    s = str(value).strip()
    if series == "focus_trimestrais":
        m = re.match(r"^(\d{1,2})/(\d{4})$", s)
        if m:
            q, y = int(m.group(1)), int(m.group(2))
            return pd.Timestamp(year=y, month=q * 3, day=30)
    if series == "focus_mensais":
        m = re.match(r"^(\d{1,2})/(\d{4})$", s)
        if m:
            mo, y = int(m.group(1)), int(m.group(2))
            return pd.Timestamp(year=y, month=mo, day=1)
    return _parse_date(s)


def _period_end(ref: pd.Timestamp) -> pd.Timestamp:
    if ref is pd.NaT or pd.isna(ref):
        return pd.NaT
    return ref + pd.offsets.MonthEnd(0)


def apply_availability(df: pd.DataFrame, avail: dict) -> pd.DataFrame:
    """Adiciona coluna `available_from` (datetime) a um DataFrame longo
    com colunas: source, series, ref_date."""
    out = df.copy()
    is_focus = out["source"] == "focus"
    out.loc[is_focus, "ref_date"] = out.loc[is_focus].apply(
        lambda r: _parse_focus_ref(r["series"], r["ref_date"]), axis=1
    )
    out.loc[~is_focus, "ref_date"] = out.loc[~is_focus, "ref_date"].map(_parse_date)

    default = avail.get("default_lag_days", 0)
    series_lags = {k: v.get("lag_days", default) for k, v in avail.get("series", {}).items()}
    source_defaults = avail.get("source_defaults", {})

    def lag_for(row) -> int:
        lag = series_lags.get(row["series"])
        if lag is not None:
            return lag
        src = source_defaults.get(row["source"], {})
        return src.get("lag_days", default)

    lags = out.apply(lag_for, axis=1)
    out["_lag_days"] = lags

    mask_focus = out["source"] == "focus"
    out.loc[mask_focus, "available_from"] = pd.to_datetime(
        out.loc[mask_focus, "survey_date"], format="mixed", dayfirst=True, errors="coerce"
    )
    not_focus = ~mask_focus
    pe = out.loc[not_focus, "ref_date"].map(_period_end)
    out.loc[not_focus, "available_from"] = pe + pd.to_timedelta(
        out.loc[not_focus, "_lag_days"], unit="D"
    )
    out = out.drop(columns=["_lag_days"])
    return out


def quarter_cutoff(quarter: str) -> pd.Timestamp:
    """'2026Q2' -> Timestamp(2026-06-30)."""
    year = int(quarter[:4])
    q = int(quarter[5])
    month_end = {1: 3, 2: 6, 3: 9, 4: 12}[q]
    return pd.Timestamp(year=year, month=month_end, day=30)


def quarter_key(ts: pd.Timestamp) -> str:
    return f"{ts.year}Q{(ts.month - 1) // 3 + 1}"
