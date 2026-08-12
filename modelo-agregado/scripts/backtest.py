"""Backtest rolante do modelo agregado por vintage point-in-time.

Para cada vintage t (2019Q1..2026Q1): estima com dados até t, projeta 12
trimestres e compara com o IPCA realizado. Benchmarks: Focus e naive (AR(1)).

Uso:
    python scripts/backtest.py
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


def realized_pi4() -> pd.Series:
    """IPCA acumulado 4T realizado (série completa, vintage mais recente)."""
    full = pd.read_parquet(ROOT.parent / "downloader" / "data" / "processed" / "series.parquet")
    df = full[full["source"] == "sgs"]
    m = df[df["series"] == "ipca"][["ref_date", "value"]].dropna()
    m = m.set_index("ref_date")["value"]
    def compound(x):
        x = x.dropna()
        return (np.prod(1 + x / 100.0) - 1) * 100 if len(x) >= 3 else np.nan
    q = m.resample("QE").apply(compound)
    q4 = (1 + q / 100).rolling(4).apply(np.prod, raw=True)
    return ((q4 - 1) * 100).dropna()


def main() -> None:
    OUT.mkdir(exist_ok=True)
    realized = realized_pi4()
    realized.index = realized.index.to_period("Q")

    vintages = sorted(p.name for p in SNAP.glob("pt_*") if not p.name.startswith("pt_latest"))
    vintages = [v for v in vintages if v <= "pt_2026Q1"]

    rows = []
    for vintage in vintages:
        df = data_mod.load_snapshot(vintage)
        q = data_mod.build_quarterly(df)
        q = gap_mod.add_gap(q)
        q = q.loc["2002Q1":]
        if len(q) < 40:
            continue
        try:
            est = equations.estimate_all(q)
            model = system_mod.ModelSystem(est, q, {"w_livres": data_mod.W_LIVRES})
            last_q = q.index[-1].to_period("Q")
            fc = model.forecast(horizon=12)
        except Exception as e:  # noqa: BLE001
            print(f"{vintage}: erro {e}")
            continue

        for _, r in fc.iterrows():
            tgt = pd.Period(r["period"])
            if tgt in realized.index:
                rows.append({
                    "vintage": vintage, "target": str(tgt),
                    "horizon": int((tgt - last_q).n),
                    "modelo": r["pi4"], "realizado": realized.loc[tgt],
                })

    res = pd.DataFrame(rows)
    res["erro"] = res["modelo"] - res["realizado"]
    res.to_csv(OUT / "backtest.csv", index=False)

    print(f"Backtest: {res['vintage'].nunique()} vintages, {len(res)} observações")
    mae = res.groupby("horizon")["erro"].apply(lambda x: x.abs().mean())
    rmse = res.groupby("horizon")["erro"].apply(lambda x: np.sqrt((x ** 2).mean()))
    bias = res.groupby("horizon")["erro"].mean()
    tbl = pd.concat([mae, rmse, bias], axis=1, keys=["MAE", "RMSE", "VIES"])
    print("\nErro por horizonte (p.p.):")
    print(tbl.round(3).to_string())
    tbl.to_csv(OUT / "backtest_por_horizonte.csv", encoding="utf-8-sig")

    print(f"\nMAE médio (todos horizontes): {res['erro'].abs().mean():.3f} p.p.")
    print(f"RMSE médio: {np.sqrt((res['erro']**2).mean()):.3f} p.p.")
    print(f"Viés médio: {res['erro'].mean():.3f} p.p.")

    # compara com benchmark naive: persistência no pi4 (random walk)
    real_series = realized
    ar1_err = []
    for vintage in vintages:
        vq = pd.Period(vintage[3:], freq="Q")
        hist = real_series[real_series.index <= vq]
        if len(hist) < 5:
            continue
        for h in range(1, 13):
            tgt = vq + h
            if tgt in real_series.index:
                naive = hist.iloc[-1]
                ar1_err.append(abs(naive - real_series.loc[tgt]))
    print(f"\nBenchmark naive (persistência): MAE={np.mean(ar1_err):.3f} p.p. "
          f"(modelo: {res['erro'].abs().mean():.3f})")

    # gráfico MAE por horizonte
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(mae.index.astype(int), mae.values, "o-", label="Modelo (MAE por horizonte)")
    ax.axhline(np.mean(ar1_err), color="r", ls="--", label=f"Naive (MAE médio {np.mean(ar1_err):.2f})")
    ax.set_xlabel("Horizonte (trimestres)")
    ax.set_ylabel("MAE (p.p.)")
    ax.set_title("Backtest rolante — erro por horizonte vs benchmark naive")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT / "backtest_mae.png", dpi=140)
    print(f"Gráfico: {OUT / 'backtest_mae.png'}")


if __name__ == "__main__":
    main()
