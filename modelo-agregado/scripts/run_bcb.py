"""run_bcb.py — estimação fiel ao modelo agregado do BCB (RI dez/2021, boxe b7).

Estimação bayesiana (PyMC) com os priors/suportes publicados, amostra 2003T4–2019T4:
  - Phillips (IC-Br em R$ + câmbio como desvio da PPC + clima assimétrico)
  - IS completa (fiscal ciclo-corrigido + incerteza + hiato mundial)
  - Expectativas com componente consistente com o modelo

Uso:
    python scripts/run_bcb.py [--draws 400]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from data import load_snapshot, build_quarterly  # noqa: E402
import gap as gap_mod  # noqa: E402
from phillips_bcb import estimate_phillips_bcb_bayes, estimate_phillips_bcb  # noqa: E402
from equacoes_bcb import estimate_is_bcb, estimate_expect_bcb  # noqa: E402
from estado_espaco_bcb import estimate_neutral_rate  # noqa: E402
from decomposicao import decompose, decompose_period  # noqa: E402
from system_bcb import BcbSystem  # noqa: E402
import equations as eqmod  # noqa: E402
import rpm as rpm_mod  # noqa: E402

OUT = ROOT / "output"
RI_P = {"pi_l_1": 0.23756, "imp_total": 0.01826, "dev_ppc": 0.01727, "gap_1": 0.13866,
        "elnino": 0.00119, "lanina": 0.00104}
RI_I = {"gap_1": 0.73897, "rreal_gap": 0.54876, "fisc_cc": 0.02985,
        "incert": 0.04073, "us_gap": 0.04342}
RI_E = {"e_prev": 0.73260, "e_consistent": 0.12271, "pi_prev": 0.04370}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vintage", default="pt_2026Q2")
    ap.add_argument("--draws", type=int, default=400)
    ap.add_argument("--tune", type=int, default=250)
    ap.add_argument("--horizon", type=int, default=12)
    ap.add_argument("--gap", choices=["hp", "kalman"], default="kalman",
                    help="hiato do produto: hp ou kalman (estado-espaço, como o BCB)")
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)

    df = load_snapshot(args.vintage)
    q = build_quarterly(df)
    q = gap_mod.add_gap_kalman(q) if args.gap == "kalman" else gap_mod.add_gap(q)
    q["gap_1"] = q["gap"].shift(1)

    print(f"== Estimação BCB (RI dez/2021, priors publicados, 2003T4-2019T4; hiato {args.gap}) ==\n")

    rows = []
    est_p = estimate_phillips_bcb_bayes(q, draws=args.draws, tune=args.tune)
    print("PHILLIPS")
    for k, v in RI_P.items():
        rows.append({"equacao": "Phillips", "param": k, "replica": est_p["params"][k],
                     "RI_2021": v})
        print(f"  {k:9s} replica={est_p['params'][k]:.4f}  RI={v:.4f}")

    est_i = estimate_is_bcb(q, draws=args.draws, tune=args.tune)
    print("\nIS")
    for k, v in RI_I.items():
        rows.append({"equacao": "IS", "param": k, "replica": est_i["params"][k],
                     "RI_2021": v})
        print(f"  {k:9s} replica={est_i['params'][k]:.4f}  RI={v:.4f}")

    est_e = estimate_expect_bcb(q, draws=args.draws, tune=args.tune)
    print("\nEXPECTATIVAS")
    for k, v in RI_E.items():
        rows.append({"equacao": "Expect", "param": k, "replica": est_e["params"][k],
                     "RI_2021": v})
        print(f"  {k:12s} replica={est_e['params'][k]:.4f}  RI={v:.4f}")

    tbl = pd.DataFrame(rows)
    tbl["dif_pp"] = tbl["replica"] - tbl["RI_2021"]
    tbl.to_csv(OUT / "comparacao_bcb_ri2021.csv", index=False)
    print(f"\nComparação salva em {OUT / 'comparacao_bcb_ri2021.csv'}")

    # ---- Juro real neutra latente (P3) ----
    try:
        res_n = estimate_neutral_rate(q)
        print("\nJURO REAL NEUTRA (estado latente, Kalman; RI jun/2024 b11)")
        print(f"  média={res_n['rbar'].mean():.2f} fim-amostra={res_n['rbar'].iloc[-1]:.2f} "
              f"min={res_n['rbar'].min():.2f} max={res_n['rbar'].max():.2f}")
        print(f"  β2 (juro real, IS)={res_n['params']['beta2']:.3f}")
    except Exception as e:  # noqa: BLE001
        print(f"\nJURO NEUTRA: indisponível ({e})")

    # ---- Decomposição de inflação (P6) ----
    try:
        est_p_ols = estimate_phillips_bcb(q)
        dec = decompose_period(q, est_p_ols, "2024Q1", "2024Q4")
        print("\nDECOMPOSIÇÃO 2024 (contribuição ao desvio de livres vs meta, p.p.)")
        print("  ofício 374/2025-BCB: inércia 0,52 | importada 0,72 | hiato 0,49 | expect 0,30")
        print(dec.round(3).to_string())
        dec.to_csv(OUT / "decomposicao_2024.csv", index_label="fator")
    except Exception as e:  # noqa: BLE001
        print(f"\nDECOMPOSIÇÃO: indisponível ({e})")

    # ---- Projeção do agregado BCB com expectativas consistentes (P3/roadmap) ----
    try:
        qf = q.copy()
        qf["incert"] = qf["dln_cambio"].rolling(12, min_periods=8).std()
        # demais equações (Taylor/UIP/admin) no mesmo padrão do modelo atual
        est_aux = eqmod.estimate_all(qf)
        est_full = {
            "phillips_bcb": est_p, "is_bcb": est_i, "expect_bcb": est_e,
            "taylor": est_aux["taylor"], "uip": est_aux["uip"], "admin": est_aux["admin"],
        }
        sys_b = BcbSystem(est_full, qf)
        cfg = rpm_mod.load()
        last_q = qf.index[-1].to_period("Q")
        nq = last_q + 1
        eq = nq + (args.horizon - 1)
        scenario = rpm_mod.scenario_path(cfg, str(nq), str(eq),
                                         last_oni=float(qf["oni"].dropna().iloc[-1]))
        fc = sys_b.forecast(horizon=args.horizon, scenario=scenario, expect_mode="consistent")
        rpm_path = rpm_mod.rpm_ipca_path(cfg)
        comp = fc.set_index("period")
        comp.index = pd.PeriodIndex(comp.index, freq="Q")
        comp = comp.join(rpm_path).sort_index()
        valid = comp.dropna(subset=["pi4", "rpm_ipca4"])
        mae = (valid["pi4"] - valid["rpm_ipca4"]).abs().mean()
        print("\nPROJEÇÃO AGREGADO BCB (expectativas consistentes) vs RPM jun/2026")
        print(f"  MAE ({len(valid)} trimestres): {mae:.3f} p.p.")
        print(comp[["pi4", "pi_l", "rpm_ipca4"]].round(2).to_string())
        comp.to_csv(OUT / "projecao_bcb.csv", index_label="period")

        # ---- IRFs do agregado BCB vs RI dez/2021 ----
        base = sys_b.forecast(horizon=args.horizon, scenario=scenario, expect_mode="consistent")
        irf_gap = sys_b.forecast(horizon=args.horizon, scenario=scenario,
                                 expect_mode="consistent", shock_gap_pp=-1.0)
        irf_selic = sys_b.forecast(horizon=args.horizon,
                                   scenario=scenario.assign(selic=scenario["selic"] + 1.0),
                                   expect_mode="consistent")
        irf_cam = sys_b.forecast(horizon=args.horizon, scenario=scenario,
                                 expect_mode="consistent", shock_cambio_pp=10.0)
        d_gap = irf_gap["pi4"] - base["pi4"]
        d_selic = irf_selic["pi4"] - base["pi4"]
        d_cam = irf_cam["pi4"] - base["pi4"]
        print("\nIRFs AGREGADO BCB (Δ p.p. IPCA 4T) vs RI dez/2021")
        print(f"  demanda -1 p.p. (hiato): pico {d_gap.abs().max():.3f} p.p. "
              f"| RI: -0,45 p.p. em 4T")
        print(f"  Selic +1 p.p.: pico {d_selic.abs().max():.3f} p.p.")
        print(f"  Câmbio +10%: pico {d_cam.abs().max():.3f} p.p.")
        pd.DataFrame({"demanda": d_gap, "selic": d_selic, "cambio": d_cam}).to_csv(
            OUT / "irfs_bcb.csv", index_label="period")
    except Exception as e:  # noqa: BLE001
        import traceback
        print(f"\nPROJEÇÃO/IRFs: indisponível ({e})")
        traceback.print_exc()


if __name__ == "__main__":
    main()
