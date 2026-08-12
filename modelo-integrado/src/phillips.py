"""Phillips setoriais (serviços, bens industriais, alimentação) — amostra SIDRA 2020+.

Mesma especificação híbrida novo-keynesiana, com câmbio como desvio da PPC (como no BCB).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.optimize import lsq_linear

import sector

PPC_AA = 1.0


def estimate_sectoral_phillips(q: pd.DataFrame, start: str = "2020Q1") -> dict:
    q = q.copy()
    q["dev_ppc"] = q["dln_cambio"] - PPC_AA / 4
    q["gap_1"] = q["gap"].shift(1)
    q = q.loc[start:]
    out = {}
    for s in ["servicos", "industriais", "alimentacao"]:
        d = q.dropna(subset=[s, "e_pi_next", "gap_1", "dev_ppc", "pi_com", "oni"])
        if len(d) < 15:
            out[s] = None
            continue
        d = d.assign(y=d[s] - d["e_pi_next"], x_inert=d[s].shift(1) - d["e_pi_next"])
        d = d.dropna(subset=["x_inert"])
        X = d[["x_inert", "dev_ppc", "pi_com", "oni"]]
        # suportes do RI: inércia/repasse/commodities em [0,1]; clima em [0,0,01].
        # O hiato é CALIBRADO em 0,14 (α4 do RI): a amostra curta 2020+ não identifica o
        # canal de hiato (OLS/constrito satura no limite e explode a IRF de demanda).
        res = lsq_linear(X.values, d["y"].values,
                         bounds=([0, 0, 0, 0], [1, 1, 1, 0.01]))
        phi1 = float(res.x[0])
        out[s] = {
            "params": {"const": 0.0, "pi_1": phi1, "e_pi_next": 1 - phi1,
                       "gap_1": 0.14, "dev_ppc": float(res.x[1]),
                       "pi_com": float(res.x[2]), "oni": float(res.x[3])},
            "n": int(len(d)), "r2": float(np.nan), "resid": None,
        }
    return out
