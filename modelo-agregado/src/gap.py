"""Hiato do produto: filtro HP (aproximação) ou estado-espaço (filtro de Kalman)."""
from __future__ import annotations

import pandas as pd
from statsmodels.tsa.filters.hp_filter import hpfilter
from statsmodels.tsa.statespace.structural import UnobservedComponents


def hp_gap(l_ibc: pd.Series, lam: float = 1600) -> pd.Series:
    cycle, trend = hpfilter(l_ibc, lamb=lam)
    return cycle * 100  # %


def add_gap(q: pd.DataFrame, lam: float = 1600) -> pd.DataFrame:
    q["gap"] = hp_gap(q["l_ibc"].dropna(), lam)
    q["gap"] = q["gap"].reindex(q.index)
    return q


def kalman_gap(l_ibc: pd.Series) -> pd.Series:
    """Ciclo (hiato, em %) da decomposição tendência local + ciclo AR (Kalman)."""
    y = l_ibc.dropna()
    model = UnobservedComponents(
        y, level="llevel", cycle=True, stochastic_cycle=True,
        damped_cycle=True, cycle_period_bounds=(1.5, 12),
    )
    res = model.fit(disp=False)
    cycle = res.states.smoothed.iloc[:, res.model.k_states - 1] * 100
    return pd.Series(cycle.values, index=y.index)


def add_gap_kalman(q: pd.DataFrame) -> pd.DataFrame:
    q["gap"] = kalman_gap(q["l_ibc"]).reindex(q.index)
    return q.loc[q["gap"].notna()]
