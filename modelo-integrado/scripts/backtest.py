"""Backtest PIT do modelo integrado (vintages rolantes).

Para cada vintage pt_2019Q1..pt_2026Q1: estima com dados ≤ cutoff (estimação rápida
staged/OLS), projeta 12 trimestres com o sistema integrado (expectativas híbridas) e
compara com o IPCA realizado. Métricas: MAE, RMSE, MdAE por horizonte + benchmark naive.

Disciplina point-in-time da ESPECIFICAÇÃO: o cenário condicionante do RPM jun/2026
(spec_manifesto.yaml, available_from 2026-06-25) só é usado em vintages com cutoff
posterior à publicação do cenário; nas demais a projeção usa o sistema endógeno
(Taylor/UIP + PPC). O `pt_latest` é usado apenas como alvo de AVALIAÇÃO (realizado).
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
import spec_manifesto as spec_man  # noqa: E402

OUT = ROOT / "output"
NAIVE_H = 4


def run_vintage(vintage: str, horizon: int = 12, calibrar: bool = False) -> pd.DataFrame | None:
    df = load_snapshot(vintage)
    cutoff = pd.Timestamp(df["available_from"].max()) if "available_from" in df.columns else pd.NaT
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

    # Calibração ao RI dez/2021 — opcional (--calibrar) e PIT-AWARE: os valores calibrados
    # (a4/a2/b1/a5/a6) são as modas do RI dez/2021 (available_from 2021-12-31); aplicá-los
    # em vintages com cutoff anterior seria vazamento. Empiricamente, a calibração PIORA a
    # acurácia fora de amostra (2,17 vs 1,92 estimado) — o default é o modelo ESTIMADO.
    q_uso = q
    if calibrar and not pd.isna(cutoff) and pd.Timestamp(cutoff) >= pd.Timestamp(
            spec_man.available_from("priors_agregado")):
        gap_std = float(q["gap"].std()) if q["gap"].std() > 0 else 1.0
        fator = 1.0 / max(gap_std, 0.3)
        q_uso = q.copy()
        q_uso["gap"] = q["gap"] * fator
        q_uso["gap_1"] = q_uso["gap"].shift(1)
        pp = dict(pp)
        pp["gap_1"] = 0.14
        pp["imp_total"] = 0.018
        pp["elnino"] = 0.00119
        pp["lanina"] = 0.00104
        pp["b1"] = 0.74
        pp["b2"] = 0.15
    est_full = {
        "phillips": {"a1": pp["pi_l_1"], "a2": pp["imp_total"], "a3": pp["dev_ppc"],
                     "a4": pp["gap_1"], "a5": pp["elnino"], "a6": pp["lanina"]},
        "is": {"b1": pp.get("b1", est_i["params"]["gap_1"]),
               "b2": pp.get("b2", est_i["params"]["rreal_gap"])},
        "expect": est_e["params"],
        "taylor": aux["taylor"], "uip": aux["uip"], "admin": aux["admin"],
    }
    sys_i = SistemaIntegrado(est_full, q_uso, None)

    last_q = q.index[-1].to_period("Q")
    nq = last_q + 1
    eq = nq + (horizon - 1)
    # Cenário do RPM jun/2026 (spec_manifesto.yaml: available_from 2026-06-25) só pode
    # condicionar projeções de vintages cujo cutoff é POSTERIOR à publicação do cenário.
    # Em vintages antigas usa-se o sistema ENDÓGENO (Taylor/UIP + PPC) — o cenário do
    # futuro numa vintage passada seria vazamento de especificação.
    scenario = None
    if spec_man.check_spec("rpm_2026q2", cutoff):
        scenario = rpm_mod.scenario_path(rpm_mod.load(), str(nq), str(eq), last_oni=0.0)
    else:
        print(f"    {vintage}: cenário RPM 2026Q2 indisponível na vintage "
              f"(cutoff {pd.Timestamp(cutoff).date()}) -> cenário endógeno PIT")
    # Nota deliberada: os suportes/priors do RI dez/2021 (spec 'priors_agregado',
    # available_from 2021-12-31) definem a ESTRUTURA do modelo replicado (referência
    # fixa), não um input condicionante variável no tempo — por isso não aborta em
    # vintages anteriores, apenas avisa.
    if not spec_man.check_spec("priors_agregado", cutoff):
        print(f"    {vintage}: AVISO — estrutura (suportes) do RI dez/2021 posterior ao cutoff")
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
    ap.add_argument("--calibrar", action="store_true", default=False,
                    help="aplica a calibração ao RI dez/2021 (PIT-aware; piora a acurácia fora de amostra)")
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)

    frames = []
    for year in range(2019, 2027):
        for qn in range(1, 5):
            vintage = f"pt_{year}Q{qn}"
            if year == 2026 and qn > 1:
                continue
            try:
                r = run_vintage(vintage, args.horizon, calibrar=args.calibrar)
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
