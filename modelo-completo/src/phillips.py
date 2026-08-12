"""Phillips setoriais (serviços, bens industriais, alimentação no domicílio).

Mesma especificação híbrida novo-keynesiana do modelo agregado, estimada para
cada setor livre sobre a amostra do SIDRA (2020+).
"""
from __future__ import annotations

import pandas as pd
import statsmodels.api as sm

from . import sector

PPC_AA = 1.0  # % a.a. (desvio da PPC nos regressores de câmbio)


def _lags(q: pd.DataFrame, cols: dict) -> pd.DataFrame:
    o = q.copy()
    for new, (col, lag) in cols.items():
        o[new] = o[col].shift(lag)
    return o


def estimate_sectoral_phillips(q: pd.DataFrame, start: str = "2020Q1") -> dict:
    q = q.copy()
    q["dev_ppc"] = q["dln_cambio"] - PPC_AA / 4  # câmbio como desvio da PPC (como no BCB)
    q = _lags(q, {"gap_1": ("gap", 1), "dln_cambio_1": ("dln_cambio", 1)})
    q = q.loc[start:]
    out = {}
    for setor in ["servicos", "industriais", "alimentacao"]:
        d = q.dropna(subset=[setor, "e_pi_next", "gap_1", "dev_ppc", "pi_com", "oni"])
        if len(d) < 15:
            out[setor] = None
            continue
        d = d.assign(y=d[setor] - d["e_pi_next"], x_inert=d[setor].shift(1) - d["e_pi_next"])
        d = d.dropna(subset=["x_inert"])
        res = sm.OLS(d["y"], sm.add_constant(d[["x_inert", "gap_1", "dev_ppc", "pi_com", "oni"]])).fit()
        phi1 = float(res.params["x_inert"])
        out[setor] = {
            "params": {
                "const": float(res.params["const"]), "pi_1": phi1,
                "e_pi_next": 1 - phi1, "gap_1": float(res.params["gap_1"]),
                "dev_ppc": float(res.params["dev_ppc"]),
                "pi_com": float(res.params["pi_com"]), "oni": float(res.params["oni"]),
            },
            "n": int(res.nobs), "r2": float(res.rsquared), "resid": res.resid,
        }
    return out


def sectoral_livres(q: pd.DataFrame, weights: dict) -> pd.Series:
    s = (q["servicos"] * weights["servicos"] + q["industriais"] * weights["industriais"]
         + q["alimentacao"] * weights["alimentacao"])
    return s / sum(weights.values())
