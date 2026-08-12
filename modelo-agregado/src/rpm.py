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


def _anchor_series(cfg: dict, key: str, start: str, end: str) -> pd.Series:
    """Interpola linearmente as âncoras trimestrais de um bloco do YAML."""
    anchors = {}
    for year, quads in cfg.get(key, {}).items():
        for q, v in quads.items():
            anchors[pd.Period(f"{year}Q{q[1]}")] = float(v)
    if not anchors:
        return pd.Series(dtype=float)
    periods = pd.period_range(start, end, freq="Q")
    x = np.array([p.ordinal for p in sorted(anchors)], dtype=float)
    y = np.array([anchors[p] for p in sorted(anchors)], dtype=float)
    xq = np.array([p.ordinal for p in periods], dtype=float)
    return pd.Series(np.interp(xq, x, y), index=periods)


def brent_path(cfg: dict, start: str, end: str) -> pd.Series:
    """Trajetória do Brent (US$/barril); +2% a.a. após a última âncora (2028+)."""
    s = _anchor_series(cfg, "brent", start, end)
    if s.empty:
        return s
    periods = pd.period_range(start, end, freq="Q")
    last_anchor = max(pd.Period(f"{y}Q{q[1]}") for y, qs in cfg["brent"].items() for q in qs)
    last_val = float(cfg["brent"][last_anchor.year][f"Q{last_anchor.quarter}"])
    growth_q = 1.02 ** 0.25  # +2% a.a. composto ao trimestre
    for p in periods:
        if p > last_anchor:
            s.loc[p] = last_val * growth_q ** ((p.ordinal - last_anchor.ordinal))
    return s


def oni_path(cfg: dict, start: str, end: str, last_observed: float = 0.0) -> pd.Series:
    """Trajetória do ONI no cenário a partir do RONI (El Niño).

    Sobe linearmente de `last_observed` ao pico do RONI (2026Q4 = 2,1°C) e
    normaliza para 0 ao longo dos 4 trimestres seguintes (cenário do RPM).
    """
    roni = cfg.get("roni_cenario", {})
    if not roni:
        return pd.Series(np.full(pd.period_range(start, end, freq="Q").size, last_observed),
                         index=pd.period_range(start, end, freq="Q"))
    peak_q = next(pd.Period(f"{y}Q{q[1]}") for y, qs in roni.items() for q in qs)
    peak = float(roni[peak_q.year][f"Q{peak_q.quarter}"])
    periods = pd.period_range(start, end, freq="Q")
    out = {}
    for p in periods:
        if p <= peak_q:
            n = (peak_q.ordinal - periods[0].ordinal) + 1
            k = (p.ordinal - periods[0].ordinal) / max(n - 1, 1)
            out[p] = last_observed + k * (peak - last_observed)
        else:
            decay = 1 - min((p.ordinal - peak_q.ordinal) / 4.0, 1.0)
            out[p] = peak * max(decay, 0.0)
    return pd.Series(out, index=periods)


def scenario_path(cfg: dict, start: str, end: str, last_oni: float = 0.0) -> pd.DataFrame:
    """Condicionantes completos do cenário de referência, por trimestre.

    Colunas: selic (Focus), dln_cambio (PPC ≈ 1% a.a.), brent, oni (RONI),
    juro_real_neutra (% a.a.).
    """
    periods = pd.period_range(start, end, freq="Q")
    ppc_q = cfg.get("cambio_ppc_depreciacao_aa", 1.0) / 4.0
    out = pd.DataFrame({
        "selic": selic_path(cfg, start, end),
        "dln_cambio": np.full(len(periods), ppc_q),
        "brent": brent_path(cfg, start, end),
        "oni": oni_path(cfg, start, end, last_observed=last_oni),
        "juro_real_neutra": cfg.get("juro_real_neutra", 5.0),
    }, index=periods)
    return out
