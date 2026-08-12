"""Carga de snapshot point-in-time e montagem da base trimestral.

Lê data/snapshots/pt_<vintage>/data.parquet e produz um DataFrame trimestral
indexado por data de fim de trimestre com as variáveis do modelo.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
SNAPSHOTS = ROOT / "downloader" / "data" / "snapshots"

W_LIVRES = 0.76


def load_snapshot(vintage: str = "pt_2026Q2") -> pd.DataFrame:
    path = SNAPSHOTS / vintage / "data.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Snapshot não encontrado: {path}")
    return pd.read_parquet(path)


def _compound(series, window) -> pd.Series:
    return (series.rolling(window).apply(
        lambda x: np.prod(1 + np.array(x) / 100.0) - 1, raw=True)) * 100


def _compound_group(x: pd.Series) -> float:
    x = x.dropna()
    if len(x) < 3:
        return np.nan
    return (np.prod(1 + np.asarray(x) / 100.0) - 1) * 100


def _expectations_quarterly(focus: pd.DataFrame) -> pd.Series:
    """E_t[pi_{t+1}] a partir das expectativas mensais do Focus (IPCA).

    Para cada trimestre de pesquisa (t), compõe a expectativa dos 3 meses do
    trimestre-alvo (t+1), usando a última pesquisa conhecida em t.
    """
    f = focus[(focus["series"] == "focus_mensais")].copy()
    f = f.dropna(subset=["value"])
    f["survey_date"] = pd.to_datetime(f["survey_date"], format="mixed", dayfirst=True)
    f["target_month"] = f["ref_date"]
    f["sq"] = f["survey_date"].dt.to_period("Q")
    f = f.sort_values("survey_date")
    lastm = f.groupby(["sq", "target_month"])["value"].last()
    mexp = lastm.unstack("target_month")  # índice=trimestre da pesquisa, colunas=mês-alvo

    # compõe os meses em trimestres-alvo (loop explícito evita quirk do groupby axis=1)
    qexp = {}
    quarter_keys = mexp.columns.to_period("Q")
    for q in sorted(set(quarter_keys)):
        cols = mexp.columns[quarter_keys == q]
        qexp[q] = mexp[cols].apply(_compound_group, axis=1)
    qexp = pd.DataFrame(qexp).astype(float)

    e_next = {}
    for sq in qexp.index:
        nxt = sq + 1
        if nxt in qexp.columns and pd.notna(qexp.loc[sq, nxt]):
            e_next[sq] = float(qexp.loc[sq, nxt])
    out = pd.Series(e_next, name="e_pi_next", dtype=float)
    out.index = out.index.to_timestamp(how="end")
    return out


def build_quarterly(df: pd.DataFrame) -> pd.DataFrame:
    sgs = df[df["source"] == "sgs"].copy()
    focus = df[(df["source"] == "focus") & (df["indicador"] == "IPCA")].copy()

    sgs_keys = ["ipca", "ipca_livres", "ipca_admin", "selic_over_aa",
                "cambio_media", "ibc_br_saz", "fiscal_prim_12m",
                "icbr_indice", "icbr_var", "nucleo_ex0"]
    m = sgs[sgs["series"].isin(sgs_keys)][["ref_date", "series", "value"]]
    m = m.pivot(index="ref_date", columns="series", values="value").sort_index()

    # Brent (FRED, mensal, US$/barril)
    brent = df[(df["source"] == "fred") & (df["series"] == "brent")][["ref_date", "value"]]
    brent = brent.set_index("ref_date")["value"].astype(float).groupby(level=0).last()
    m["brent"] = brent.reindex(m.index)

    # IC-Br mensal (% var): 28451 onde houver; senão deriva do índice 28515.
    icbr = m["icbr_var"].copy()
    deriv = m["icbr_indice"].pct_change(fill_method=None) * 100
    icbr = icbr.where(icbr.notna(), deriv)
    m["icbr"] = icbr

    # ONI (NOAA, trimestral, ref = fim do mês final da estação) espalhado sobre os meses
    oni = df[(df["source"] == "noaa")][["ref_date", "value"]].rename(columns={"value": "oni"})
    oni = oni.set_index("ref_date")["oni"]
    oni = oni.groupby(level=0).last()
    m_idx = m.index.to_period("M")
    m["oni"] = oni.set_axis(oni.index.to_period("M")).reindex(m_idx).ffill().to_numpy()

    # Fed Funds (FRED, mensal)
    ff = df[(df["source"] == "fred") & (df["series"] == "fedfunds_monthly")][["ref_date", "value"]]
    ff = ff.set_index("ref_date")["value"].groupby(level=0).last()
    m["ff"] = ff.reindex(m.index)

    # Hiato mundial proxy: hiato do produto dos EUA (FRED GDPC1/GDPPOT, trimestral)
    us = df[df["source"] == "fred"].copy()
    us = us[us["series"].isin(["us_gdp", "us_gdp_pot"])][["ref_date", "series", "value"]]
    us_gap_q = None
    if len(us):
        us = us.pivot(index="ref_date", columns="series", values="value").sort_index()
        us = us.astype(float)
        us_gap = (us["us_gdp"] / us["us_gdp_pot"] - 1.0) * 100
        us_gap = us_gap[~us_gap.index.duplicated()]
        us_gap_q = us_gap.resample("QE").last()

    q = m.resample("QE").agg({
        "ipca": _compound_group, "ipca_livres": _compound_group,
        "ipca_admin": _compound_group,
        "selic_over_aa": "mean", "cambio_media": "mean", "ibc_br_saz": "mean",
        "fiscal_prim_12m": "mean", "oni": "mean", "icbr": _compound_group,
        "ff": "mean", "nucleo_ex0": _compound_group, "brent": "mean",
    })
    q.columns = ["pi", "pi_l", "pi_a", "selic", "cambio", "ibc_br", "fiscal",
                 "oni", "pi_com", "ff", "nucleo", "brent"]
    q = q.dropna(subset=["pi"])
    q["pi4"] = _compound(q["pi"], 4)
    q["pi4_l"] = _compound(q["pi_l"], 4)
    q["pi4_a"] = _compound(q["pi_a"], 4)
    q["dln_cambio"] = np.log(q["cambio"]).diff() * 100
    q["l_ibc"] = np.log(q["ibc_br"])
    if us_gap_q is not None:
        us_idx = q.index.to_period("Q").to_timestamp(how="end").normalize()
        q["us_gap"] = us_gap_q.reindex(us_idx)
        q["us_gap"] = q["us_gap"].ffill()

    # SIDRA trimestrais (PIB YoY e desocupação) alinhadas ao fim do trimestre
    def _quarter_series(df: pd.DataFrame, series_key: str) -> pd.Series:
        s = df[(df["source"] == "sidra") & (df["series"] == series_key)][["ref_date", "value"]]
        s = s.set_index("ref_date")["value"].astype(float)
        s.index = pd.to_datetime(s.index)
        s = s.groupby(s.index.to_period("Q")).last()
        s.index = s.index.to_timestamp(how="end").normalize()
        return s

    for col, key in [("pib_yoy", "t5932_v6561"), ("desocupacao", "t4099_v4099")]:
        q[col] = _quarter_series(df, key).reindex(q.index)

    e = _expectations_quarterly(focus)
    e.index = e.index.to_period("Q")
    q["e_pi_next"] = e.reindex(q.index.to_period("Q")).to_numpy()
    q = q.dropna(subset=["e_pi_next"])
    q["period"] = q.index.to_period("Q").astype(str)
    return q
