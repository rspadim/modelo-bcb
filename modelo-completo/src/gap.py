"""Hiato do produto por estado-espaço (filtro de Kalman), em 2 estágios.

Estágio 1: filtro no log do IBC-Br sazonal com tendência local + ciclo AR(2)
(UnobservedComponents do statsmodels); o ciclo é a medida de hiato.
Estágio 2: as demais equações são estimadas condicionadas a esse hiato.
"""
from __future__ import annotations

import pandas as pd
from statsmodels.tsa.statespace.structural import UnobservedComponents


def kalman_gap(l_ibc: pd.Series, ar_order: int = 2) -> pd.Series:
    """Retorna o ciclo (hiato, em %) da decomposição tendência local + ciclo AR."""
    y = l_ibc.dropna()
    model = UnobservedComponents(
        y, level="llevel", cycle=True, stochastic_cycle=True,
        damped_cycle=True, cycle_period_bounds=(1.5, 12),
    )
    res = model.fit(disp=False)
    cycle = res.states.smoothed.iloc[:, res.model.k_states - 1] * 100
    # corrige sinal se necessário (hiato = componente cíclico de log(atividade))
    return cycle.reindex(l_ibc.index)


def add_gap_kalman(q: pd.DataFrame) -> pd.DataFrame:
    gap = kalman_gap(q["l_ibc"])
    q["gap"] = gap.reindex(q.index)
    q = q.loc[q["gap"].notna()]
    return q
