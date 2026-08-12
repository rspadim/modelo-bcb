"""Equações do modelo BCB (RI dez/2021) — IS completa e expectativas com componente
consistente com o modelo. Estimação bayesiana com os priors/suportes publicados.

IS (RI dez/2021): gap_t = c + β1·gap_{t-1} + β2·(r̄ − r_{t-1}) + β3·fisc_cc_t
                          + β4·incert_t + β5·hiato_mundial_t + ε
  - (r̄ − r) : juro real gap (r = Selic − 4·Eπ; r̄ = neutra 5%) — β2 ∈ [0,2]
  - fisc_cc : resultado primário % PIB ciclo-corrigido (desvio HP da tendência) — Beta
  - incert  : incerteza (proxy: desvio-padrão rolante de Δcâmbio) — Beta
  - us_gap  : hiato mundial (proxy: hiato do produto dos EUA, FRED) — ∈ [0,1]

Expectativas (RI): Eπ_t = φ1·Eπ_{t-1} + φ2·Eπ_consistente + φ3·π_{t-1}   (φi ∈ [0,1])
  - Eπ_consistente é a expectativa do próprio modelo; na estimação usa-se o realizado
    π_{t+1} como proxy (em média a expectativa consistente ≈ realizado).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm

try:
    import pymc as pm
except ImportError:  # pragma: no cover
    pm = None


def _hp_cycle(s: pd.Series, lam: float = 1600) -> pd.Series:
    """Componente cíclico (desvio da tendência) via filtro HP."""
    cycle, _ = sm.tsa.filters.hpfilter(s.dropna(), lamb=lam)
    return cycle


def estimate_is_bcb(q: pd.DataFrame, start: str = "2003Q4", end: str = "2019Q4",
                    r_neutral: float = 5.0, bayes: bool = True, draws: int = 800,
                    tune: int = 400) -> dict:
    """IS do RI dez/2021 (fiscal ciclo-corrigido + incerteza + hiato mundial)."""
    d = q.copy()
    d["rreal"] = d["selic"] - 4 * d["e_pi_next"]
    d["rreal_gap"] = r_neutral - d["rreal"]                # juro real gap (β2 ∈ [0,2])
    d = d.loc[start:end].copy()
    # fisc_cc/incert calculados DENTRO da janela: o filtro HP é bilateral (suavizado) —
    # calculá-lo sobre a série cheia da vintage contaminaria a janela com dados futuros.
    d["fisc_cc"] = _hp_cycle(d["fiscal"])                 # ciclo-corrigido (desvio)
    d["incert"] = d["dln_cambio"].rolling(12, min_periods=8).std()  # proxy incerteza
    sub = d.dropna(subset=["gap", "gap_1", "rreal_gap", "fisc_cc", "incert", "us_gap"])
    X = sub[["gap_1", "rreal_gap", "fisc_cc", "incert", "us_gap"]]
    y = sub["gap"]

    if not bayes or pm is None:
        lo = [-2.0, 0.0, 0.0, 0.0, 0.0]
        hi = [2.0, 2.0, 1.0, 1.0, 1.0]
        from scipy.optimize import lsq_linear
        res = lsq_linear(X.values, y.values, bounds=(lo, hi))
        coef = res.x
        return {"params": dict(zip(X.columns, coef)), "n": int(len(sub)), "bayes": False}

    with pm.Model():
        b1 = pm.Uniform("gap_1", -2, 2)
        b2 = pm.Uniform("rreal_gap", 0, 2)
        b3 = pm.Beta("fisc_cc", 3, 100)
        b4 = pm.Beta("incert", 3, 80)
        b5 = pm.Uniform("us_gap", 0, 1)
        mu = b1 * X["gap_1"] + b2 * X["rreal_gap"] + b3 * X["fisc_cc"] \
            + b4 * X["incert"] + b5 * X["us_gap"]
        sigma = pm.HalfNormal("sigma", 2.0)
        pm.Normal("y", mu=mu, sigma=sigma, observed=y.values)
        trace = pm.sample(draws=draws, tune=tune, chains=2, cores=2,
                          random_seed=42, progressbar=False)

    def post(name):
        return float(trace.posterior[name].values.mean())

    return {"params": {k: post(k) for k in X.columns}, "n": int(len(sub)),
            "bayes": True, "_trace": trace}


def estimate_expect_bcb(q: pd.DataFrame, start: str = "2003Q4", end: str = "2019Q4",
                        bayes: bool = True, draws: int = 800, tune: int = 400) -> dict:
    """Equação de expectativas do RI dez/2021 (inércia + consistente + passada)."""
    d = q.copy()
    d["e_prev"] = d["e_pi_next"].shift(1)
    d["pi_prev"] = d["pi"].shift(1)
    d["e_consistent"] = d["pi"].shift(-1)  # proxy: realizado (expectativa consistente)
    d = d.loc[start:end].copy()
    sub = d.dropna(subset=["e_pi_next", "e_prev", "pi_prev", "e_consistent"])
    X = sub[["e_prev", "e_consistent", "pi_prev"]]
    y = sub["e_pi_next"]

    if not bayes or pm is None:
        from scipy.optimize import lsq_linear
        res = lsq_linear(X.values, y.values, bounds=([0, 0, 0], [1, 1, 1]))
        coef = res.x
        return {"params": dict(zip(X.columns, coef)), "n": int(len(sub)), "bayes": False}

    with pm.Model():
        f1 = pm.Uniform("e_prev", 0, 1)
        f2 = pm.Uniform("e_consistent", 0, 1)
        f3 = pm.Uniform("pi_prev", 0, 1)
        mu = f1 * X["e_prev"] + f2 * X["e_consistent"] + f3 * X["pi_prev"]
        sigma = pm.HalfNormal("sigma", 1.0)
        pm.Normal("y", mu=mu, sigma=sigma, observed=y.values)
        trace = pm.sample(draws=draws, tune=tune, chains=2, cores=2,
                          random_seed=7, progressbar=False)

    def post(name):
        return float(trace.posterior[name].values.mean())

    return {"params": {k: post(k) for k in X.columns}, "n": int(len(sub)),
            "bayes": True, "_trace": trace}
