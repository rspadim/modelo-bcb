"""Leitura do cenário do RPM e construção das trajetórias de condicionamento."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import yaml

CONFIG = Path(__file__).resolve().parent.parent / "config" / "rpm_2026q2.yaml"


def load() -> dict:
    with open(CONFIG, encoding="utf-8") as f:
        return yaml.safe_load(f)


def rpm_ipca_path(cfg: dict) -> pd.DataFrame:
    """Trajetória trimestral do IPCA acumulado 4T do cenário de referência."""
    rows = []
    for year, quads in cfg["ipca_acum4t"].items():
        for q, v in quads.items():
            rows.append({"period": f"{year}Q{q[1]}", "rpm_ipca4": v})
    df = pd.DataFrame(rows)
    df["period"] = pd.PeriodIndex(df["period"], freq="Q")
    return df.set_index("period")


def selic_path(cfg: dict, start: str, end: str) -> pd.Series:
    """Trajetória da Selic (pesquisa Focus) interpolada linearmente entre âncoras."""
    anchors = {}
    for year, quads in cfg["selic_focus"].items():
        for q, v in quads.items():
            anchors[pd.Period(f"{year}Q{q[1]}")] = v
    periods = pd.period_range(start, end, freq="Q")
    x = np.array([p.ordinal for p in sorted(anchors)], dtype=float)
    y = np.array([anchors[p] for p in sorted(anchors)], dtype=float)
    xq = np.array([p.ordinal for p in periods], dtype=float)
    vals = np.interp(xq, x, y)
    # além da última âncora, mantém o último valor
    return pd.Series(vals, index=periods)
