"""Hiato do produto por estado-espaço (múltiplos indicadores).

Estágio 1 (gap): fator comum do log(IBC-Br), PIB trimestral (crescimento YoY)
e desocupação (sinal invertido) via DynamicFactor (fator comum AR(2)).
O fator é calibrado para a escala do hiato em % pela regressão sobre o
ciclo de Kalman univariado do log(IBC-Br) (mesma unidade usada nas equações).

Estágio 2: demais equações condicionadas a esse hiato.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.statespace.dynamic_factor import DynamicFactor
from statsmodels.tsa.statespace.structural import UnobservedComponents


def kalman_gap(l_ibc: pd.Series, ar_order: int = 2) -> pd.Series:
    """Ciclo (hiato, em %) da decomposição tendência local + ciclo AR do log(IBC-Br)."""
    y = l_ibc.dropna()
    model = UnobservedComponents(
        y, level="llevel", cycle=True, stochastic_cycle=True,
        damped_cycle=True, cycle_period_bounds=(1.5, 12),
    )
    res = model.fit(disp=False)
    cycle = res.states.smoothed.iloc[:, res.model.k_states - 1] * 100
    return cycle.reindex(l_ibc.index)


def multi_indicator_gap(q: pd.DataFrame) -> pd.DataFrame:
    """Hiato multi-indicador (IBC-Br + PIB + desocupação).

    Retorna DataFrame com 'gap' (fator comum calibrado em % do hiato).
    """
    y = pd.DataFrame({
        "dl_ibc": q["l_ibc"].diff(),
        "pib_yoy": q.get("pib_yoy"),
        "desoc_neg": -q.get("desocupacao"),
    }).dropna()
    if len(y) < 40:
        return q

    mod = DynamicFactor(y, k_factors=1, factor_order=2, error_cov_type="diagonal")
    try:
        res = mod.fit(disp=False)
        factor = res.factors.smoothed.iloc[:, 0]
    except Exception:  # noqa: BLE001 - fallback ao filtro univariado
        q["gap"] = kalman_gap(q["l_ibc"])
        return q.loc[q["gap"].notna()]

    # calibra escala: regressa o fator sobre o ciclo de Kalman (unidade em %)
    ref = kalman_gap(q["l_ibc"])
    d = pd.DataFrame({"gap": ref, "f": factor}).dropna()
    if len(d) < 20:
        q["gap"] = ref
        return q.loc[q["gap"].notna()]
    beta, alpha = np.polyfit(d["f"], d["gap"], 1)
    q["gap"] = (alpha + beta * factor).reindex(q.index)
    q = q.loc[q["gap"].notna()]
    return q


def add_gap_kalman(q: pd.DataFrame) -> pd.DataFrame:
    gap = kalman_gap(q["l_ibc"])
    q["gap"] = gap.reindex(q.index)
    q = q.loc[q["gap"].notna()]
    return q


def add_gap_multi(q: pd.DataFrame) -> pd.DataFrame:
    return multi_indicator_gap(q)
