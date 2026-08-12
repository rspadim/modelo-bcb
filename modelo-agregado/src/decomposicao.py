"""Decomposição de inflação (WP 440 / ofício 374/2025-BCB).

Usa a Phillips agregada do RI dez/2021 para decompor o desvio da inflação de livres
em relação à meta em contribuições de:
  - inércia            : α1·(πL_{t-1} − meta)
  - expectativas       : (1−α1)·(Eπ − meta)
  - inflação importada : α2·imp  (IC-Br em R$)
  - câmbio (desvio PPC): α3·dev_ppc
  - hiato do produto   : α4·gap_{t-1}
  - clima (El Niño/La Niña): α5·elnino + α6·lanina
  - residual/constante : const + ε
O somatório reproduz o desvio πL − meta (fora a constante/residual).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

PPC_AA = 1.0


def decompose(q: pd.DataFrame, phillips: dict, start: str = "2024Q1",
              end: str = "2024Q4", meta: float = 3.0) -> pd.DataFrame:
    """Contribuições trimestrais ao desvio πL − meta (p.p.)."""
    p = phillips["params"]
    d = q.copy()
    d["imp"] = d["pi_com"].ffill() + d["dln_cambio"]   # ffill da lacuna do IC-Br 2024-25
    d["dev_ppc"] = d["dln_cambio"] - PPC_AA / 4
    d["elnino"] = d["oni"].clip(lower=0)
    d["lanina"] = (-d["oni"]).clip(lower=0)

    d["dev"] = d["pi_l"] - meta / 4                    # desvio trimestral de livres
    d["inercia"] = p["pi_l_1"] * (d["pi_l"].shift(1) - meta / 4)
    d["expect"] = p["e_pi_next"] * (d["e_pi_next"] - meta / 4)
    d["importada"] = p["imp"] * d["imp"]
    d["cambio"] = p["dev_ppc"] * d["dev_ppc"]
    d["hiato"] = p["gap_1"] * d["gap_1"]
    d["clima"] = p["elnino"] * d["elnino"] + p["lanina"] * d["lanina"]

    cols = ["inercia", "expect", "importada", "cambio", "hiato", "clima"]
    out = d.loc[start:end, ["dev"] + cols].copy()
    out["residual"] = out["dev"] - out[cols].sum(axis=1)
    return out


def summary(contrib: pd.DataFrame, annualize: bool = False) -> pd.DataFrame:
    """Resumo das contribuições médias (ou anuais) ao desvio, em p.p."""
    cols = ["inercia", "expect", "importada", "cambio", "hiato", "clima", "residual"]
    if annualize:
        # soma dentro do ano e projeta: desvio anual ≈ soma dos 4 trimestres
        y = contrib.assign(ano=contrib.index.year)[["ano"] + cols]
        return y.groupby("ano")[cols].sum().T.rename_axis("fator")
    return contrib[cols].mean().to_frame("contribuicao_p.p.")


def decompose_period(q: pd.DataFrame, phillips: dict, start: str, end: str,
                     meta: float = 3.0) -> pd.DataFrame:
    """Decomposição do desvio ACUMULADO em 4T no período (como no ofício 374)."""
    d = decompose(q, phillips, start, end, meta)
    cols = ["inercia", "expect", "importada", "cambio", "hiato", "clima", "residual"]
    return d[cols].sum().to_frame("contribuicao_4t_p.p.")
