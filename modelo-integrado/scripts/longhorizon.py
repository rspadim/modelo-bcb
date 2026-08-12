"""Long horizon do modelo integrado — MAE 1T e 4T à frente (vintages recursivas PIT).

Resume o backtest_integrado.csv (produzido por backtest.py) nos horizontes 1T e 4T,
comparando com o naive (persistência).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
OUT = ROOT / "output"


def main() -> None:
    path = OUT / "backtest_integrado.csv"
    if not path.exists():
        print("Rode backtest.py primeiro.")
        return
    bt = pd.read_csv(path).dropna(subset=["realizado"])
    if not len(bt):
        print("Sem dados de realizado.")
        return
    bt["abs"] = bt["abs"] if "abs" in bt else (bt["modelo"] - bt["realizado"]).abs()
    print("== Long horizon integrado (PIT) ==")
    for h in [1, 4]:
        d = bt[bt["horizon"] == h]
        if len(d):
            print(f"  MAE {h}T à frente: {d['abs'].mean():.3f} p.p. (n={len(d)})")
    # naive por vintage: persistência do pi4 do fim da vintage
    last_by_v = bt.sort_values("horizon").drop_duplicates("vintage")[["vintage", "modelo"]]
    last_by_v.columns = ["vintage", "naive_base"]
    m = bt.merge(last_by_v, on="vintage")
    m["naive"] = m["naive_base"]
    m["naive_abs"] = (m["naive"] - m["realizado"]).abs()
    print(f"  MAE geral modelo: {bt['abs'].mean():.3f} | naive: {m['naive_abs'].mean():.3f} p.p.")


if __name__ == "__main__":
    main()
