"""run_integrado.py — o MODELO ÚNICO integrado da réplica.

1) Estima a CONJUNTA PLENA (PyMC, hiato + neutra + Phillips/IS/expectativas) — default;
   `--est staged` usa o MLE/estágios como fallback.
2) Projeta com o sistema único (admin endógeno + expectativas consistentes) e o cenário RPM.
3) Valida contra o PDF: IRFs vs RI dez/2021, MAE vs RPM, juro neutra.

Uso:
    python scripts/run_integrado.py [--draws 400] [--est conjunta|staged]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
for p in [ROOT / "src", ROOT.parent / "modelo-agregado" / "src", ROOT.parent / "modelo-completo"]:
    sys.path.insert(0, str(p))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from data import load_snapshot, build_quarterly  # noqa: E402
import gap as gap_mod  # noqa: E402
from estimador_conjunto import estimar_conjunta  # noqa: E402
from sistema import SistemaIntegrado  # noqa: E402
from equacoes_bcb import estimate_is_bcb, estimate_expect_bcb, _hp_cycle  # noqa: E402
from phillips_bcb import estimate_phillips_bcb_bayes  # noqa: E402
from src import spec_manifesto as spec_man  # noqa: E402
import equations as eqmod  # noqa: E402
import rpm as rpm_mod  # noqa: E402

OUT = ROOT.parent / "modelo-integrado" / "output"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vintage", default="pt_2026Q2")
    ap.add_argument("--horizon", type=int, default=12)
    ap.add_argument("--draws", type=int, default=400)
    ap.add_argument("--tune", type=int, default=250)
    ap.add_argument("--est", choices=["conjunta", "staged"], default="conjunta")
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)

    df = load_snapshot(args.vintage)
    cutoff = pd.Timestamp(df["available_from"].max()) if "available_from" in df.columns else pd.NaT
    if not spec_man.check_spec("rpm_2026q2", cutoff) or not spec_man.check_spec("priors_agregado", cutoff):
        sys.exit("[spec_manifesto] especificação/cenário posterior ao cutoff da vintage — abortando.")
    q = build_quarterly(df)
    q = gap_mod.add_gap_kalman(q)
    q["gap_1"] = q["gap"].shift(1)
    q["incert"] = q["dln_cambio"].rolling(12, min_periods=8).std()

    print(f"== MODELO ÚNICO INTEGRADO (estimação {args.est}; hiato por estado-espaço) ==\n")

    # ---- estimação ----
    if args.est == "conjunta":
        print(f"Estimando a CONJUNTA PLENA (PyMC, {args.draws} amostras)...")
        res = estimar_conjunta(q, draws=args.draws, tune=args.tune)
        pp = res["params"]
        gap_s = res["gap"]
        neutra_s = res["rbar"]
    else:  # staged fallback
        est_p = estimate_phillips_bcb_bayes(q, draws=args.draws, tune=args.tune)
        est_i = estimate_is_bcb(q, draws=args.draws, tune=args.tune)
        est_e = estimate_expect_bcb(q, draws=args.draws, tune=args.tune)
        pp = {"a1": est_p["params"]["pi_l_1"], "a2": est_p["params"]["imp_total"],
              "a3": est_p["params"]["dev_ppc"], "a4": est_p["params"]["gap_1"],
              "a5": est_p["params"]["elnino"], "a6": est_p["params"]["lanina"],
              "b1": est_i["params"]["gap_1"], "b2": est_i["params"]["rreal_gap"]}
        gap_s = q["gap"]
        neutra_s = pd.Series(5.0, index=q.index)

    print("Parâmetros conjuntos:")
    for k in ["a1", "a2", "a3", "a4", "b1", "b2"]:
        print(f"  {k:3s} = {pp[k]:.4f}")
    print(f"  juro neutra: média {neutra_s.mean():.2f} (fim {neutra_s.iloc[-1]:.2f})")
    print(f"  hiato: média {gap_s.mean():.2f} min {gap_s.min():.2f} max {gap_s.max():.2f}")

    # ---- sistema único ----
    est_e = estimate_expect_bcb(q, draws=120, tune=80)
    aux = eqmod.estimate_all(q)
    est_full = {
        "phillips": pp,
        "is": {"b1": pp["b1"], "b2": pp["b2"]},
        "expect": est_e["params"],
        "taylor": aux["taylor"], "uip": aux["uip"], "admin": aux["admin"],
    }
    sys_integ = SistemaIntegrado(est_full, q, admin_est=None)
    sys_integ.neutra = float(neutra_s.iloc[-1])

    cfg = rpm_mod.load()
    last_q = q.index[-1].to_period("Q")
    nq = last_q + 1
    eq = nq + (args.horizon - 1)
    scenario = rpm_mod.scenario_path(cfg, str(nq), str(eq),
                                     last_oni=float(q["oni"].dropna().iloc[-1]))

    # ---- projeção ----
    fc = sys_integ.forecast(horizon=args.horizon, scenario=scenario, expect_mode="consistent")
    rpm_path = rpm_mod.rpm_ipca_path(cfg)
    comp = fc.set_index("period")
    comp.index = pd.PeriodIndex(comp.index, freq="Q")
    comp = comp.join(rpm_path).sort_index()
    valid = comp.dropna(subset=["pi4", "rpm_ipca4"])
    mae = (valid["pi4"] - valid["rpm_ipca4"]).abs().mean()
    print(f"\nMAE vs RPM jun/2026 ({len(valid)} trimestres): {mae:.3f} p.p.")
    comp.to_csv(OUT / "projecao_integrada.csv", index_label="period")

    # ---- IRFs vs RI dez/2021 ----
    base = sys_integ.forecast(horizon=args.horizon, scenario=scenario)
    irf_gap = sys_integ.forecast(horizon=args.horizon, scenario=scenario, shock_gap_pp=-1.0)
    irf_cam = sys_integ.forecast(horizon=args.horizon, scenario=scenario, shock_cambio_pp=10.0)
    d_gap = irf_gap["pi4"] - base["pi4"]
    d_cam = irf_cam["pi4"] - base["pi4"]
    print("\nIRFs (Δ p.p. IPCA 4T) vs RI dez/2021:")
    print(f"  demanda −1 p.p. (hiato): pico {d_gap.abs().max():.3f} p.p. (RI: −0,45)")
    print(f"  câmbio +10%: pico {d_cam.abs().max():.3f} p.p.")
    pd.DataFrame({"demanda": d_gap, "cambio": d_cam}).to_csv(OUT / "irfs_integradas.csv",
                                                              index_label="period")

    # ---- hiato/neutra suavizados para inspeção ----
    gap_s.to_frame("gap").to_csv(OUT / "hiato_integrado.csv", index_label="period")
    neutra_s.to_frame("neutra").to_csv(OUT / "neutra_integrada.csv", index_label="period")


if __name__ == "__main__":
    main()
