"""IRFs + balanço de riscos + fan chart com incerteza paramétrica (modelo completo).

Uso:
    python scripts/irf_and_risk.py [--vintage pt_2026Q2] [--draws 300] [--npaths 200]
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
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent / "modelo-agregado" / "src"))

from src import data as dcomplete
from src import gap as kgap
from src import phillips as pset
from src import system as csystem
from src import bayes as bayes_mod
from src import admin_calibrado as admin_cal
from src import spec_manifesto as spec_man
import equations as eqmod
import rpm as rpm_mod

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

OUT = ROOT / "output"
BAND = (1.5, 4.5)  # intervalo de tolerância da meta contínua (±1,5 p.p. em torno de 3%)


def build_model(vintage: str, args):
    df = dcomplete.load_snapshot(vintage)
    cutoff = pd.Timestamp(df["available_from"].max()) if "available_from" in df.columns else pd.NaT
    if not spec_man.check_spec("rpm_2026q2", cutoff):
        sys.exit("[spec_manifesto] cenário RPM posterior ao cutoff da vintage — abortando.")
    q = dcomplete.build_complete_quarterly(df)
    q = kgap.add_gap_kalman(q)
    q = q.loc["2020Q1":]
    sp = pset.estimate_sectoral_phillips(q)
    est = eqmod.estimate_all(q)
    est.pop("phillips", None)
    est["phillips"] = sp
    return csystem.CompleteSystem(est, q, {}), q, est


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vintage", default="pt_2026Q2")
    ap.add_argument("--horizon", type=int, default=12)
    ap.add_argument("--draws", type=int, default=300, help="amostras por cadeia (bayes)")
    ap.add_argument("--npaths", type=int, default=150, help="trajetórias do fan chart paramétrico")
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)

    model, q, est_ols = build_model(args.vintage, args)

    # Estimação bayesiana conjunta (repasse positivo + hiato com prior informativo)
    print("Estimando bayesiana (modelo base das IRFs e do fan chart)...")
    est_b = bayes_mod.estimate_bayesian(q, est_ols, draws=args.draws)
    est_bayes = dict(est_b)
    est_bayes.pop("_trace", None)
    for k in ("taylor", "uip", "expect"):
        if k in est_ols:
            est_bayes[k] = est_ols[k]
    model = csystem.CompleteSystem(est_bayes, q, {})
    trace = est_b["_trace"]

    cfg_rpm = rpm_mod.load()
    last_q = q.index[-1].to_period("Q")
    next_q = last_q + 1
    end_q = next_q + (args.horizon - 1)
    spath = rpm_mod.selic_path(cfg_rpm, str(next_q), str(end_q))
    scenario = rpm_mod.scenario_path(cfg_rpm, str(next_q), str(end_q),
                                     last_oni=float(q["oni"].dropna().iloc[-1]))

    # ---- Bloco de administrados calibrado (B9) ----
    df = dcomplete.load_snapshot(args.vintage)
    band = admin_cal.load_bandeiras()
    est_a = admin_cal.calibrate_aggregate(df, bandeiras=band)
    idx = pd.date_range(pd.Timestamp(last_q.to_timestamp()) + pd.DateOffset(months=1),
                        periods=args.horizon * 3, freq="MS")
    brent_q = scenario["brent"]
    brent_m = brent_q.reindex(brent_q.index.to_timestamp()).resample("MS").ffill().reindex(idx).ffill()
    c0 = float(q["cambio"].dropna().iloc[-1])
    ppc_q = cfg_rpm.get("cambio_ppc_depreciacao_aa", 1.0) / 4 / 3
    cambio_m = pd.Series(c0 * (1 + ppc_q) ** np.arange(len(idx)), index=idx)
    band_fut = band.reindex(idx).ffill().fillna(0.0)
    ipca12_m = pd.Series(4.5, index=idx)
    mono = admin_cal.forecast_admin_calibrado(est_a, df, brent_m, cambio_m, ipca12_m, band_fut,
                                              args.horizon * 3)
    q_admin = mono.resample("QE").apply(
        lambda x: (np.prod(1 + np.asarray(x.dropna()) / 100.0) - 1) * 100
        if len(x.dropna()) >= 3 else np.nan).dropna()
    q_admin.index = q_admin.index.to_period("Q")
    admin_path = q_admin

    base = model.forecast(horizon=args.horizon, selic_path=spath, scenario=scenario,
                          admin_path=admin_path)

    # ---- IRFs do bloco de administrados (anexo B9: alvos 1,8 / 1,3 p.p.) ----
    print("\n===== IRFs ADMINISTRADOS CALIBRADOS (alvos do anexo B9) =====")
    admin_irf = admin_cal.calibrate_aggregate(df, bandeiras=band)  # recalcula p/ medir resposta
    p_irf = admin_irf["params"]
    resp_fx = admin_cal._irf_scale(df, admin_irf, "fx", p_irf["dln_cambio"], band)
    resp_oil = admin_cal._irf_scale(df, admin_irf, "oil", p_irf["dln_brent_rl"], band)
    print(f"  câmbio +10%% -> admin {resp_fx:.2f} p.p. em 4T (alvo B9 ~1,8)")
    print(f"  petróleo +10%% -> admin {resp_oil:.2f} p.p. em 4T (alvo B9 ~1,3)")

    # ---- IRFs (diferença vs cenário base, em p.p. de pi4) ----
    def brent_level_shock(sc):
        sc = sc.copy()
        sc.loc[sc.index[0], "brent"] *= 1.10  # salto de nível no 1º período
        return sc

    def irf(shock_kwargs, scenario_mod=None):
        sc = scenario_mod(scenario) if scenario_mod else scenario
        s = model.forecast(horizon=args.horizon, selic_path=spath, scenario=sc,
                           admin_path=admin_path, **shock_kwargs)
        return pd.Series((s["pi4"] - base["pi4"]).values, index=base["period"])

    shocks = {
        "Câmbio +10% (depreciação)": irf({"shock_cambio_pp": 10.0}),
        "Selic +1 p.p. (trajetória)": irf({}, lambda sc: sc.assign(selic=sc["selic"] + 1.0)),
        "Brent +10% (nível, 1º T)": irf({}, brent_level_shock),
        "Demanda +1 p.p. (hiato)": irf({"shock_gap_pp": 1.0}),
    }
    irf_df = pd.DataFrame(shocks)
    print("\n===== IRFs: efeito em IPCA acumulado 4T (Δ p.p. vs base) =====")
    print(irf_df.round(3).to_string())
    print("\nEfeito de pico (máx |Δpi4|):")
    for k, s in shocks.items():
        print(f"  {k:30s} pico={s.abs().max():.3f} p.p. (em {s.idxmax() if (s==s.max()).any() else s.index[s.abs().argmax()]})")
    irf_df.to_csv(OUT / "irfs.csv", index_label="period")

    # ---- Fan chart com incerteza de parâmetro (posterior bayesiana) ----
    post = trace.posterior
    n_draws = int(post["is_const"].shape[0] * post["is_const"].shape[1])
    rng = np.random.default_rng(11)
    idx = rng.choice(n_draws, size=min(args.npaths, n_draws), replace=False)

    paths = []
    for i in idx:
        est_draw = bayes_mod.trace_to_est(trace, i, est_ols)
        m = csystem.CompleteSystem(est_draw, q, {})
        f = m.forecast(horizon=args.horizon, selic_path=spath, scenario=scenario,
                       admin_path=admin_path)
        paths.append(f["pi4"].values)
    paths = np.array(paths)

    pct = {p: np.percentile(paths, p, axis=0) for p in (10, 25, 50, 75, 90)}
    fan = pd.DataFrame(pct, index=base["period"])
    fan["mediana"] = fan[50]
    fan.to_csv(OUT / "fan_chart_parametrico.csv", index_label="period")

    # ---- Balanço de riscos: P(pi4 fora da banda de tolerância) ----
    prob = (paths < BAND[0]) | (paths > BAND[1])
    risk = pd.DataFrame({
        "P(abaixo)": (paths < BAND[0]).mean(axis=0),
        "P(acima)": (paths > BAND[1]).mean(axis=0),
        "P(fora)": prob.mean(axis=0),
    }, index=base["period"])
    print("\n===== BALANÇO DE RISCOS: probabilidade de romper a banda [1,5; 4,5] =====")
    print(risk.round(3).to_string())
    risk.to_csv(OUT / "balanco_riscos.csv", index_label="period")

    # ---- Figura: fan chart + banda + cenário oficial ----
    rpm_path = rpm_mod.rpm_ipca_path(cfg_rpm)
    fig, ax = plt.subplots(figsize=(11, 6))
    x = fan.index.astype(str)
    for lo, hi, color, alpha in [(10, 90, "#c9d4e8", 0.35), (25, 75, "#7f9cc8", 0.45)]:
        ax.fill_between(x, fan[lo], fan[hi], color=color, alpha=alpha,
                        label=f"P10-P90 / P25-P75" if lo == 10 else None)
    ax.plot(x, fan[50], "b-o", lw=2, label="Mediana (incerteza de parâmetro)")
    ax.plot(x, base["pi4"], "k--", lw=1.2, label="Cenário base (OLS)")
    ax.plot(rpm_path.index.astype(str), rpm_path["rpm_ipca4"], "r-o", lw=1.5,
            label="Cenário oficial RPM")
    ax.axhline(3.0, color="black", ls=":", lw=1)
    ax.axhspan(*BAND, color="gray", alpha=0.08)
    ax.set_title("Fan chart com incerteza paramétrica (posterior bayesiana) — IPCA acumulado 4T")
    ax.set_ylabel("% a.a.")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(OUT / "fan_chart_parametrico.png", dpi=140)
    print(f"\nFigura: {OUT / 'fan_chart_parametrico.png'}")
    plt.close(fig)


if __name__ == "__main__":
    main()
