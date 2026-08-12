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
    ("integrado", ["python", "modelo-integrado/scripts/run_integrado.py",
                   "--draws", "150", "--tune", "100"]),
    ("backtest_integrado", ["python", "modelo-integrado/scripts/backtest.py"]),
    ("longhorizon_integrado", ["python", "modelo-integrado/scripts/longhorizon.py"]),
    ("decomposicao", ["python", "modelo-integrado/scripts/decomposicao.py"]),
    ("figuras", ["python", "scripts/make_figures.py"]),
]


def _summary() -> None:
    print("\n" + "=" * 70)
    print("RESUMO — números-chave da réplica")
    print("=" * 70)
    try:
        import pandas as pd
        bt = pd.read_csv(ROOT / "modelo-integrado" / "output" / "backtest_integrado.csv")
        bt = bt.dropna(subset=["realizado"])
        print(f"  Backtest integrado ({bt['vintage'].nunique()} vintages): MAE médio {bt['abs'].mean():.3f} p.p.")
        pr = pd.read_csv(ROOT / "modelo-integrado" / "output" / "projecao_integrada.csv")
        v = pr.dropna(subset=["pi4", "rpm_ipca4"])
        mae = (v["pi4"] - v["rpm_ipca4"]).abs().mean()
        print(f"  MAE integrado vs cenário oficial (RPM jun/2026): {mae:.3f} p.p. ({len(v)} trimestres)")
    except Exception as e:  # noqa: BLE001
        print(f"  (resumo indisponível: {e})")
    print("  Dashboard: docker compose up dashboard")
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
