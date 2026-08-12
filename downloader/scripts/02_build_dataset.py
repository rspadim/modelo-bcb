"""02_build_dataset.py — monta série longa PIT + snapshots por trimestre.

Produz:
    data/processed/series.parquet        # série completa com available_from
    data/processed/snapshots_manifest.json
    data/snapshots/pt_<YYYYQn>/data.parquet  # cortes point-in-time
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

# desativa inferência de string[pyarrow] (incompatível com a lógica PIT em alguns ambientes)
try:
    pd.set_option("future.infer_string", False)
except Exception:  # noqa: BLE001
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import focus as focus_mod
from src import fred as fred_mod
from src import io_utils
from src import ipeadata as ipeadata_mod
from src import noaa as noaa_mod
from src import pit
from src import sidra as sidra_mod
from src import sgs as sgs_mod


def _load_all(cfg, series_cfg, dirs) -> pd.DataFrame:
    frames = []
    missing = []

    sgs_payloads = {}
    for key, spec in series_cfg["sgs"].items():
        p = io_utils.read_json(dirs["raw"] / "sgs" / f"{spec['code']}.json") \
            if (dirs["raw"] / "sgs" / f"{spec['code']}.json").exists() else None
        if p is not None:
            sgs_payloads[key] = p
        else:
            missing.append(f"sgs:{key}")
    frames.append(sgs_mod.sgs_to_frame(sgs_payloads))

    focus_payloads = {}
    for indicador in series_cfg["focus_indicators"]:
        for horizon in focus_mod.ENDPOINTS:
            f = dirs["raw"] / "focus" / f"{indicador}_{horizon}.json"
            p = io_utils.read_json(f) if f.exists() else None
            if p is not None:
                focus_payloads[f"{indicador}_{horizon}"] = p
            else:
                missing.append(f"focus:{indicador}_{horizon}")
    frames.append(focus_mod.focus_to_frame(focus_payloads))

    f = dirs["raw"] / "sidra" / "ipca_subitem.json"
    if f.exists():
        frames.append(sidra_mod.sidra_to_frame(io_utils.read_json(f)))
    else:
        missing.append("sidra:ipca_subitem")

    for qkey in ("pib_trimestral", "desocupacao"):
        f = dirs["raw"] / "sidra" / f"t{series_cfg['sidra'][qkey]['table']}_v{series_cfg['sidra'][qkey]['variable']}.json"
        if f.exists():
            frames.append(sidra_mod.sidra_quarterly_to_frame(io_utils.read_json(f)))
        else:
            missing.append(f"sidra:{qkey}")

    f = dirs["raw"] / "noaa" / "oni.json"
    if f.exists():
        frames.append(noaa_mod.noaa_to_frame(io_utils.read_json(f)))
    else:
        missing.append("noaa:oni")

    fred_payloads = {}
    for key in series_cfg["fred"]:
        f = dirs["raw"] / "fred" / f"{key}.json"
        p = io_utils.read_json(f) if f.exists() else None
        if p is not None:
            fred_payloads[key] = p
        else:
            missing.append(f"fred:{key}")
    fred_quarterly = {k for k, v in series_cfg["fred"].items() if v.get("freq") == "quarterly"}
    frames.append(fred_mod.fred_to_frame(fred_payloads, quarterly=fred_quarterly))

    ipea_payloads = {}
    for key in series_cfg["ipeadata"]["setorais"]:
        f = dirs["raw"] / "ipeadata" / f"{key}.json"
        p = io_utils.read_json(f) if f.exists() else None
        if p is not None and "error" not in p:
            ipea_payloads[key] = p
        else:
            missing.append(f"ipeadata:{key}")
    frames.append(ipeadata_mod.ipeadata_to_frame(ipea_payloads))

    if missing:
        print(f"AVISO: fontes sem cache ignoradas -> {missing}")
    return pd.concat(frames, ignore_index=True)


def _snapshot(frame: pd.DataFrame, cutoff: pd.Timestamp) -> pd.DataFrame:
    frame = frame.copy()
    # forçam Timestamp (robusto a valores não parseados / ambientes diferentes)
    frame["ref_date"] = pd.to_datetime(frame["ref_date"], errors="coerce")
    frame["available_from"] = pd.to_datetime(frame["available_from"], errors="coerce")
    return frame[(frame["ref_date"] <= cutoff) & (frame["available_from"] <= cutoff)]


def main() -> None:
    cfg = io_utils.settings()
    series_cfg = io_utils.load_yaml("series.yaml")
    avail = io_utils.load_yaml("availability.yaml")
    dirs = io_utils.data_dirs()

    frame = _load_all(cfg, series_cfg, dirs)
    frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
    frame = pit.apply_availability(frame, avail)
    frame = frame.dropna(subset=["ref_date"])
    # colunas de texto: converte via object (evita o backend string[pyarrow], que falha
    # no write do parquet com valores ausentes em alguns ambientes)
    for col in frame.select_dtypes(include=["object", "string"]).columns:
        frame[col] = frame[col].astype(object).fillna("").astype(str)
    frame = frame.sort_values(["source", "series", "ref_date"]).reset_index(drop=True)

    frame.to_parquet(dirs["processed"] / "series.parquet", index=False)
    print(f"Série longa: {len(frame):,} observações -> data/processed/series.parquet")
    print(frame.groupby(["source", "series"])["ref_date"].agg(["count", "max"]).to_string())

    snap_cfg = cfg["snapshots"]
    start = pd.Period(pit.quarter_cutoff(snap_cfg["start"]), freq="Q")
    now = pd.Timestamp.now().normalize()
    current_q = pd.Period(now, freq="Q")

    cutoffs = []
    q = start
    while q <= current_q:
        cutoffs.append(q.end_time.tz_localize(None).normalize())
        q = q + 1
    cutoffs.append(now)  # snapshot 'latest' com tudo disponível até hoje

    snap_manifest = {}
    for i, cutoff in enumerate(cutoffs):
        is_latest = (i == len(cutoffs) - 1)
        key = "latest" if is_latest else pit.quarter_key(cutoff)
        snap = _snapshot(frame, cutoff)
        out_dir = dirs["snapshots"] / f"pt_{key}"
        out_dir.mkdir(parents=True, exist_ok=True)
        snap.to_parquet(out_dir / "data.parquet", index=False)

        cov = snap.groupby(["source", "series"])["ref_date"].agg(["count", "max"])
        cov = cov.rename(columns={"count": "n", "max": "ultimo_ref"})
        cov["ultimo_ref"] = pd.to_datetime(cov["ultimo_ref"]).dt.strftime("%Y-%m-%d")
        snap_manifest[key] = {
            "cutoff": cutoff.isoformat(),
            "rows": int(len(snap)),
            "coverage": {f"{i[0]}|{i[1]}": {"n": int(r.n), "ultimo_ref": r.ultimo_ref}
                         for i, r in cov.iterrows()},
        }
        print(f"Snapshot {key}: cutoff={cutoff.date()} obs={len(snap):,}")

    io_utils.write_json(dirs["processed"] / "snapshots_manifest.json", snap_manifest)

    max_avail = frame.groupby(["source", "series"])["available_from"].max().max()
    print(f"ok. Último available_from geral: {max_avail}")


if __name__ == "__main__":
    main()
