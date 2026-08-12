"""Estado-espaço CONJUNTO (P3 completo) — hiato + juro neutra latentes com as equações.

Estrutura (BCB pós-2020, RI dez/2021 b7): o hiato é latente, com dinâmica dada pela IS
(juro real vs neutra) e observado pela atividade e pela Phillips.

Estados: [g_t, g_{t-1}, r̄_t]
Transição (IS = lei de movimento do hiato):
    g_t  = b1·g_{t-1} + b2·(r̄_{t-1} − rreal_{t-1}) + η_g
    r̄_t = r̄_{t-1} + η_r          (σ_r fixo pequeno: neutra move-se lentamente)
Observações:
    dl_ibc_t = g_t − g_{t-1} + ε_ibc          (identifica a escala do hiato, em log-IBC)
    desoc_t  = mdesoc + ldesoc·g_t + ε_desoc  (2012+)
    πL_t     = a1·πL_{t-1} + (1−a1)·Eπ_t + a2·imp_t + a3·dev_ppc_t + a4·g_{t-1}
               + a5·ElNiño_t + a6·LaNiña_t + ε_phi

Estimação por MLE (L-BFGS-B) com suportes (b1∈[0,1], b2≥0, a_i≥0). Suavizados: hiato e neutra.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from statsmodels.tsa.statespace.mlemodel import MLEModel

from equacoes_bcb import _hp_cycle

PPC_AA = 1.0
META = 3.0
SIGMA_R = 0.2  # desvio do choque da neutra (fixo, lento)


class JointStateSpace(MLEModel):
    def __init__(self, y, rreal, phillips_exog, phillips_fixed=None):
        # y: [dl_ibc, desoc, pi_l]; rreal defasado; phillips_exog: [pi_l_1, e_next, imp, dev_ppc, elnino, lanina]
        k_states, k_posdef = 3, 2
        super().__init__(endog=y, k_states=k_states, k_posdef=k_posdef)
        self["transition"] = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
        self["selection"] = np.array([[1.0, 0.0], [0.0, 0.0], [0.0, 1.0]])
        self["state_cov"] = np.diag([1.0, SIGMA_R ** 2])
        self["design"] = np.zeros((3, k_states, self.nobs))
        self["design", 0, 0, :] = 1.0     # dl_ibc = g_t − g_{t-1}
        self["design", 0, 1, :] = -1.0
        self["obs_intercept"] = np.zeros((3, self.nobs))
        self["state_intercept"] = np.zeros((k_states, self.nobs))
        self.rreal = np.asarray(rreal)
        self.px = np.asarray(phillips_exog)
        # se fixar a Phillips, só IS + variâncias são estimados
        self.phillips_fixed = phillips_fixed
        self.ssm.initialize_approximate_diffuse(1e-6)

    @property
    def param_names(self):
        if self.phillips_fixed is not None:
            return ["b1", "b2", "ldesoc", "mdesoc", "sg", "sd", "sp"]
        return ["b1", "b2", "ldesoc", "mdesoc",
                "a1", "a2", "a3", "a4", "a5", "a6",
                "sg", "sd", "sp"]

    @property
    def start_params(self):
        if self.phillips_fixed is not None:
            return np.array([0.75, 0.3, -0.2, 9.5, 0.5, 0.4, 0.6])
        return np.array([0.75, 0.3, -0.2, 9.5,
                         0.3, 0.02, 0.02, 0.15, 0.005, 0.005,
                         0.5, 0.4, 0.6])

    def update(self, params, transformed=True, **kwargs):
        params = super().update(params, transformed, **kwargs)
        if self.phillips_fixed is not None:
            b1, b2, ldesoc, mdesoc = params[0:4]
            sg, sd, sp = params[4:7]
            a1, a2, a3, a4, a5, a6 = self.phillips_fixed
        else:
            b1, b2, ldesoc, mdesoc = params[0:4]
            a1, a2, a3, a4, a5, a6 = params[4:10]
            sg, sd, sp = params[10:13]
        self["transition", 0, 0] = b1
        self["transition", 0, 2] = b2
        self["state_intercept", 0, :] = -b2 * self.rreal
        self["state_intercept", 1:, :] = 0.0
        self["state_cov", 0, 0] = sg ** 2
        self["design", 1, 0, :] = ldesoc
        self["obs_intercept", 1, :] = mdesoc
        self["design", 2, 1, :] = a4
        self["obs_intercept", 2, :] = (a1 * self.px[:, 0] + (1 - a1) * self.px[:, 1]
                                       + a2 * self.px[:, 2] + a3 * self.px[:, 3]
                                       + a5 * self.px[:, 4] + a6 * self.px[:, 5])
        self["obs_cov"] = np.diag([sd ** 2, sd ** 2, sp ** 2])

    @property
    def param_bounds(self):
        if self.phillips_fixed is not None:
            return [(0.0, 1.0), (0.0, np.inf), (-np.inf, np.inf), (-np.inf, np.inf),
                    (1e-6, np.inf), (1e-6, np.inf), (1e-6, np.inf)]
        return [(0.0, 1.0), (0.0, np.inf), (-np.inf, np.inf), (-np.inf, np.inf),
                (0.0, 1.0), (0.0, np.inf), (0.0, np.inf), (0.0, np.inf),
                (0.0, 0.1), (0.0, 0.1),
                (1e-6, np.inf), (1e-6, np.inf), (1e-6, np.inf)]


def estimate_joint(q: pd.DataFrame, start: str = "2003Q4", end: str = "2019Q4",
                   maxiter: int = 800, phillips_fixed: tuple | None = None) -> dict:
    """Estima o estado-espaço conjunto.

    phillips_fixed: (a1, a2, a3, a4, a5, a6) opcional — fixa a Phillips (dos valores
    já estimados em phillips_bcb) e estima só IS + variâncias + estados (mais estável).
    """
    d = q.copy()
    d["dl_ibc"] = d["l_ibc"].diff() * 100
    d["imp"] = (d["pi_com"].ffill() + d["dln_cambio"]) - META / 4
    d["dev_ppc"] = d["dln_cambio"] - PPC_AA / 4
    d["elnino"] = d["oni"].clip(lower=0)
    d["lanina"] = (-d["oni"]).clip(lower=0)
    d["rreal"] = d["selic"] - 4 * d["e_pi_next"]
    d["rreal_1"] = d["rreal"].shift(1).ffill().bfill()
    for c in ["imp", "dev_ppc", "elnino", "lanina"]:
        d[c] = d[c].ffill().bfill()
    d = d.loc[start:end].copy()

    y = d[["dl_ibc", "desocupacao", "pi_l"]]
    rreal = d["rreal_1"].values
    px = np.column_stack([d["pi_l"].shift(1), d["e_pi_next"], d["imp"], d["dev_ppc"],
                          d["elnino"], d["lanina"]])
    valid = d["pi_l"].notna() & d["e_pi_next"].notna()
    y = y[valid].copy()
    rreal = rreal[valid]
    px = px[valid]
    px = np.nan_to_num(px, nan=0.0)

    mod = JointStateSpace(y, rreal, px, phillips_fixed=phillips_fixed)
    res = mod.fit(method="lbfgs", bounds=mod.param_bounds, maxiter=maxiter, disp=False)

    states = np.asarray(res.states.smoothed).reshape(-1, mod.k_states)
    gap = pd.Series(states[:, 0], index=y.index)
    rbar = pd.Series(states[:, 2], index=y.index) + 5.0  # nível da neutra (offset)
    params = {name: float(v) for name, v in zip(mod.param_names, res.params)}
    return {"params": params, "gap": gap, "rbar": rbar, "n": int(len(y)), "res": res}
