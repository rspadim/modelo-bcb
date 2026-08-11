"""Runner do modelo completo: setores → Kalman → Phillips setoriais → sistema → projeção.

Uso:
    python scripts/run_complete.py [--vintage pt_2026Q2]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # pacote src = modelo-completo/src
sys.path.insert(0, str(ROOT.parent / "modelo-agregado" / "src"))  # módulos planos agregados

from src import data as dcomplete
from src import gap as kgap
from src import phillips as pset
from src import sector as sector_mod
from src import system as csystem
import equations as eqmod
import rpm as rpm_mod

OUT = ROOT / "output"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vintage", default="pt_2026Q2")
    ap.add_argument("--horizon", type=int, default=12)
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)

    df = dcomplete.load_snapshot(args.vintage)
    q = dcomplete.build_complete_quarterly(df)
    q = kgap.add_gap_kalman(q)
    q = q.loc["2020Q1":]

    # Phillips setoriais (amostra SIDRA)
    sp = pset.estimate_sectoral_phillips(q)
    print("=== PHILLIPS SETORIAIS (amostra SIDRA 2020+) ===")
    for s, r in sp.items():
        if r is None:
            print(f"  {s}: dados insuficientes")
            continue
        print(f"  {s:12s} n={r['n']} R2={r['r2']:.3f} | inércia={r['params']['pi_1']:.2f} "
              f"expect={r['params']['e_pi_next']:.2f} gap={r['params']['gap_1']:.3f} "
              f"câmbio={r['params']['dln_cambio']:.4f}")

    # Demais equações (reutiliza o estimador do modelo agregado)
    est = eqmod.estimate_all(q)
    # remove phillips agregada (usaremos as setoriais)
    est.pop("phillips", None)
    est["phillips"] = sp

    model = csystem.CompleteSystem(est, q, {})
    w = model.w
    print(f"\nPesos (média da amostra): livres={ (w['servicos']+w['industriais']+w['alimentacao'])*100:.1f}% "
          f"admin={w['admin']*100:.1f}% | dentro de livres: serv={w['servicos']/model.w_livres*100:.0f}% "
          f"ind={w['industriais']/model.w_livres*100:.0f}% "
          f"alim={w['alimentacao']/model.w_livres*100:.0f}%")

    cfg_rpm = rpm_mod.load()
    last_q = q.index[-1].to_period("Q")
    next_q = last_q + 1
    end_q = next_q + (args.horizon - 1)
    spath = rpm_mod.selic_path(cfg_rpm, str(next_q), str(end_q))

    fc = model.forecast(horizon=args.horizon, selic_path=spath)
    rpm_path = rpm_mod.rpm_ipca_path(cfg_rpm)
    comp = fc.set_index("period")
    comp.index = pd.PeriodIndex(comp.index, freq="Q")
    comp = comp.join(rpm_path).sort_index()

    valid = comp.dropna(subset=["rpm_ipca4", "pi4"])
    mae = (valid["pi4"] - valid["rpm_ipca4"]).abs().mean()
    print(f"\n===== VALIDAÇÃO COMPLETO vs RPM JUN/2026 =====")
    print(f"MAE ({len(valid)} trimestres): {mae:.3f} p.p.")
    print(comp[["pi4", "pi_l", "pi_a", "servicos", "industriais", "alimentacao", "rpm_ipca4"]].round(2).to_string())

    comp.to_csv(OUT / "comparacao_completo.csv", encoding="utf-8-sig")

    # ---- Repasse cambial: choque +10% USD/BRL ----
    base = model.forecast(horizon=12, selic_path=spath)
    shock = model.forecast(horizon=12, selic_path=spath, shock_cambio_pp=10.0)
    pr = pd.DataFrame({
        "period": base["period"],
        "dpi_total": shock["pi4"] - base["pi4"],
        "dservicos": shock["servicos"] - base["servicos"],
        "dindustriais": shock["industriais"] - base["industriais"],
        "dalimentacao": shock["alimentacao"] - base["alimentacao"],
    })
    print("\n===== REPASSE CAMBIAL: +10% USD/BRL (diferença, p.p.) =====")
    print(pr.round(3).to_string())
    pr.to_csv(OUT / "repasse_cambial.csv", index=False)

    # ---- Gráfico ----
    fig, ax = plt.subplots(figsize=(11, 6))
    periods = comp.index.astype(str)
    ax.plot(periods, comp["rpm_ipca4"], "r-o", lw=2, label="Cenário oficial (RPM jun/2026)")
    ax.plot(periods, comp["pi4"], "b-o", lw=2, label="Modelo completo")
    ax.axhline(3.0, color="black", ls=":", lw=1)
    ax.axhspan(1.5, 4.5, color="gray", alpha=0.08)
    ax.set_title("IPCA acumulado 4T — modelo completo (3 Phillips setoriais) vs cenário oficial")
    ax.set_ylabel("% a.a.")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(OUT / "fan_chart_completo.png", dpi=140)
    print(f"\nGráfico: {OUT / 'fan_chart_completo.png'}")
    plt.close(fig)


if __name__ == "__main__":
    main()
