"""Utilitários de caminho, config e HTTP com retry."""
from __future__ import annotations

import json
import time
from pathlib import Path
from urllib.parse import urlencode

import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"


def data_dirs() -> dict[str, Path]:
    raw = DATA_DIR / "raw"
    processed = DATA_DIR / "processed"
    snapshots = DATA_DIR / "snapshots"
    for p in (raw, processed, snapshots):
        p.mkdir(parents=True, exist_ok=True)
    return {"raw": raw, "processed": processed, "snapshots": snapshots}


def load_yaml(name: str) -> dict:
    path = CONFIG_DIR / name
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def settings() -> dict:
    return load_yaml("settings.yaml")


def read_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, payload) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def http_get(url: str, params: dict | None = None, cfg: dict | None = None,
             timeout: float | None = None, headers: dict | None = None,
             expect_json: bool = False):
    cfg = cfg or settings()
    h = cfg.get("http", {})
    to = timeout or h.get("timeout", 40)
    retries = h.get("retries", 4)
    backoff = h.get("backoff", 3)
    hdrs = {"User-Agent": h.get("user_agent", "python-requests")}
    if headers:
        hdrs.update(headers)

    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, headers=hdrs, timeout=to)
            if r.status_code == 200:
                if expect_json:
                    try:
                        return r.json()
                    except ValueError:
                        last_err = RuntimeError("HTTP 200 com corpo JSON inválido/vazio")
                        time.sleep(backoff * (attempt + 1))
                        continue
                return r
            if 400 <= r.status_code < 500:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
            last_err = RuntimeError(f"HTTP {r.status_code}")
        except RuntimeError:
            raise
        except Exception as e:  # noqa: BLE001 - timeout/rede precisam de retry
            last_err = e
        time.sleep(backoff * (attempt + 1))
    raise RuntimeError(f"Falha ao buscar {url} ({params}): {last_err}") from last_err


def raw_cache_path(dirs: dict[str, Path], source: str, key: str) -> Path:
    folder = dirs["raw"] / source
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{key}.json"


def read_cached(raw_path: Path, max_age_days: int | None = None):
    """Lê cache raw; retorna (payload, is_fresh)."""
    if not raw_path.exists():
        return None, False
    data = read_json(raw_path)
    fresh = True
    if max_age_days is not None:
        fetched = data.get("fetched_at")
        if fetched:
            from datetime import datetime

            age = (datetime.utcnow() - datetime.fromisoformat(fetched)).days
            fresh = age <= max_age_days
    return data, fresh
