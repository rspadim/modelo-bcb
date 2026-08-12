"""Orquestrador do pipeline: roda as etapas em ordem e resume os números-chave.

Uso:
    python main.py                 # roda tudo
    python main.py --skip download # pula etapas (ex.: dados já baixados)
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

STEPS = [
    ("01_download", ["python", "downloader/scripts/01_download.py"]),
    ("02_build", ["python", "downloader/scripts/02_build_dataset.py"]),
    ("agregado", ["python", "modelo-agregado/scripts/run_aggregate.py"]),
    ("backtest", ["python", "modelo-agregado/scripts/backtest.py"]),
    ("longhorizon", ["python", "modelo-agregado/scripts/longhorizon.py"]),
    ("bcb_agregado", ["python", "modelo-agregado/scripts/run_bcb.py",
                      "--draws", "250", "--tune", "150"]),
    ("completo", ["python", "modelo-completo/scripts/run_complete.py"]),
    ("irf_and_risk", ["python", "modelo-completo/scripts/irf_and_risk.py",
                      "--draws", "200", "--npaths", "100"]),
    ("validate_sector", ["python", "modelo-completo/scripts/validate_sector.py"]),
    ("figuras", ["python", "scripts/make_figures.py"]),
]


def _summary() -> None:
    print("\n" + "=" * 70)
    print("RESUMO — números-chave da réplica")
    print("=" * 70)
    try:
        import pandas as pd
        comp = pd.read_csv(ROOT / "modelo-agregado" / "output" / "comparacao_rpm.csv")
        v = comp.dropna(subset=["pi4_modelo_cond", "rpm_ipca4"])
        mae = (v["pi4_modelo_cond"] - v["rpm_ipca4"]).abs().mean()
        print(f"  MAE vs cenário oficial (RPM jun/2026): {mae:.3f} p.p. ({len(v)} trimestres)")
        bt = pd.read_csv(ROOT / "modelo-agregado" / "output" / "backtest.csv")
        print(f"  Backtest ({bt['vintage'].nunique()} vintages): MAE médio {bt['modelo'].sub(bt['realizado']).abs().mean():.3f} p.p.")
        lh = pd.read_csv(ROOT / "modelo-agregado" / "output" / "longhorizon.csv")
        print(f"  Long horizon ({len(lh)} vintages): MAE 1T={lh['prev_1q'].sub(lh['real_1q']).abs().mean():.2f} | "
              f"4T={lh['prev_4q'].sub(lh['real_4q']).abs().mean():.2f} p.p.")
    except Exception as e:  # noqa: BLE001
        print(f"  (resumo indisponível: {e})")
    print("  Figuras: docs/figures/  |  Dashboard: docker compose up dashboard")
    print("=" * 70)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip", default="", help="etapas separadas por vírgula para pular")
    args = ap.parse_args()
    skip = {s.strip() for s in args.skip.split(",") if s.strip()}

    for name, cmd in STEPS:
        if name in skip:
            print(f"--- pulando {name} ---")
            continue
        print(f"\n=== {name} ===")
        r = subprocess.run(cmd, cwd=str(ROOT))
        if r.returncode != 0:
            print(f"[ERRO] etapa {name} falhou (código {r.returncode}). Abortando.")
            sys.exit(r.returncode)

    _summary()


if __name__ == "__main__":
    main()
