"""Gera as figuras da documentação a partir das saídas do MODELO INTEGRADO."""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "modelo-integrado" / "src"))
OUT = ROOT / "modelo-integrado" / "output"
FIG = ROOT / "docs" / "figures"
FIG.mkdir(exist_ok=True)

BLUE = "#1f77b4"
RED = "#d62728"


def main() -> None:
    # 1) Projeção integrada vs RPM
    pr = pd.read_csv(OUT / "projecao_integrada.csv")
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.plot(pr["period"], pr["rpm_ipca4"], "r-o", lw=2, label="Cenário oficial (RPM jun/2026)")
    ax.plot(pr["period"], pr["pi4"], "b-o", lw=2, label="Modelo integrado")
    ax.axhline(3.0, color="black", ls=":", lw=1)
    ax.set_title("Modelo integrado — IPCA acumulado 4T vs cenário oficial")
    ax.set_ylabel("% a.a.")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(FIG / "projecao_integrada.png", dpi=140)
    plt.close(fig)

    # 2) Backtest integrado por horizonte
    bt = pd.read_csv(OUT / "backtest_integrado.csv").dropna(subset=["realizado"])
    bt["abs"] = bt["abs"] if "abs" in bt else (bt["modelo"] - bt["realizado"]).abs()
    mae_h = bt.groupby("horizon")["abs"].mean()
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(mae_h.index, mae_h.values, color=BLUE, alpha=0.8)
    ax.set_title("Backtest integrado — MAE por horizonte (vintages PIT)")
    ax.set_xlabel("Horizonte (trimestres)")
    ax.set_ylabel("MAE (p.p.)")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIG / "backtest_integrado.png", dpi=140)
    plt.close(fig)

    print("Figuras geradas em docs/figures/: projecao_integrada.png, backtest_integrado.png")


if __name__ == "__main__":
    main()
