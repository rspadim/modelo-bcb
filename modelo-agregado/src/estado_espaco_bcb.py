"""Estado-espaço (P3): juro real neutra como ESTADO LATENTE estimado com a IS.

Reduzido e tratável: o hiato vem do estágio 1 (Kalman/DynamicFactor); a taxa neutra
r̄_t é um passeio aleatório estimado conjuntamente com os coeficientes da IS:

    gap_t = c + β1·gap_{t-1} + β2·(r̄_{t-1} − rreal_{t-1}) + β3·fisc_cc + β4·incert
                  + β5·us_gap + ε_t
    r̄_t = r̄_{t-1} + η_t          (σ_η estimado)

Observação: rreal = Selic − 4·Eπ. β2 > 0 implica juro real acima da neutra reduz o hiato.
A trajetória suavizada de r̄ é a estimativa da taxa neutra consistente com o modelo
(analogamente ao RI jun/2024, boxe b11).

O BCB estima hiato E neutra conjuntamente (estado-espaço bayesiano completo); a versão
completa fica como roadmap — ver docs/modelagem_bcb.md.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from statsmodels.tsa.statespace.mlemodel import MLEModel

import equacoes_bcb as eqb  # _hp_cycle

ETA_SD = 0.2  # desvio do choque do passeio aleatório da neutra (lento, calibrado)


class ISNeutralRate(MLEModel):
    """gap = c + β1·gap_{t-1} + β2·(r̄_{t-1} − rreal_{t-1}) + X·γ;  r̄ RW."""

    def __init__(self, y, exog, rreal):
        super().__init__(y, k_states=1, k_posdef=1)
        self["transition"] = [[1.0]]           # r̄ RW
        self["state_cov", 0, 0] = 1.0
        self["selection"] = [[1.0]]
        self["obs_intercept"] = np.zeros((1, self.nobs))  # time-varying
        self.exog = np.asarray(exog)           # [const, gap_1, fisc_cc, incert, us_gap]
        self.rreal = np.asarray(rreal)
        k = self.exog.shape[1]
        self._n_reg = k
        self["state_intercept"] = np.zeros((1, 1))
        self.ssm.initialize_approximate_diffuse(1e-6)

    @property
    def param_names(self):
        return [f"b{i}" for i in range(self._n_reg)] + ["beta2", "sigma_eps"]

    @property
    def start_params(self):
        return np.r_[np.zeros(self._n_reg), 0.2, 0.5]

    def update(self, params, transformed=True, **kwargs):
        params = super().update(params, transformed, **kwargs)
        n = self._n_reg
        b, beta2, se = params[:n], params[n], params[n + 1]
        # design: loading de r̄_{t-1} = beta2; intercept = b·X − beta2·rreal_{t-1}
        self["design", 0, 0] = beta2
        self["obs_intercept", 0, :] = self.exog @ b - beta2 * self.rreal
        self["state_cov", 0, 0] = ETA_SD ** 2   # σ_η fixo (neutra move-se lentamente)
        self["obs_cov", 0, 0] = se ** 2


def estimate_neutral_rate(q: pd.DataFrame, start: str = "2003Q4", end: str = "2019Q4",
                          r_neutral_init: float = 5.0) -> dict:
    """Estima a taxa neutra latente (Kalman) + IS, amostra 2003T4–2019T4."""
    d = q.copy()
    d["rreal"] = d["selic"] - 4 * d["e_pi_next"]
    d = d.loc[start:end].copy()
    # fisc_cc dentro da janela (HP bilateral não deve ver dados além de `end`)
    d["fisc_cc"] = eqb._hp_cycle(d["fiscal"])
    d["incert"] = d["dln_cambio"].rolling(12, min_periods=8).std()
    sub = d.dropna(subset=["gap", "gap_1", "rreal", "fisc_cc", "incert", "us_gap"])
    y = sub["gap"].values
    exog = np.column_stack([np.ones(len(sub)), sub["gap_1"], sub["fisc_cc"],
                            sub["incert"], sub["us_gap"]])
    rreal = sub["rreal"].values

    mod = ISNeutralRate(y, exog, rreal)
    res = mod.fit(disp=False, maxiter=500)

    # suavização do estado r̄
    states = res.states.smoothed[:, 0] if hasattr(res.states.smoothed, "shape") \
        else res.states.smoothed
    rbar = pd.Series(np.asarray(states), index=sub.index) + r_neutral_init  # nível
    params = {
        "const": float(res.params[0]), "gap_1": float(res.params[1]),
        "fisc_cc": float(res.params[2]), "incert": float(res.params[3]),
        "us_gap": float(res.params[4]), "beta2": float(res.params[5]),
        "sigma_eps": float(res.params[6]),
    }
    return {"params": params, "rbar": rbar, "n": int(len(sub)), "res": res}
