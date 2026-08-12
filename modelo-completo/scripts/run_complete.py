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
from src import bayes as bayes_mod
from src import admin_calibrado as admin_cal
from src import spec_manifesto as spec_man
import equations as eqmod
import rpm as rpm_mod

OUT = ROOT / "output"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vintage", default="pt_2026Q2")
    ap.add_argument("--horizon", type=int, default=12)
    ap.add_argument("--expect", choices=["hybrid", "consistent"], default="hybrid",
                    help="modo de expectativas: hybrid (ancora na meta) ou consistent (fixed-point)")
    ap.add_argument("--gap", choices=["kalman", "multi"], default="kalman",
                    help="hiato: kalman (1 indicador) ou multi (IBC-Br+PIB+desocupação)")
    ap.add_argument("--est", choices=["ols", "bayes"], default="ols",
                    help="estimação: ols ou bayes (PyMC, conjunta)")
    ap.add_argument("--draws", type=int, default=600, help="amostras por cadeia (bayes)")
    ap.add_argument("--admin", choices=["ols", "calibrado"], default="calibrado",
                    help="bloco de administrados: calibrado (B9, default) ou ols (equação agregada)")
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)

    df = dcomplete.load_snapshot(args.vintage)
    q = dcomplete.build_complete_quarterly(df)
    if args.gap == "multi":
        q = kgap.add_gap_multi(q)
    else:
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

    if args.est == "bayes":
        print("\n=== ESTIMAÇÃO BAYESIANA CONJUNTA (PyMC) ===")
        est_ols = est
        est = bayes_mod.estimate_bayesian(q, est_ols, draws=args.draws)
        # Taylor/UIP/expectativas permanecem do OLS (não incluídas no bloco conjunto)
        for k in ("taylor", "uip", "expect"):
            est[k] = est_ols[k]
        for s in ["servicos", "industriais", "alimentacao"]:
            r = est["phillips"][s]
            print(f"  {s:12s} inércia={r['params']['pi_1']:.2f} (sd {r['sd']['pi_1']:.2f}) "
                  f"gap={r['params']['gap_1']:.3f} câmbio={r['params']['dln_cambio']:.4f}")
        r = est["is"]
        print(f"  is: gap_1={r['params']['gap_1']:.3f} rreal={r['params']['rreal_1']:.3f} "
              f"câmbio={r['params']['dln_cambio']:.4f}")

    model = csystem.CompleteSystem(est, q, {})
    w = model.w
    print(f"\nPesos (média da amostra): livres={ (w['servicos']+w['industriais']+w['alimentacao'])*100:.1f}% "
          f"admin={w['admin']*100:.1f}% | dentro de livres: serv={w['servicos']/model.w_livres*100:.0f}% "
          f"ind={w['industriais']/model.w_livres*100:.0f}% "
          f"alim={w['alimentacao']/model.w_livres*100:.0f}%")

    cfg_rpm = rpm_mod.load()
    cutoff = pd.Timestamp(df["available_from"].max()) if "available_from" in df.columns else None
    spec_man.check_spec("rpm_2026q2", cutoff)
    spec_man.check_spec("admin_equacoes", cutoff)
    last_q = q.index[-1].to_period("Q")
    next_q = last_q + 1
    end_q = next_q + (args.horizon - 1)
    spath = rpm_mod.selic_path(cfg_rpm, str(next_q), str(end_q))
    scenario = rpm_mod.scenario_path(cfg_rpm, str(next_q), str(end_q),
                                     last_oni=float(q["oni"].dropna().iloc[-1]))

    # ---- Bloco de administrados calibrado (anexo B9) ----
    admin_path = None
    if args.admin == "calibrado":
        print("\n=== ADMINISTRADOS CALIBRADOS (B9: regras institucionais + alvos de IRF) ===")
        band = admin_cal.load_bandeiras()
        est_a = admin_cal.calibrate_aggregate(df, bandeiras=band)
        p = est_a["params"]
        print(f"  repasse câmbio={p['dln_cambio']:.4f} petróleo={p['dln_brent_rl']:.4f} "
              f"ipca12={p['ipca12_1']:.3f} bandeira={p['d_bandeira']:.4f}")
        # caminhos mensais do cenário
        idx = pd.date_range(pd.Timestamp(last_q.to_timestamp()) + pd.DateOffset(months=1),
                            periods=args.horizon * 3, freq="MS")
        brent_q = scenario["brent"]
        brent_m = brent_q.reindex(brent_q.index.to_timestamp()).resample("MS").ffill().reindex(idx).ffill()
        c0 = float(q["cambio"].dropna().iloc[-1])
        ppc_q = cfg_rpm.get("cambio_ppc_depreciacao_aa", 1.0) / 4 / 3
        cambio_m = pd.Series(c0 * (1 + ppc_q) ** np.arange(len(idx)), index=idx)
        band_fut = band.reindex(idx).ffill().fillna(0.0)
        ipca12_last = float(q["nucleo"].dropna().iloc[-1]) if q["nucleo"].notna().any() else 4.0
        ipca12_m = pd.Series(ipca12_last, index=idx)
        mono = admin_cal.forecast_admin_calibrado(est_a, df, brent_m, cambio_m, ipca12_m,
                                                  band_fut, args.horizon * 3)
        q_admin = mono.resample("QE").apply(
            lambda x: (np.prod(1 + np.asarray(x.dropna()) / 100.0) - 1) * 100
            if len(x.dropna()) >= 3 else np.nan).dropna()
        q_admin.index = q_admin.index.to_period("Q")
        admin_path = q_admin
        print(f"  projeção admin (trimestral, {len(admin_path)} períodos): "
              f"{admin_path.round(3).head(4).to_dict()}")

    fc = model.forecast(horizon=args.horizon, selic_path=spath, scenario=scenario,
                        expect_mode=args.expect, admin_path=admin_path)
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
