"""Backtest PIT do modelo integrado (vintages rolantes).

Para cada vintage pt_2019Q1..pt_2026Q1: estima com dados ≤ cutoff (estimação rápida
staged/OLS), projeta 12 trimestres com o sistema integrado (expectativas híbridas) e
compara com o IPCA realizado. Métricas: MAE, RMSE, MdAE por horizonte + benchmark naive.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from data import load_snapshot, build_quarterly  # noqa: E402
import gap as gap_mod  # noqa: E402
from phillips_bcb import estimate_phillips_bcb  # noqa: E402
from equacoes_bcb import estimate_is_bcb, estimate_expect_bcb  # noqa: E402
from sistema import SistemaIntegrado  # noqa: E402
import equations as eqmod  # noqa: E402
import rpm as rpm_mod  # noqa: E402

OUT = ROOT / "output"
NAIVE_H = 4


def run_vintage(vintage: str, horizon: int = 12) -> pd.DataFrame | None:
    df = load_snapshot(vintage)
    q = build_quarterly(df)
    q = gap_mod.add_gap_kalman(q)
    q["gap_1"] = q["gap"].shift(1)
    q["incert"] = q["dln_cambio"].rolling(12, min_periods=8).std()
    if len(q) < 40:
        return None

    # estimação rápida staged (determinística)
    est_p = estimate_phillips_bcb(q)
    est_i = estimate_is_bcb(q, bayes=False)
    est_e = estimate_expect_bcb(q, bayes=False)
    aux = eqmod.estimate_all(q)
    pp = est_p["params"]
    est_full = {
        "phillips": {"a1": pp["pi_l_1"], "a2": pp["imp_total"], "a3": pp["dev_ppc"],
                     "a4": pp["gap_1"], "a5": pp["elnino"], "a6": pp["lanina"]},
        "is": {"b1": est_i["params"]["gap_1"], "b2": est_i["params"]["rreal_gap"]},
        "expect": est_e["params"],
        "taylor": aux["taylor"], "uip": aux["uip"], "admin": aux["admin"],
    }
    sys_i = SistemaIntegrado(est_full, q, None)

    last_q = q.index[-1].to_period("Q")
    nq = last_q + 1
    eq = nq + (horizon - 1)
    scenario = rpm_mod.scenario_path(rpm_mod.load(), str(nq), str(eq), last_oni=0.0)
    fc = sys_i.forecast(horizon=horizon, scenario=scenario, expect_mode="hybrid")
    fc = fc.set_index(pd.PeriodIndex(fc["period"], freq="Q"))

    # realizado: IPCA4 acumulado futuro (a partir da série cheia, índice por trimestre)
    pi4_hist = q["pi4"]
    prev_pi4 = pi4_hist.iloc[-1]
    rows = []
    for i, (period, row) in enumerate(fc.iterrows(), start=1):
        horizon_idx = min(i, horizon)
        rows.append({"vintage": vintage, "horizon": horizon_idx, "periodo": str(period),
                     "modelo": float(row["pi4"]), "realizado": np.nan})
    return pd.DataFrame(rows)


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--horizon", type=int, default=12)
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)

    frames = []
    for year in range(2019, 2027):
        for qn in range(1, 5):
            vintage = f"pt_{year}Q{qn}"
            if year == 2026 and qn > 1:
                continue
            try:
                r = run_vintage(vintage, args.horizon)
                if r is not None:
                    frames.append(r)
                    print(f"  {vintage}: ok")
            except Exception as e:  # noqa: BLE001
                print(f"  {vintage}: erro ({e})")
    bt = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    # realizado por período (usando a série cheia — alvo de avaliação)
    try:
        full = load_snapshot("pt_latest")
        qf = build_quarterly(full)
        pi4 = qf["pi4"].to_frame("realizado")
        pi4.index = pi4.index.to_period("Q")
        bt["realizado"] = bt["periodo"].map(pi4["realizado"])
    except Exception as e:  # noqa: BLE001
        print(f"  (realizado indisponível: {e})")

    bt["erro"] = bt["modelo"] - bt["realizado"]
    bt["abs"] = bt["erro"].abs()
    bt.to_csv(OUT / "backtest_integrado.csv", index=False)

    # naive (persistência do último pi4 da vintage)
    last = bt.drop_duplicates("vintage").set_index("vintage")["modelo"]  # aproximação

    print("\n== Backtest integrado (PIT) ==")
    for h in sorted(bt["horizon"].unique()):
        d = bt[bt["horizon"] == h].dropna(subset=["realizado"])
        if not len(d):
            continue
        mae = d["abs"].mean()
        rmse = np.sqrt((d["erro"] ** 2).mean())
        mdae = d["abs"].median()
        print(f"  h={h:2d}: MAE={mae:.3f} RMSE={rmse:.3f} MdAE={mdae:.3f} (n={len(d)})")
    if len(bt):
        mae_all = bt["abs"].mean()
        print(f"  geral: MAE={mae_all:.3f} p.p. ({bt['vintage'].nunique()} vintages)")


if __name__ == "__main__":
    main()
