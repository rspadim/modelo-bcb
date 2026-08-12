"""Estimação bayesiana conjunta (PyMC) — aproximação do procedimento do BCB.

Estima Phillips setoriais + IS + admin de forma conjunta, condicionadas ao
hiato do estado-espaço (estágio 2), com priors informativos centrados nas
estimações OLS e dispersão moderada. A distribuição posterior alimenta:
    - parâmetros médios (substituem o OLS no sistema);
    - incerteza paramétrica para o fan chart (Fase F).

Nota: o BCB estima o modelo de pequeno porte com o hiato e o juro neutro
como estados latentes estimados conjuntamente (bayesiano). Nesta réplica o
hiato vem do DynamicFactor (estágio 1) e o restante do sistema é estimado
conjuntamente — simplificação documentada.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pymc as pm

from . import sector


def _priors(res: dict, width: float = 2.0) -> dict:
    """Priors normais centrados no OLS com desvio = |coef|*width (mín. pequeno)."""
    out = {}
    for k, v in res["params"].items():
        sd = max(abs(v) * width, 0.05)
        out[k] = (float(v), float(sd))
    return out


def estimate_bayesian(q: pd.DataFrame, ols: dict, draws: int = 600,
                      tune: int = 400, chains: int = 2, seed: int = 42) -> dict:
    """Estimação conjunta das equações do sistema via PyMC (NUTS).

    ols: dict no formato de equations.estimate_all (contém 'params').
    Retorna dict com 'params' (médias posteriores), 'sd' (desvio posterior),
    'trace' e 'n'.
    """
    n = len(q)
    meta = np.full(n, 3.0)

    # dados (alinhados por linha de q, com lags)
    d = pd.DataFrame({
        "pi_l": q["pi_l"], "pi_l_1": q["pi_l"].shift(1),
        "e_next": q["e_pi_next"], "gap": q["gap"], "gap_1": q["gap"].shift(1),
        "gap_2": q["gap"].shift(2), "dln_cambio": q["dln_cambio"],
        "dev_ppc": q["dln_cambio"] - 0.25,   # câmbio como desvio da PPC (~1% a.a.)
        "pi_com": q["pi_com"], "oni": q["oni"],
        "selic": q["selic"], "selic_1": q["selic"].shift(1),
        "selic_2": q["selic"].shift(2), "ff": q["ff"],
        "pi_a": q["pi_a"], "pi_a_1": q["pi_a"].shift(1),
        "fiscal": q.get("fiscal", 0.0),
        "rreal_1": (q["selic"] - 4 * q["e_pi_next"]).shift(1),
    })
    for s in ["servicos", "industriais", "alimentacao"]:
        d[s] = q[s]
        d[f"{s}_1"] = q[s].shift(1)
    d = d.dropna()

    p_liv = ols["phillips"]
    with pm.Model() as model:
        # ---- Phillips setoriais (híbrida NK: e_pi = 1 - pi_1) ----
        coefs = {}
        for s in ["servicos", "industriais", "alimentacao"]:
            p0 = _priors(p_liv[s])
            c = {}
            for k, (mu, sd) in p0.items():
                if k in ("dev_ppc", "dln_cambio"):
                    # repasse cambial imposto positivo (como no modelo do BCB)
                    c[k] = pm.HalfNormal(f"{s}_{k}", sigma=max(sd, 0.1))
                elif k == "gap_1":
                    # prior informativo do hiato na Phillips (BCB ~0,3-0,6), evita
                    # coeficiente explosivo da amostra curta (OLS ~4-18)
                    c[k] = pm.Normal(f"{s}_{k}", mu=0.4, sigma=0.3)
                else:
                    c[k] = pm.Normal(f"{s}_{k}", mu=mu, sigma=sd)
            coefs[s] = c
            camb = c.get("dev_ppc", c.get("dln_cambio"))
            mu = (c["const"] + c["pi_1"] * d[f"{s}_1"] + (1 - c["pi_1"]) * d["e_next"]
                  + c["gap_1"] * d["gap_1"] + camb * d["dev_ppc"]
                  + c["pi_com"] * d["pi_com"] + c["oni"] * d["oni"])
            sigma = pm.HalfNormal(f"sigma_{s}", sigma=1.0)
            pm.Normal(f"y_{s}", mu=mu, sigma=sigma, observed=d[s])

        # ---- IS ----
        p_is = ols["is"]
        p0 = _priors(p_is)
        c_is = {k: pm.Normal(f"is_{k}", mu=v, sigma=sd) for k, (v, sd) in p0.items()}
        mu_is = (c_is["const"] + c_is["gap_1"] * d["gap_1"] + c_is["gap_2"] * d["gap_2"]
                 + c_is["rreal_1"] * d["rreal_1"] + c_is["dln_cambio"] * d["dln_cambio"]
                 + c_is["fiscal"] * d["fiscal"])
        sigma_is = pm.HalfNormal("sigma_is", sigma=2.0)
        pm.Normal("y_is", mu=mu_is, sigma=sigma_is, observed=d["gap"])

        # ---- Admin ----
        p_adm = ols["admin"]
        p0 = _priors(p_adm)
        c_adm = {}
        for k, (mu, sd) in p0.items():
            if k == "dln_cambio":
                c_adm[k] = pm.HalfNormal(f"adm_{k}", sigma=max(sd, 0.1))
            else:
                c_adm[k] = pm.Normal(f"adm_{k}", mu=mu, sigma=sd)
        mu_a = (c_adm["const"] + c_adm["pi_a_1"] * d["pi_a_1"]
                + c_adm["pi_l_1"] * d["pi_l_1"] + c_adm["dln_cambio"] * d["dln_cambio"])
        sigma_a = pm.HalfNormal("sigma_adm", sigma=1.0)
        pm.Normal("y_adm", mu=mu_a, sigma=sigma_a, observed=d["pi_a"])

        trace = pm.sample(draws=draws, tune=tune, chains=chains, cores=2,
                          random_seed=seed, progressbar=False)

    out: dict = {}
    n_obs = len(d)
    for s in ["servicos", "industriais", "alimentacao"]:
        out.setdefault("phillips", {})[s] = _posterior(trace, s)
    out["is"] = _posterior(trace, "is")
    out["admin"] = _posterior(trace, "adm")
    for key in out:
        out[key]["n"] = n_obs
    out["_trace"] = trace
    return out


def _posterior(trace, prefix: str) -> dict:
    params, sd = {}, {}
    for var in trace.posterior:
        name = str(var)
        if not name.startswith(prefix + "_"):
            continue
        key = name[len(prefix) + 1:]
        arr = trace.posterior[name].values
        params[key] = float(np.mean(arr))
        sd[key] = float(np.std(arr))
    return {"params": params, "sd": sd}


def trace_to_est(trace, idx: int, template: dict) -> dict:
    """Monta um est dict (params) a partir da idx-ésima amostra da posterior.

    template: est OLS (define a estrutura: phillips por setor, is, admin).
    """
    post = trace.posterior
    out: dict = {}

    def params_for(prefix: str) -> dict:
        p = {}
        for var in post:
            name = str(var)
            if name.startswith(prefix + "_"):
                key = name[len(prefix) + 1:]
                p[key] = float(post[name].values.reshape(-1)[idx])
        return p

    out["phillips"] = {}
    for s in ["servicos", "industriais", "alimentacao"]:
        out["phillips"][s] = {"params": params_for(s)}
    out["is"] = {"params": params_for("is")}
    out["admin"] = {"params": params_for("adm")}
    for k in ("taylor", "uip", "expect"):
        if k in template:
            out[k] = template[k]
    return out


def posterior_samples(trace, key: str, n: int = 500, seed: int = 7) -> list[dict]:
    """Amostras da posterior para um conjunto de parâmetros (fan chart)."""
    rng = np.random.default_rng(seed)
    draws = trace.posterior[key].values.reshape(-1)
    idx = rng.choice(len(draws), size=n, replace=True)
    return [{"params": {"const": float(draws[i])}} for i in idx]
