"""Decomposição de inflação do modelo integrado (WP 440 / ofício 374) para 2024.

Usa a Phillips do modelo integrado (estaged OLS por padrão; --bayes opcional) para
decompor o desvio das livres em relação à meta em inércia, expectativas, importada,
câmbio, hiato e clima — comparando com o ofício 374/2025-BCB.
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
from phillips_bcb import estimate_phillips_bcb, estimate_phillips_bcb_bayes  # noqa: E402
from decomposicao import decompose, decompose_period  # noqa: E402
import spec_manifesto as spec_man  # noqa: E402

OUT = ROOT / "output"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vintage", default="pt_2026Q2")
    ap.add_argument("--bayes", action="store_true", help="usa a Phillips bayesiana")
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)

    df = load_snapshot(args.vintage)
    cutoff = pd.Timestamp(df["available_from"].max()) if "available_from" in df.columns else pd.NaT
    if not spec_man.check_spec("priors_agregado", cutoff):
        sys.exit("[spec_manifesto] especificação (RI dez/2021) posterior ao cutoff da vintage — abortando.")
    q = build_quarterly(df)
    q = gap_mod.add_gap_kalman(q)
    q["gap_1"] = q["gap"].shift(1)

    est = estimate_phillips_bcb_bayes(q, draws=300, tune=200) if args.bayes \
        else estimate_phillips_bcb(q)
    dec = decompose_period(q, est, "2024Q1", "2024Q4")
    print("== Decomposição 2024 (modelo integrado; contribuição ao desvio de livres vs meta, p.p.) ==")
    print("  ofício 374/2025-BCB: inércia 0,52 | importada 0,72 | hiato 0,49 | expect 0,30")
    print(dec.round(3).to_string())
    dec.to_csv(OUT / "decomposicao_2024_integrada.csv", index_label="fator")

    d = decompose(q, est, "2024Q1", "2024Q4")
    print("\nTrimestral:")
    print(d.round(3).to_string())


if __name__ == "__main__":
    main()
