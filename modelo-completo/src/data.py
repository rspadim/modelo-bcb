"""Base trimestral do modelo completo: setores + agregados."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "modelo-agregado" / "src"))
from data import build_quarterly, load_snapshot  # noqa: E402

from . import sector  # noqa: E402


def build_complete_quarterly(df: pd.DataFrame) -> pd.DataFrame:
    q = build_quarterly(df)  # agregado (com e_pi_next, gap via HP, etc.)
    sub = df[(df["source"] == "sidra") & (df["variable"].isin([63, 66]))]
    v, w = sector.build_sectoral_monthly(sub)

    # setoriais mensais -> trimestrais (composto de 3 meses)
    def to_q(s):
        return s.resample("QE").apply(
            lambda x: (np.prod(1 + np.asarray(x.dropna()) / 100.0) - 1) * 100
            if len(x.dropna()) >= 3 else np.nan)

    qsec = pd.DataFrame({c: to_q(v[c]) for c in sector.SETORES})
    wq = pd.DataFrame({c: w[c].resample("QE").mean() for c in sector.SETORES})

    out = q.join(qsec).join(wq, rsuffix="_w")
    out = out.rename(columns={f"{c}_w": f"w_{c}" for c in sector.SETORES})
    # IC-Br tem lacunas (rebase do índice em 2024-25): ffill para não perder amostra
    out["pi_com"] = out["pi_com"].ffill()
    # livres setorial = soma ponderada dos 3 setores livres (para validar consistência)
    out["livres_set"] = (
        out["servicos"] * out["w_servicos"] + out["industriais"] * out["w_industriais"]
        + out["alimentacao"] * out["w_alimentacao"]
    ) / out[["w_servicos", "w_industriais", "w_alimentacao"]].sum(axis=1)
    return out
