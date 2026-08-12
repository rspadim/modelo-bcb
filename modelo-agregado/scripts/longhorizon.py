"""Projeção recursiva de longo prazo: modelo re-estimado a cada vintage point-in-time.

Para cada vintage t (snapshot pt_<t>, de 2019Q1 em diante), estima o modelo com os
dados DISPONÍVEIS ATÉ t (ref_date ≤ t e available_from ≤ t) e projeta 1 e 4
trimestres à frente, comparando o IPCA acumulado em 4 trimestres previsto com o
realizado (série mais recente — usado só como alvo de avaliação).

Uso:
    python scripts/longhorizon.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src import data as data_mod, equations, gap as gap_mod, system as system_mod

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SNAP = ROOT.parent / "downloader" / "data" / "snapshots"
OUT = ROOT / "output"


def _acum4(pi: pd.Series) -> float:
    return (np.prod(1 + np.asarray(pi) / 100.0) - 1) * 100


def main() -> None:
    OUT.mkdir(exist_ok=True)
    # realizado: série mais recente (alvo de avaliação, NÃO entra na estimação/projeção)
    realized_q = data_mod.build_quarterly(data_mod.load_snapshot("pt_latest")).loc["2002Q1":]

    vintages = sorted(p.name for p in SNAP.glob("pt_*") if not p.name.startswith("pt_latest"))
    vintages = [v for v in vintages if v <= "pt_2026Q1"]

    rows = []
    for vintage in vintages:
        df = data_mod.load_snapshot(vintage)
        q = data_mod.build_quarterly(df)
        q = q.loc["2002Q1":]
        if len(q) < 40:
            continue
        # PIT: o hiato (HP) é calculado APENAS sobre os dados da própria vintage
        q = gap_mod.add_gap(q)
        try:
            est = equations.estimate_all(q)
            model = system_mod.ModelSystem(est, q, {"w_livres": data_mod.W_LIVRES})
            fc = model.forecast(horizon=4)
        except Exception:  # noqa: BLE001
            continue

        t_period = q.index[-1].to_period("Q")
        tgt1 = t_period + 1
        tgt4 = t_period + 4
        fc_pi4_4 = _acum4(fc["pi"].iloc[:4])
        ts = lambda p: p.end_time.normalize()  # noqa: E731
        if ts(tgt1) not in realized_q.index or ts(tgt4) not in realized_q.index:
            continue  # alvo ainda sem realizado

        rows.append({
            "vintage": str(t_period), "tgt1": str(tgt1), "tgt4": str(tgt4),
            "prev_1q": fc["pi4"].iloc[0],   # acumulado-4T terminando em t+1
            "prev_4q": fc_pi4_4,            # acumulado dos 4 trimestres previstos
            "real_1q": realized_q.loc[ts(tgt1), "pi4"],
            "real_4q": realized_q.loc[ts(tgt4), "pi4"],
        })

    res = pd.DataFrame(rows)
    res.to_csv(OUT / "longhorizon.csv", index=False)

    print(f"Projeções recursivas: {len(res)} vintages ({res['vintage'].iloc[0]}–{res['vintage'].iloc[-1]})")
    mae1 = (res["prev_1q"] - res["real_1q"]).abs().mean()
    mae4 = (res["prev_4q"] - res["real_4q"]).abs().mean()
    print(f"MAE 1T à frente (acumulado-4T): {mae1:.2f} p.p.")
    print(f"MAE 4T à frente (acumulado-4T): {mae4:.2f} p.p.")

    fig, ax = plt.subplots(figsize=(13, 6))
    x = pd.PeriodIndex(res["vintage"].astype(str), freq="Q").to_timestamp(how="end")
    ax.plot(x, res["real_4q"], "k-", lw=2, label="Realizado (IPCA acum. 4T)")
    ax.plot(x, res["prev_1q"], "b-o", ms=3, lw=1.2, label="Modelo — 1T à frente")
    ax.plot(x, res["prev_4q"], "r--s", ms=3, lw=1.2, label="Modelo — 4T à frente (fora de amostra)")
    ax.axhline(3.0, color="gray", ls=":", lw=1, label="Meta (3%)")
    ax.axhspan(1.5, 4.5, color="gray", alpha=0.08)
    ax.set_title("Modelo vs realizado — projeção recursiva por vintage (PIT)")
    ax.set_ylabel("% a.a. (acumulado em 4 trimestres)")
    ax.legend(fontsize=9, loc="upper left")
    ax.grid(alpha=0.3)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(OUT / "longhorizon_modelo_vs_realizado.png", dpi=140)
    print(f"Gráfico: {OUT / 'longhorizon_modelo_vs_realizado.png'}")
    plt.close(fig)


if __name__ == "__main__":
    main()
