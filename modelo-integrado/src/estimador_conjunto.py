"""Estimação bayesiana CONJUNTA PLENA do modelo integrado (PyMC + g++).

Estrutura (RI dez/2021 b7): hiato (AR com dinâmica da IS) e juro real neutra (passeio
aleatório) como latentes, observados por atividade (Δlog IBC-Br, desocupação) e pela
Phillips de livres, com as expectativas.

Latentes (por t = 0..n-1):
    g_{t}   = b1·g_{t-1} + b2·(r̄_{t-1} − rreal_{t-1}) + η_g      (IS)
    r̄_{t}   = r̄_{t-1} + η_r                                        (σ_r fixo pequeno)
Observações:
    dl_ibc_t = g_t − g_{t-1} + ε_i
    desoc_t  = mdesoc + ldesoc·g_t + ε_d
    πL_t     = a1·πL_{t-1} + (1−a1)·E_t + a2·imp_t + a3·dev_ppc_t + a4·g_{t-1}
               + a5·ElNiño_t + a6·LaNiña_t + ε_π

Priors: Uniform nos suportes do RI dez/2021 (a1..a4 ∈[0,1], a5/a6 ∈[0,0,01], b1∈[0,1],
b2∈[0,2]). Roda em C com g++ (Docker); o `--est staged` (MLE) é o fallback.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pymc as pm
from pytensor.scan import scan

PPC_AA = 1.0
META = 3.0
SIGMA_R = 0.2


def _prep(q: pd.DataFrame, start: str = "2003Q4", end: str = "2019Q4"):
    d = q.copy()
    d["dl_ibc"] = d["l_ibc"].diff() * 100
    d["imp"] = (d["pi_com"].ffill() + d["dln_cambio"]).rolling(4).mean() - META / 4
    d["dev_ppc"] = d["dln_cambio"] - PPC_AA / 4
    d["elnino"] = d["oni"].clip(lower=0)
    d["lanina"] = (-d["oni"]).clip(lower=0)
    d["rreal"] = d["selic"] - 4 * d["e_pi_next"]
    d["rreal_1"] = d["rreal"].shift(1)
    for c in ["imp", "dev_ppc", "elnino", "lanina", "rreal_1"]:
        d[c] = d[c].ffill().bfill()
    d = d.loc[start:end].copy()
    d["pi_l_1"] = d["pi_l"].shift(1)
    valid = d["pi_l"].notna() & d["e_pi_next"].notna() & d["pi_l_1"].notna()
    d = d[valid].copy()
    return d


def estimar_conjunta(q: pd.DataFrame, start: str = "2003Q4", end: str = "2019Q4",
                     draws: int = 500, tune: int = 300, chains: int = 2,
                     seed: int = 42) -> dict:
    """Estima o modelo integrado conjuntamente (PyMC NUTS). Retorna posteriors + estados."""
    d = _prep(q, start, end)
    n = len(d)
    dl = d["dl_ibc"].values
    desoc = d["desocupacao"].values
    pi = d["pi_l"].values
    pil1 = d["pi_l_1"].values
    E = d["e_pi_next"].values
    imp = d["imp"].values
    dev = d["dev_ppc"].values
    en = d["elnino"].values
    la = d["lanina"].values
    rreal1 = d["rreal_1"].values

    with pm.Model():
        # parâmetros com priors dos suportes do RI dez/2021
        a1 = pm.Uniform("a1", 0, 1)
        a2 = pm.Uniform("a2", 0, 1)
        a3 = pm.Uniform("a3", 0, 1)
        a4 = pm.Uniform("a4", 0, 1)
        a5 = pm.Uniform("a5", 0, 0.01)
        a6 = pm.Uniform("a6", 0, 0.01)
        b1 = pm.Uniform("b1", 0, 1)
        b2 = pm.Uniform("b2", 0, 2)
        ldesoc = pm.Normal("ldesoc", -0.3, 0.15)
        mdesoc = pm.Normal("mdesoc", 10.0, 2.0)
        sg = pm.HalfNormal("sg", 0.5)
        si = pm.HalfNormal("si", 0.5)
        sd = pm.HalfNormal("sd", 0.5)
        sp = pm.HalfNormal("sp", 0.6)

        # latentes: juro neutra (passeio aleatório lento)
        rbar = pm.GaussianRandomWalk("rbar", sigma=SIGMA_R, init_dist=pm.Normal.dist(0, 1), shape=n)

        # hiato AR(1) com drift da IS (loop Python sobre n ~ 64 é barato simbolicamente)
        g0 = pm.Normal("g0", 0, 1)
        g_shock = pm.Normal("g_shock", 0, sg, shape=n)
        g_list = [g0]
        for t in range(1, n):
            g_list.append(b1 * g_list[t - 1] + b2 * (rbar[t - 1] - rreal1[t]) + g_shock[t])
        g = pm.Deterministic("gap", pm.math.stack(g_list))

        # observações
        pm.Normal("obs_ibc", mu=g - pm.math.concatenate([[g0], g[:-1]]), sigma=si,
                  observed=dl)
        pm.Normal("obs_desoc", mu=mdesoc + ldesoc * g, sigma=sd, observed=desoc)
        mu_pi = (a1 * pil1 + (1 - a1) * E + a2 * imp + a3 * dev
                 + a4 * pm.math.concatenate([[g0], g[:-1]]) + a5 * en + a6 * la)
        pm.Normal("obs_pi", mu=mu_pi, sigma=sp, observed=pi)

        trace = pm.sample(draws=draws, tune=tune, chains=chains, cores=2,
                          random_seed=seed, progressbar=False)

    def post(name):
        return float(trace.posterior[name].values.mean())

    params = {"a1": post("a1"), "a2": post("a2"), "a3": post("a3"), "a4": post("a4"),
              "a5": post("a5"), "a6": post("a6"),
              "b1": post("b1"), "b2": post("b2"),
              "ldesoc": post("ldesoc"), "mdesoc": post("mdesoc"),
              "sg": post("sg"), "si": post("si"), "sd": post("sd"), "sp": post("sp")}
    gap_post = trace.posterior["gap"].values.mean(axis=(0, 1))
    rbar_post = trace.posterior["rbar"].values.mean(axis=(0, 1)) + 5.0
    return {
        "params": params,
        "gap": pd.Series(gap_post, index=d.index),
        "rbar": pd.Series(rbar_post, index=d.index),
        "n": int(n), "_trace": trace, "bayes": True,
    }
