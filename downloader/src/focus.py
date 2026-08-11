"""Cliente Focus (BCB/OLINDA) — expectativas de mercado."""
from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import quote, urlencode

import pandas as pd

from .io_utils import http_get, raw_cache_path, read_cached, write_json

BASE = ("https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/"
        "{endpoint}")

ENDPOINTS = {
    "trimestrais": "ExpectativasMercadoTrimestrais",
    "anuais": "ExpectativasMercadoAnuais",
    "12meses": "ExpectativasMercadoInflacao12Meses",
    "mensais": "ExpectativaMercadoMensais",
}


def _odata_url(endpoint: str, params: dict) -> str:
    # OLINDA rejeita codificação form (`+` no lugar de espaço). Codificamos
    # manualmente com `%20`/`%27` para o filtro OData funcionar.
    query = urlencode(params, quote_via=quote)
    return f"{BASE.format(endpoint=endpoint)}?{query}"


def _fetch_endpoint(endpoint: str, indicador: str, cfg: dict) -> list[dict]:
    filtro = f"Indicador eq '{indicador}'"
    out: list[dict] = []
    skip = 0
    top = 10000
    max_rows = 500_000
    while len(out) < max_rows:
        url = _odata_url(
            endpoint,
            {"$filter": filtro, "$skip": skip, "$top": top, "$format": "json"},
        )
        data = http_get(url, cfg=cfg, expect_json=True)
        batch = data.get("value", [])
        out.extend(batch)
        if len(batch) < top:
            break
        skip += top
    return out


def download_focus(indicators: list[str], cfg: dict, dirs: dict,
                   force: bool = False, max_age_days: int | None = None) -> dict[str, dict]:
    max_age_days = cfg.get("cache_max_age_days") if max_age_days is None else max_age_days
    out: dict[str, dict] = {}
    for indicador in indicators:
        for key, endpoint in ENDPOINTS.items():
            path = raw_cache_path(dirs, "focus", f"{indicador}_{key}")
            cached, fresh = read_cached(path, max_age_days)
            if cached is not None and fresh and not force:
                out[f"{indicador}_{key}"] = cached
                continue
            values = _fetch_endpoint(endpoint, indicador, cfg)
            payload = {
                "indicador": indicador,
                "endpoint": key,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "values": values,
            }
            write_json(path, payload)
            out[f"{indicador}_{key}"] = payload
    return out


def focus_to_frame(payloads: dict[str, dict]) -> pd.DataFrame:
    rows = []
    for key, payload in payloads.items():
        ind = payload["indicador"]
        horizon = payload["endpoint"]
        for v in payload["values"]:
            rows.append(
                {
                    "source": "focus",
                    "series": f"focus_{horizon}",
                    "indicador": ind,
                    "ref_date": v.get("DataReferencia"),
                    "survey_date": v.get("Data"),
                    "value": v.get("Mediana"),
                    "mean": v.get("Media"),
                    "min": v.get("Minimo"),
                    "max": v.get("Maximo"),
                    "respondentes": v.get("numeroRespondentes"),
                }
            )
    return pd.DataFrame(rows)
