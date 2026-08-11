"""Runner do modelo agregado: base → hiato → estimação → projeção → fan chart → comparação.

Uso:
    python scripts/run_aggregate.py [--vintage pt_2026Q2] [--draws 2000]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import data as data_mod
from src import equations, gap as gap_mod, rpm as rpm_mod, system as system_mod

OUT = ROOT / "output"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vintage", default="pt_2026Q2")
    ap.add_argument("--draws", type=int, default=2000)
    ap.add_argument("--horizon", type=int, default=12)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)

    df = data_mod.load_snapshot(args.vintage)
    q = data_mod.build_quarterly(df)
    q = gap_mod.add_gap(q)
    q = q.loc["2002Q1":]

    est = equations.estimate_all(q)
    cfg_rpm = rpm_mod.load()

    for name, r in est.items():
        print(f"\n=== {name.upper()} (n={r['n']}, R2={r['r2']:.3f}) ===")
        for k, v in r["params"].items():
            sig = "***" if r["pvalues"][k] < 0.01 else "**" if r["pvalues"][k] < 0.05 else "*" if r["pvalues"][k] < 0.1 else ""
            print(f"  {k:12s} {v:8.4f} (se {r['stderr'][k]:.4f}){sig}")

    model = system_mod.ModelSystem(est, q, {"w_livres": data_mod.W_LIVRES})

    last_q = q.index[-1].to_period("Q")
    next_q = last_q + 1
    end_q = next_q + (args.horizon - 1)

    # Variante 1: Selic condicionada à trajetória do RPM (Focus)
    sp = rpm_mod.selic_path(cfg_rpm, str(next_q), str(end_q))
    fc_cond = model.forecast(horizon=args.horizon, selic_path=sp)
    # Variante 2: Selic endógena (regra de Taylor)
    fc_end = model.forecast(horizon=args.horizon)

    fan = system_mod.monte_carlo(model, horizon=args.horizon, n_draws=args.draws, seed=args.seed)

    # ---- Comparação com o cenário oficial do RPM ----
    rpm_path = rpm_mod.rpm_ipca_path(cfg_rpm)
    comp = pd.DataFrame({
        "period": fc_cond["period"],
        "pi4_modelo_cond": fc_cond["pi4"].values,
        "pi4_modelo_taylor": fc_end["pi4"].values,
        "fan_50lo": fan["25"].values,
        "fan_50hi": fan["75"].values,
        "fan_90lo": fan["5"].values,
        "fan_90hi": fan["95"].values,
    }).set_index("period")
    comp.index = pd.PeriodIndex(comp.index, freq="Q")
    comp = comp.join(rpm_path, how="outer").sort_index()

    # métricas vs RPM no overlap (12 trimestres a partir de 2026Q2)
    valid = comp.dropna(subset=["rpm_ipca4", "pi4_modelo_cond"])
    mae_cond = (valid["pi4_modelo_cond"] - valid["rpm_ipca4"]).abs().mean()
    mae_tay = (valid["pi4_modelo_taylor"] - valid["rpm_ipca4"]).abs().mean()
    first = valid.iloc[0]

    print("\n===== VALIDAÇÃO vs CENÁRIO RPM JUN/2026 =====")
    print(comp.to_string())
    print(f"\nMAE (modelo condicionado, {len(valid)} trimestres): {mae_cond:.3f} p.p.")
    print(f"MAE (Selic Taylor): {mae_tay:.3f} p.p.")
    print(f"1º trimestre ({valid.index[0]}): modelo={first['pi4_modelo_cond']:.2f} vs RPM={first['rpm_ipca4']:.2f} "
          f"(dif {first['pi4_modelo_cond'] - first['rpm_ipca4']:.3f} p.p.)")

    # Projeção oficial dentro do leque
    inside_50 = ((comp["rpm_ipca4"] >= comp["fan_50lo"]) & (comp["rpm_ipca4"] <= comp["fan_50hi"])).sum()
    inside_90 = ((comp["rpm_ipca4"] >= comp["fan_90lo"]) & (comp["rpm_ipca4"] <= comp["fan_90hi"])).sum()
    n = comp["rpm_ipca4"].notna().sum()
    print(f"Cenário oficial dentro do leque 50%: {inside_50}/{n}")
    print(f"Cenário oficial dentro do leque 90%: {inside_90}/{n}")

    comp.to_csv(OUT / "comparacao_rpm.csv", encoding="utf-8-sig")

    # ---- Gráficos ----
    fig, ax = plt.subplots(figsize=(11, 6))
    periods = comp.index.astype(str)
    ax.plot(periods, comp["rpm_ipca4"], "r-o", lw=2, label="Cenário oficial (RPM jun/2026)")
    ax.plot(periods, comp["pi4_modelo_cond"], "b-o", lw=2, label="Modelo (Selic condicionada)")
    ax.plot(periods, comp["pi4_modelo_taylor"], "g--o", lw=1.5, label="Modelo (Selic Taylor)")
    ax.fill_between(periods, comp["fan_50lo"], comp["fan_50hi"], alpha=0.25, color="blue", label="Leque 50%")
    ax.fill_between(periods, comp["fan_90lo"], comp["fan_90hi"], alpha=0.12, color="blue", label="Leque 90%")
    ax.axhline(3.0, color="black", ls=":", lw=1, label="Meta (3%)")
    ax.axhspan(1.5, 4.5, color="gray", alpha=0.08)
    ax.set_title("IPCA acumulado em 4 trimestres — modelo agregado vs cenário oficial")
    ax.set_ylabel("% a.a.")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(OUT / "fan_chart_agregado.png", dpi=140)
    print(f"\nGráfico salvo em {OUT / 'fan_chart_agregado.png'}")
    plt.close(fig)


if __name__ == "__main__":
    main()
