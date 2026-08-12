"""Check de vintage da especificação (point-in-time da SPEC, não só dos dados).

A especificação do modelo (priors, calibração de admin, cenário) é uma "vintage" da
publicação do BCB. Ao reestimar numa vintage `t`, usar especificação publicada depois
de `t` é vazamento de especificação (análogo ao look-ahead nos dados).

Uso:
    from spec_manifesto import check_spec, available_from
    check_spec("priors_agregado", cutoff)   # warning se available_from > cutoff
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

CONFIG = Path(__file__).resolve().parent.parent / "config" / "spec_manifesto.yaml"


def load_manifest(path=CONFIG) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def available_from(name: str, manifest: dict | None = None) -> pd.Timestamp | None:
    manifest = manifest or load_manifest()
    spec = manifest.get("specs", {}).get(name)
    if spec is None:
        return None
    return pd.Timestamp(spec["available_from"])


def check_spec(name: str, cutoff, manifest: dict | None = None) -> bool:
    """Avisa (print) se a especificação é posterior ao cutoff. Retorna True se ok."""
    av = available_from(name, manifest)
    if av is None:
        print(f"[spec_manifesto] '{name}' não encontrado no manifesto.")
        return False
    if pd.isna(cutoff):
        return True
    if av > pd.Timestamp(cutoff):
        print(f"[spec_manifesto] ATENÇÃO: spec '{name}' (available_from {av.date()}) é "
              f"posterior ao cutoff {pd.Timestamp(cutoff).date()} — vazamento de especificação.")
        return False
    return True


def check_scenario(cfg: dict, cutoff) -> bool:
    """Checa o cenário carregado (rpm.yaml) contra o cutoff do snapshot."""
    name = cfg.get("spec_name", "rpm_2026q2")
    return check_spec(name, cutoff)
