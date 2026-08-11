"""Hiato do produto por filtro HP (aproximação da abordagem usada em réplicas)."""
from __future__ import annotations

import pandas as pd
from statsmodels.tsa.filters.hp_filter import hpfilter


def hp_gap(l_ibc: pd.Series, lam: float = 1600) -> pd.Series:
    cycle, trend = hpfilter(l_ibc, lamb=lam)
    return cycle * 100  # %


def add_gap(q: pd.DataFrame, lam: float = 1600) -> pd.DataFrame:
    q["gap"] = hp_gap(q["l_ibc"].dropna(), lam)
    q["gap"] = q["gap"].reindex(q.index)
    return q
