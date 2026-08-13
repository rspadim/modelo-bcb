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
sys.path.insert(0, str(ROOT / "src"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from data import load_snapshot, build_quarterly  # noqa: E402
import gap as gap_mod  # noqa: E402
from estimador_conjunto import estimar_conjunta  # noqa: E402
from sistema import SistemaIntegrado  # noqa: E402
from equacoes_bcb import estimate_is_bcb, estimate_expect_bcb, _hp_cycle  # noqa: E402
from phillips_bcb import estimate_phillips_bcb_bayes  # noqa: E402
import spec_manifesto as spec_man  # noqa: E402
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
    ap.add_argument("--expect", choices=["hybrid", "consistent"], default="hybrid",
                    help="expectativas: hybrid (ancoradas na meta, estável) ou consistent (φ2 fixed-point)")
    ap.add_argument("--calibrar", dest="calibrar", action="store_true", default=True,
                    help="calibra a4/b2/a2 aos valores do RI dez/2021 (padrão, como o BCB calibra)")
    ap.add_argument("--sem-calibrar", dest="calibrar", action="store_false",
                    help="usa os parâmetros estimados (sem calibração)")
    ap.add_argument("--nivel", choices=["agregado", "setorial"], default="agregado",
                    help="modelo desagregado (3 Phillips setoriais) como opção")
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

    # ---- Calibração aos valores publicados do RI dez/2021 ----
    # O hiato estimado tem amplitude ~±6% (dados públicos); o BCB usa ~±1% (função de
    # produção com dados internos). Calibramos: resscalar o hiato à convenção do BCB e
    # fixar a4 (Phillips/hiato), a2 (importada), b1 (persistência da IS) e b2 (juro real)
    # nas modas do RI, de modo que as IRFs reproduzam o PDF. b2 pode desestabilizar com o
    # juro real atual (~10% vs neutra 5) — o gate de estabilidade abaixo reduz se preciso.
    q_uso = q
    if args.calibrar:
        gap_std = float(gap_s.std()) if gap_s.std() > 0 else 1.0
        fator = 1.0 / max(gap_std, 0.3)          # resscala o hiato para ~1 desvio-padrão
        q_uso = q.copy()
        q_uso["gap"] = q["gap"] * fator
        q_uso["gap_1"] = q_uso["gap"].shift(1)
        pp_cal = dict(pp)
        pp_cal["a4"] = 0.14        # RI α4 (hiato na Phillips)
        pp_cal["a2"] = 0.018       # RI α2 (inflação importada)
        pp_cal["b1"] = 0.74        # RI β1 (persistência da IS — destrava a transmissão)
        pp_cal["b2"] = 0.55        # RI β2 (juro real na IS)
        print(f"\nCALIBRAÇÃO AO RI (como o BCB calibra componentes):")
        print(f"  hiato resscalado por {fator:.2f} | a4={pp_cal['a4']} a2={pp_cal['a2']} "
              f"b1={pp_cal['b1']} b2={pp_cal['b2']}")
        pp = pp_cal
        gap_s = gap_s * fator
    else:
        print("\nSEM calibração (parâmetros estimados).")

    # ---- sistema único ----
    est_e = estimate_expect_bcb(q, draws=120, tune=80)
    aux = eqmod.estimate_all(q)
    est_full = {
        "phillips": pp,
        "is": {"b1": pp["b1"], "b2": pp["b2"]},
        "expect": est_e["params"],
        "taylor": aux["taylor"], "uip": aux["uip"], "admin": aux["admin"],
    }
    pset = None
    wsec = None
    if args.nivel == "setorial":
        from sector import add_sectoral_quarterly
        from phillips import estimate_sectoral_phillips
        q_uso = add_sectoral_quarterly(q_uso, df)
        pset = estimate_sectoral_phillips(q_uso)
        wsec = {s: float(q_uso[f"w_{s}"].dropna().iloc[-1])
                for s in ["servicos", "industriais", "alimentacao"]}
        print("\nMODO SETORIAL (3 Phillips de livres, amostra 2020+):")
        for s, r in pset.items():
            if r is not None:
                print(f"  {s:12s} n={r['n']} inércia={r['params']['pi_1']:.2f} "
                      f"gap={r['params']['gap_1']:.3f} câmbio(PPC)={r['params']['dev_ppc']:.4f}")
    sys_integ = SistemaIntegrado(est_full, q_uso, admin_est=None,
                                 phillips_setorial=pset, pesos_setoriais=wsec)
    sys_integ.neutra = float(neutra_s.iloc[-1])

    cfg = rpm_mod.load()
    last_q = q.index[-1].to_period("Q")
    nq = last_q + 1
    eq = nq + (args.horizon - 1)
    scenario = rpm_mod.scenario_path(cfg, str(nq), str(eq),
                                     last_oni=float(q["oni"].dropna().iloc[-1]))

    # ---- projeção ----
    fc = sys_integ.forecast(horizon=args.horizon, scenario=scenario, expect_mode=args.expect)

    # ---- Gate de estabilidade da transmissão (b2) ----
    # Com o juro real atual (~10% vs neutra ~5), b2=0,55 derruba o hiato e diverge a
    # projeção. Usamos b2=0,15: transmissão presente (Selic IRF ~0,2, consistente com os
    # ~0,26 p.p. implícitos no RI) sem degradar o MAE. O β2=0,55 do RI não é alcançável
    # de forma estável — documentado.
    if args.calibrar and fc["gap"].abs().max() > 5.0:
        b2_estavel = 0.15
        print(f"\nGATE DE ESTABILIDADE: b2=0,55 divergiu (hiato pico {fc['gap'].abs().max():.1f}) "
              f"-> b2={b2_estavel} (transmissão presente, Selic IRF ~0,2; RI β2=0,55 não estável).")
        pp["b2"] = b2_estavel
        est_full["is"]["b2"] = b2_estavel
        sys_integ = SistemaIntegrado(est_full, q_uso, admin_est=None,
                                     phillips_setorial=pset, pesos_setoriais=wsec)
        sys_integ.neutra = float(neutra_s.iloc[-1])
        fc = sys_integ.forecast(horizon=args.horizon, scenario=scenario, expect_mode=args.expect)

    rpm_path = rpm_mod.rpm_ipca_path(cfg)
    comp = fc.set_index("period")
    comp.index = pd.PeriodIndex(comp.index, freq="Q")
    comp = comp.join(rpm_path).sort_index()
    valid = comp.dropna(subset=["pi4", "rpm_ipca4"])
    mae = (valid["pi4"] - valid["rpm_ipca4"]).abs().mean()
    print(f"\nMAE vs RPM jun/2026 ({len(valid)} trimestres): {mae:.3f} p.p.")
    comp.to_csv(OUT / "projecao_integrada.csv", index_label="period")

    # ---- IRFs vs RI dez/2021 ----
    base = sys_integ.forecast(horizon=args.horizon, scenario=scenario, expect_mode=args.expect)
    irf_gap = sys_integ.forecast(horizon=args.horizon, scenario=scenario, expect_mode=args.expect,
                                 shock_gap_pp=-1.0)
    irf_cam = sys_integ.forecast(horizon=args.horizon, scenario=scenario, expect_mode=args.expect,
                                 shock_cambio_pp=10.0)
    irf_selic = sys_integ.forecast(horizon=args.horizon,
                                   scenario=scenario.assign(selic=scenario["selic"] + 1.0),
                                   expect_mode=args.expect)
    d_gap = irf_gap["pi4"] - base["pi4"]
    d_cam = irf_cam["pi4"] - base["pi4"]
    d_selic = irf_selic["pi4"] - base["pi4"]
    print("\nIRFs (Δ p.p. IPCA 4T) vs RI dez/2021:")
    print(f"  demanda −1 p.p. (hiato): pico {d_gap.abs().max():.3f} p.p. (RI: −0,45)")
    print(f"  câmbio +10%: pico {d_cam.abs().max():.3f} p.p.")
    print(f"  Selic +1 p.p.: pico {d_selic.abs().max():.3f} p.p.")
    pd.DataFrame({"demanda": d_gap, "cambio": d_cam, "selic": d_selic}).to_csv(
        OUT / "irfs_integradas.csv", index_label="period")

    # ---- Fidelidade vs RI (tabela) ----
    ri = {"a1": 0.23756, "a2": 0.01826, "a3": 0.01727, "a4": 0.13866,
          "a5": 0.00119, "a6": 0.00104, "b1": 0.73897, "b2": 0.54876}
    linhas = []
    for k, v in ri.items():
        linhas.append({"param": k, "modelo": pp.get(k, float("nan")), "RI_2021": v})
    linhas += [
        {"param": "IRF_demanda", "modelo": float(d_gap.abs().max()), "RI_2021": 0.45},
        {"param": "IRF_selic", "modelo": float(d_selic.abs().max()), "RI_2021": None},
        {"param": "MAE_vs_RPM", "modelo": mae, "RI_2021": None},
    ]
    tab = pd.DataFrame(linhas)
    tab.to_csv(OUT / "fidelidade_vs_ri.csv", index=False)
    print("\nFIDELIDADE VS RI (RI dez/2021):")
    print(tab.round(4).to_string(index=False))

    # ---- Fan chart + balanço de riscos (incerteza da posterior) ----
    if args.est == "conjunta" and "_trace" in res:
        try:
            import numpy as np
            post = res["_trace"].posterior
            n_draws = int(post["a1"].shape[0] * post["a1"].shape[1])
            rng = np.random.default_rng(7)
            idx = rng.choice(n_draws, size=min(60, n_draws), replace=False)
            paths = []
            for i in idx:
                flat = lambda name: float(post[name].values.reshape(-1)[i])
                pp_draw = {"a1": flat("a1"), "a2": args.calibrar and 0.018 or flat("a2"),
                           "a3": flat("a3"), "a4": args.calibrar and 0.14 or flat("a4"),
                           "a5": flat("a5"), "a6": flat("a6"),
                           "b1": flat("b1"), "b2": flat("b2")}
                est_d = {"phillips": pp_draw,
                         "is": {"b1": pp_draw["b1"], "b2": pp_draw["b2"]},
                         "expect": est_e["params"], "taylor": aux["taylor"],
                         "uip": aux["uip"], "admin": aux["admin"]}
                m = SistemaIntegrado(est_d, q_uso, None)
                m.neutra = sys_integ.neutra
                f = m.forecast(horizon=args.horizon, scenario=scenario, expect_mode=args.expect)
                paths.append(f["pi4"].values)
            paths = np.array(paths)
            fan = pd.DataFrame({p: np.percentile(paths, p, axis=0) for p in (10, 25, 50, 75, 90)},
                               index=base["period"])
            fan["mediana"] = fan[50]
            fan.to_csv(OUT / "fan_chart_integrado.csv", index_label="period")
            fora = ((paths < 1.5) | (paths > 4.5)).mean(axis=0)
            risco = pd.DataFrame({"P(fora [1,5;4,5])": fora}, index=base["period"])
            risco.to_csv(OUT / "balanco_riscos_integrado.csv", index_label="period")
            print(f"\nBALANÇO DE RISCOS (P(IPCA4 fora de [1,5;4,5])) — posterior")
            print(risco.round(3).head(8).to_string())
        except Exception as e:  # noqa: BLE001
            print(f"\nFan chart: indisponível ({e})")

    # ---- Convergência (R-hat) ----
    if args.est == "conjunta" and "_trace" in res:
        import arviz as az
        rhat_ds = az.rhat(res["_trace"])
        bad = []
        for name in rhat_ds.data_vars:
            val = float(rhat_ds[name].values.reshape(-1)[0])
            if val > 1.05:
                bad.append(str(name))
        print(f"\nR-hat: params com rhat>1.05: {bad if bad else 'nenhum'}")
        if bad:
            print("  (convergência insatisfatória — aumentar tune ou ancorar priors)")

    # ---- hiato/neutra suavizados para inspeção ----
    gap_s.to_frame("gap").to_csv(OUT / "hiato_integrado.csv", index_label="period")
    neutra_s.to_frame("neutra").to_csv(OUT / "neutra_integrada.csv", index_label="period")


if __name__ == "__main__":
    main()
