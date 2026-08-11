"""Estimação das equações estruturais (OLS, uma equação por vez)."""
from __future__ import annotations

import pandas as pd
import statsmodels.api as sm

try:
    from . import meta as meta_mod
except ImportError:
    import meta as meta_mod


def _ols(y, X, names):
    X = sm.add_constant(X)
    res = sm.OLS(y, X, missing="drop").fit()
    return {
        "params": {k: float(v) for k, v in res.params.items()},
        "stderr": {k: float(v) for k, v in res.bse.items()},
        "pvalues": {k: float(v) for k, v in res.pvalues.items()},
        "n": int(res.nobs), "r2": float(res.rsquared),
        "aic": float(res.aic), "resid": res.resid,
    }


def _with_lags(q: pd.DataFrame, cols: dict) -> pd.DataFrame:
    out = q.copy()
    for new, (col, lag) in cols.items():
        out[new] = out[col].shift(lag)
    return out


def estimate_all(q: pd.DataFrame, start: str = "2002Q1",
                 meta_tol: float = 1.5) -> dict:
    q = q.copy()
    q["meta"] = meta_mod.meta_series(q)
    q["rreal"] = q["selic"] - 4 * q["e_pi_next"]
    q["dev_pi"] = q["e_pi_next"] - q["meta"]
    q["diff_juros"] = (q["selic"] - q["ff"]).shift(1)

    q = _with_lags(q, {
        "pi_l_1": ("pi_l", 1), "gap_1": ("gap", 1), "gap_2": ("gap", 2),
        "rreal_1": ("rreal", 1), "selic_1": ("selic", 1),
        "selic_2": ("selic", 2), "pi_a_1": ("pi_a", 1),
        "e_pi_next_1": ("e_pi_next", 1), "pi_1": ("pi", 1),
    })
    q = q.loc[start:]
    out = {}

    d = q.dropna(subset=["pi_l", "pi_l_1", "e_pi_next", "gap_1", "dln_cambio", "pi_com", "oni"])
    # Phillips híbrida com restrição novo-keynesiana: coef. da expectativa = 1 - coef. da defasagem
    d = d.assign(y=d["pi_l"] - d["e_pi_next"],
                 x_inert=d["pi_l_1"] - d["e_pi_next"])
    res = sm.OLS(d["y"], sm.add_constant(d[["x_inert", "gap_1", "dln_cambio", "pi_com", "oni"]]),
                 missing="drop").fit()
    phi1 = float(res.params["x_inert"])
    se_phi1 = float(res.bse["x_inert"])
    p_phi1 = float(res.pvalues["x_inert"])
    out["phillips"] = {
        "params": {
            "const": float(res.params["const"]),
            "pi_l_1": phi1,
            "e_pi_next": 1 - phi1,
            "gap_1": float(res.params["gap_1"]),
            "dln_cambio": float(res.params["dln_cambio"]),
            "pi_com": float(res.params["pi_com"]),
            "oni": float(res.params["oni"]),
        },
        "stderr": {
            "const": float(res.bse["const"]), "pi_l_1": se_phi1, "e_pi_next": se_phi1,
            "gap_1": float(res.bse["gap_1"]), "dln_cambio": float(res.bse["dln_cambio"]),
            "pi_com": float(res.bse["pi_com"]), "oni": float(res.bse["oni"]),
        },
        "pvalues": {
            "const": float(res.pvalues["const"]), "pi_l_1": p_phi1, "e_pi_next": p_phi1,
            "gap_1": float(res.pvalues["gap_1"]), "dln_cambio": float(res.pvalues["dln_cambio"]),
            "pi_com": float(res.pvalues["pi_com"]), "oni": float(res.pvalues["oni"]),
        },
        "n": int(res.nobs), "r2": float(res.rsquared),
        "aic": float(res.aic), "resid": res.resid,
    }

    d = q.dropna(subset=["gap", "gap_1", "gap_2", "rreal_1", "dln_cambio", "fiscal"])
    out["is"] = _ols(d["gap"], d[["gap_1", "gap_2", "rreal_1", "dln_cambio", "fiscal"]],
                     ["gap_1", "gap_2", "rreal_1", "dln_cambio", "fiscal"])

    d = q.dropna(subset=["selic", "selic_1", "selic_2", "dev_pi"])
    out["taylor"] = _ols(d["selic"], d[["selic_1", "selic_2", "dev_pi"]],
                         ["selic_1", "selic_2", "dev_pi"])

    d = q.dropna(subset=["dln_cambio", "diff_juros"])
    out["uip"] = _ols(d["dln_cambio"], d[["diff_juros"]], ["diff_juros"])

    d = q.dropna(subset=["pi_a", "pi_a_1", "pi_l_1", "dln_cambio"])
    out["admin"] = _ols(d["pi_a"], d[["pi_a_1", "pi_l_1", "dln_cambio"]],
                        ["pi_a_1", "pi_l_1", "dln_cambio"])

    d = q.dropna(subset=["e_pi_next", "e_pi_next_1", "pi_1"])
    out["expect"] = _ols(d["e_pi_next"], d[["e_pi_next_1", "pi_1"]],
                         ["e_pi_next_1", "pi_1"])

    return out