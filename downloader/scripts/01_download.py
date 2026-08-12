"""01_download.py — baixa/atualiza os dados brutos (cache em data/raw).

Uso:
    python scripts/01_download.py            # só o que está desatualizado
    python scripts/01_download.py --force    # ignora cache e rebaixa tudo
    python scripts/01_download.py --sources sgs,focus   # só fontes escolhidas
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import focus as focus_mod
from src import fred as fred_mod
from src import io_utils
from src import ipeadata as ipeadata_mod
from src import noaa as noaa_mod
from src import sidra as sidra_mod
from src import sgs as sgs_mod


def main() -> None:
    ap = argparse.ArgumentParser(description="Coleta dados brutos das fontes públicas.")
    ap.add_argument("--force", action="store_true", help="ignora cache e rebaixa tudo")
    ap.add_argument("--sources", default="sgs,focus,sidra,noaa,fred,ipeadata",
                    help="vírgula-separado: sgs,focus,sidra,noaa,fred,ipeadata")
    args = ap.parse_args()

    cfg = io_utils.settings()
    series_cfg = io_utils.load_yaml("series.yaml")
    dirs = io_utils.data_dirs()
    wanted = {s.strip() for s in args.sources.split(",") if s.strip()}

    manifest: dict = {}
    fetched_at = datetime.now(timezone.utc).isoformat()

    if "sgs" in wanted:
        sgs_series = series_cfg["sgs"]
        payloads, errors = sgs_mod.download_sgs(sgs_series, cfg, dirs, force=args.force)
        n = {k: len(v["values"]) for k, v in payloads.items()}
        manifest["sgs"] = {"fetched_at": fetched_at, "series": n, "errors": errors}
        print(f"SGS: {len(payloads)}/{len(sgs_series)} séries -> {n}")

    if "focus" in wanted:
        indicators = series_cfg["focus_indicators"]
        payloads = focus_mod.download_focus(indicators, cfg, dirs, force=args.force)
        n = {k: len(v["values"]) for k, v in payloads.items()}
        manifest["focus"] = {"fetched_at": fetched_at, "series": n}
        print(f"Focus: {len(payloads)} combinações -> {n}")

    if "sidra" in wanted:
        spec = series_cfg["sidra"]["table_ipca_subitem"]
        payload = sidra_mod.download_sidra(spec, cfg, dirs, force=args.force)
        manifest["sidra"] = {"fetched_at": fetched_at, "rows": len(payload.get("values", []))}
        print(f"SIDRA: {len(payload.get('values', []))} observações de subitens")
        for qkey in ("pib_trimestral", "desocupacao"):
            spec_q = series_cfg["sidra"][qkey]
            payload_q = sidra_mod.download_sidra_quarterly(spec_q, cfg, dirs, force=args.force)
            nq = len(payload_q.get("values", []))
            manifest.setdefault("sidra_quarterly", {})[qkey] = nq
            print(f"SIDRA {qkey}: {nq} observações")

    if "noaa" in wanted:
        payload = noaa_mod.download_noaa(cfg, dirs, force=args.force)
        manifest["noaa"] = {"fetched_at": fetched_at, "text_len": len(payload.get("text", ""))}
        print("NOAA: ONI atualizado")

    if "fred" in wanted:
        payloads = fred_mod.download_fred(series_cfg["fred"], cfg, dirs, force=args.force)
        ok = [k for k, v in payloads.items() if "error" not in v]
        err = [f"{k}:{v['error']}" for k, v in payloads.items() if "error" in v]
        manifest["fred"] = {"fetched_at": fetched_at, "ok": ok, "errors": err}
        print(f"FRED: ok={ok} erros={err if err else 'nenhum'}")

    if "ipeadata" in wanted:
        payloads = ipeadata_mod.download_ipeadata(series_cfg["ipeadata"]["setorais"],
                                                  cfg, dirs, force=args.force)
        ok = {k: len(v["values"]) for k, v in payloads.items() if "error" not in v}
        err = [f"{k}:{v['error']}" for k, v in payloads.items() if "error" in v]
        manifest["ipeadata"] = {"fetched_at": fetched_at, "series": ok, "errors": err}
        print(f"IpeaData: ok={ok} erros={err if err else 'nenhum'}")

    io_utils.write_json(dirs["raw"] / "manifest.json", manifest)
    print("Manifesto salvo em data/raw/manifest.json")


if __name__ == "__main__":
    main()
