"""Phillips agregada fiel à especificação do RI dez/2021 (boxe b7).

    πL_t = c + α1·πL_{t-1} + (1−α1)·E_t[π_{t+1}] + α2·imp_t + α3·dev_ppc_t
               + α4·gap_{t-1} + α5·ElNiño_t + α6·LaNiña_t + ε

- imp     : inflação importada = variação do IC-Br em R$ (índice × câmbio). O BCB usa
            3 componentes (agro/metal/energia) ponderadas como desvio da meta; a réplica
            usa o IC-Br total em R$ (componentes indisponíveis na SGS) — simplificação.
- dev_ppc : variação do câmbio como desvio da PPC (Δe − ppc_trimestral).
- clima   : dummies assimétricas El Niño (ONI > 0,5) e La Niña (ONI < −0,5).
- Restrição novo-keynesiana: soma de inércia e expectativa = 1.
- Suportes (RI dez/2021): α1∈[0,1], α2∈[0,1], α3∈[0,1], α4∈[0,1], α5,α6∈[0,0,01].
- Amostra: 2003T4–2019T4 (a mesma do BCB).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import lsq_linear

PPC_AA = 1.0  # % a.a. (cenário/PPC de referência)
META_AA = 3.0  # % a.a. (meta contínua; usada no "desvio da meta" da inflação importada)


def estimate_phillips_bcb(q: pd.DataFrame, start: str = "2003Q4", end: str = "2019Q4",
                          ppc_aa: float = PPC_AA, constrain: bool = True) -> dict:
    """Estima a Phillips agregada do RI dez/2021 com restrição de suporte.

    Retorna dict com params, suportes, n, r2 e comparação com as modas publicadas.
    """
    d = q.copy()
    # inflação importada: IC-Br em R$ como DESVIO da meta (construção do RI) + energia (Brent R$)
    d["imp_total_dev"] = (d["pi_com"] + d["dln_cambio"]) - META_AA / 4
    d["imp_energia"] = np.log(d["brent"] * d["cambio"]).diff() * 100
    d["dev_ppc"] = d["dln_cambio"] - ppc_aa / 4       # desvio da PPC
    d["elnino"] = d["oni"].clip(lower=0)              # parte positiva (El Niño)
    d["lanina"] = (-d["oni"]).clip(lower=0)           # parte negativa (La Niña)
    d = d.loc[start:end].copy()

    # restrição NK: estimar com y = πL − Eπ e x_inert = πL_1 − Eπ
    sub = d.dropna(subset=["pi_l", "e_pi_next", "imp_total_dev", "imp_energia",
                           "dev_ppc", "gap_1", "elnino", "lanina"])
    sub = sub.assign(y=sub["pi_l"] - sub["e_pi_next"],
                     x_inert=sub["pi_l"].shift(1) - sub["e_pi_next"])
    sub = sub.dropna(subset=["x_inert"])

    X = sub[["x_inert", "imp_total_dev", "imp_energia", "dev_ppc", "gap_1", "elnino", "lanina"]]
    y = sub["y"]

    if constrain:
        # α1, α2a, α2b, α3, α4 em [0,1]; α5/α6 suporte [0,0.01] como no RI
        lo = [0.0] * 5 + [0.0, 0.0]
        hi = [1.0] * 5 + [0.01, 0.01]
        res = lsq_linear(X.values, y.values, bounds=(lo, hi))
        coef = res.x
    else:
        coef = np.linalg.lstsq(X.values, y.values, rcond=None)[0]

    phi1 = float(coef[0])
    params = {
        "pi_l_1": phi1, "e_pi_next": 1.0 - phi1,
        "imp_total": float(coef[1]), "imp_energia": float(coef[2]),
        "dev_ppc": float(coef[3]),
        "gap_1": float(coef[4]), "elnino": float(coef[5]), "lanina": float(coef[6]),
    }
    fit = X.values @ coef
    r2 = 1 - np.sum((y.values - fit) ** 2) / np.sum((y.values - y.mean()) ** 2)
    return {
        "params": params,
        "suportes": {"pi_l_1": "[0;1]", "imp_total": "[0;1]", "imp_energia": "[0;1]",
                     "dev_ppc": "[0;1]", "gap_1": "[0;1]",
                     "elnino": "[0;0,01]", "lanina": "[0;0,01]"},
        "n": int(len(sub)), "r2": float(r2), "constrain": constrain,
    }


RI_REF = {  # modas publicadas (RI dez/2021)
    "pi_l_1": 0.23756, "imp_total": 0.01826, "dev_ppc": 0.01727,
    "gap_1": 0.13866, "elnino": 0.00119, "lanina": 0.00104,
}


def compare_to_ri(est: dict) -> pd.DataFrame:
    rows = []
    for k, v in RI_REF.items():
        rows.append({"param": k, "replica": est["params"][k], "RI_2021": v,
                     "suporte": est["suportes"][k]})
    return pd.DataFrame(rows)


def estimate_phillips_bcb_bayes(q: pd.DataFrame, start: str = "2003Q4", end: str = "2019Q4",
                                ppc_aa: float = PPC_AA, draws: int = 800,
                                tune: int = 400, chains: int = 2, seed: int = 42) -> dict:
    """Phillips BCB bayesiana com os PRIORS UNIFORMES do RI dez/2021 (método do BCB).

    Priors nos suportes publicados: α1, imp, dev_ppc, gap_1 ~ Uniform([0,1]);
    El Niño e La Niña ~ Uniform([0,0,01]). Restrição NK (inércia + expectativa = 1).
    """
    import pymc as pm  # import local (PyMC só é necessário neste método)

    d = q.copy()
    d["imp_total_dev"] = (d["pi_com"] + d["dln_cambio"]) - META_AA / 4
    d["imp_energia"] = np.log(d["brent"] * d["cambio"]).diff() * 100
    d["dev_ppc"] = d["dln_cambio"] - ppc_aa / 4
    d["elnino"] = d["oni"].clip(lower=0)
    d["lanina"] = (-d["oni"]).clip(lower=0)
    d = d.loc[start:end].copy()
    sub = d.dropna(subset=["pi_l", "e_pi_next", "imp_total_dev", "imp_energia",
                           "dev_ppc", "gap_1", "elnino", "lanina"])
    sub = sub.assign(y=sub["pi_l"] - sub["e_pi_next"],
                     x_inert=sub["pi_l"].shift(1) - sub["e_pi_next"])
    sub = sub.dropna(subset=["x_inert"])

    with pm.Model():
        a1 = pm.Uniform("a1", 0, 1)
        impt = pm.Uniform("imp_total", 0, 1)
        impe = pm.Uniform("imp_energia", 0, 1)
        dev = pm.Uniform("dev_ppc", 0, 1)
        gap = pm.Uniform("gap_1", 0, 1)
        en = pm.Uniform("elnino", 0, 0.01)
        la = pm.Uniform("lanina", 0, 0.01)
        mu = (a1 * sub["x_inert"] + impt * sub["imp_total_dev"] + impe * sub["imp_energia"]
              + dev * sub["dev_ppc"] + gap * sub["gap_1"]
              + en * sub["elnino"] + la * sub["lanina"])
        sigma = pm.HalfNormal("sigma", 1.0)
        pm.Normal("y", mu=mu, sigma=sigma, observed=sub["y"].values)
        trace = pm.sample(draws=draws, tune=tune, chains=chains, cores=2,
                          random_seed=seed, progressbar=False)

    def post(name):
        return float(trace.posterior[name].values.mean())

    params = {"pi_l_1": post("a1"), "e_pi_next": 1 - post("a1"),
              "imp_total": post("imp_total"), "imp_energia": post("imp_energia"),
              "dev_ppc": post("dev_ppc"),
              "gap_1": post("gap_1"), "elnino": post("elnino"), "lanina": post("lanina")}
    return {
        "params": params,
        "suportes": {"pi_l_1": "[0;1]", "imp_total": "[0;1]", "imp_energia": "[0;1]",
                     "dev_ppc": "[0;1]", "gap_1": "[0;1]",
                     "elnino": "[0;0,01]", "lanina": "[0;0,01]"},
        "n": int(len(sub)), "constrain": True, "bayes": True, "_trace": trace,
    }
