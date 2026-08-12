"""Satélite de itens administrados (anexo B9 do modelo do BCB).

Estima uma equação por categoria administrada (24 grupos mapeados aos subitens
do SIDRA 7060, 2020+). Regressores por categoria:
    - inércia própria (t-1)
    - indexação à inflação passada (IPCA acumulado 12m)
    - Δpetróleo em R$ (Brent × câmbio)  — energia, GLP, combustíveis
    - Δcâmbio                            — telecom, medicamentos, etc.
    - dummies sazonais de reajuste (amostra >= 60 meses)

A projeção mensal compõe o IPCA administrado trimestral, usado como caminho
exógeno no sistema completo (duas passagens).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm

# categoria -> códigos de subitem (item_code do SIDRA 7060, classificação atual)
ADMIN_CATS: dict[str, list[str]] = {
    "agua_esgoto": ["7451"],
    "gas_botijao": ["7482"],
    "gas_encanado": ["7483"],
    "energia_eletrica": ["7485"],
    "onibus_urbano": ["7628"],
    "taxi": ["7629"],
    "trem": ["7630"],
    "onibus_intermunicipal": ["7631"],
    "onibus_interestadual": ["7632"],
    "metro": ["7635"],
    "transporte_escolar": ["7639"],
    "emplacamento_licenca": ["7642"],
    "gasolina": ["7657"],
    "etanol": ["7658"],
    "diesel": ["7659"],
    "plano_saude": ["7696"],
    "conselho_classe": ["7728"],
    "cigarro": ["7759"],
    "correio": ["7789"],
    "telefonia_fixa": ["47668"],
    "telefonia_movel": ["47669"],
    "tv_assinatura": ["47670"],
    "internet": ["107688"],
    "combo_telecom": ["47672"],
    # medicamentos (produtos farmacêuticos; preços administrados pela CMED/ANVISA).
    # Nota: não reproduz a série oficial de administrados (ver doc) — módulo de pesquisa.
    "medicamentos": ["7663", "7664", "7665", "7666", "12412", "7669", "7670",
                     "7671", "47651", "7673", "7674", "107659", "7677", "47652"],
}
ITEM2CAT = {code: cat for cat, codes in ADMIN_CATS.items() for code in codes}


def build_admin_monthly(df: pd.DataFrame) -> pd.DataFrame:
    """Série mensal por categoria: variação (v=63) e peso (v=66).

    Retorna DataFrame indexado por ref_date com colunas de variação
    (prefixo 'v_') e peso (prefixo 'w_') por categoria.
    """
    sub = df[(df["source"] == "sidra") & (df["variable"].isin([63, 66]))].copy()
    sub["ref_date"] = pd.to_datetime(sub["ref_date"])
    sub = sub[sub["item_name"].astype(str).str.match(r"^\d{7,}\.")].copy()
    sub = sub[sub["item_code"].astype(str).isin(ITEM2CAT)].copy()
    sub["cat"] = sub["item_code"].astype(str).map(ITEM2CAT)

    wide = sub.pivot_table(index=["ref_date", "cat"], columns="variable",
                           values="value").reset_index()
    # pivot_table ordena colunas numericamente: 63 (variação) antes de 66 (peso)
    wide.columns = ["ref_date", "cat", "v", "w"]

    v = wide.pivot(index="ref_date", columns="cat", values="v")
    w = wide.pivot(index="ref_date", columns="cat", values="w")
    v.columns = [f"v_{c}" for c in v.columns]
    w.columns = [f"w_{c}" for c in w.columns]
    out = v.join(w)
    cats = [c for c in ADMIN_CATS if f"v_{c}" in out.columns and f"w_{c}" in out.columns]
    if cats:
        out["v_admin"] = sum(out[f"v_{c}"] * out[f"w_{c}"] for c in cats) / \
            sum(out[f"w_{c}"] for c in cats)
        out["w_admin"] = sum(out[f"w_{c}"] for c in cats)
    return out


def _aux_macro(m: pd.DataFrame, df: pd.DataFrame) -> pd.DataFrame:
    """Joga IPCA 12m, Δcâmbio e Δpetróleo(R$) mensais num DataFrame mensal."""
    sgs = df[df["source"] == "sgs"]
    ipca12 = sgs[sgs["series"] == "ipca_12m"][["ref_date", "value"]]
    ipca12 = ipca12.set_index(pd.to_datetime(ipca12["ref_date"]))["value"].astype(float).sort_index()
    cambio = sgs[sgs["series"] == "cambio_media"][["ref_date", "value"]]
    cambio = cambio.set_index(pd.to_datetime(cambio["ref_date"]))["value"].astype(float).sort_index()
    brent = df[(df["source"] == "fred") & (df["series"] == "brent")][["ref_date", "value"]]
    brent = brent.set_index(pd.to_datetime(brent["ref_date"]))["value"].astype(float).sort_index()

    brent_rl = brent * cambio  # US$/barril x R$/US$ = R$/barril
    macro = pd.DataFrame({
        "ipca12": ipca12,
        "dln_cambio": np.log(cambio).diff() * 100,
        "dln_brent_rl": np.log(brent_rl).diff() * 100,
    })
    return m.join(macro)


def estimate_admin24(df: pd.DataFrame, start: str = "2020-03") -> dict:
    """Estima as 24 equações de administrados (OLS mensal por categoria)."""
    m = build_admin_monthly(df)
    m = _aux_macro(m, df)
    m = m.loc[start:]

    cats = [c for c in ADMIN_CATS if f"v_{c}" in m.columns]
    out: dict = {}
    for cat in cats:
        y = m[f"v_{cat}"]
        d = pd.DataFrame({
            "y": y,
            "y_1": y.shift(1),
            "ipca12_1": m["ipca12"].shift(1),
            "dln_cambio_1": m["dln_cambio"].shift(1),
            "dln_brent_rl": m["dln_brent_rl"],
        })
        regs = ["y_1", "ipca12_1", "dln_cambio_1", "dln_brent_rl"]
        if len(d.dropna()) >= 60:
            for mo in (1, 5, 7, 10):
                d[f"d_{mo}"] = (d.index.month == mo).astype(float)
                regs.append(f"d_{mo}")
        d = d.dropna(subset=regs + ["y"])
        if len(d) < 30:
            out[cat] = None
            continue
        res = sm.OLS(d["y"], sm.add_constant(d[regs]), missing="drop").fit()
        out[cat] = {
            "params": {k: float(v) for k, v in res.params.items()},
            "stderr": {k: float(v) for k, v in res.bse.items()},
            "pvalues": {k: float(v) for k, v in res.pvalues.items()},
            "n": int(res.nobs), "r2": float(res.rsquared), "resid": res.resid,
            "weight": float(m[f"w_{cat}"].iloc[-1]),
        }
    return out


def validate_admin24(df: pd.DataFrame) -> pd.DataFrame:
    """Compara o agregado ponderado do satélite com o IPCA administrado oficial (SGS)."""
    m = build_admin_monthly(df)
    m = _aux_macro(m, df)
    m["admin_rep"] = m["v_admin"]
    sgs = df[(df["source"] == "sgs") & (df["series"] == "ipca_admin")][["ref_date", "value"]]
    sgs = sgs.set_index(pd.to_datetime(sgs["ref_date"]))["value"].astype(float).sort_index()
    out = pd.DataFrame({
        "oficial": sgs.reindex(m.index),
        "satelite": m["v_admin"],
    }).dropna()
    return out


def forecast_admin_monthly(est: dict, m: pd.DataFrame, last: pd.DataFrame,
                           brent_path: pd.Series, cambio_path: pd.Series,
                           ipca12_path: pd.Series, horizon: int) -> pd.DataFrame:
    """Projeta a inflação administrada mensal (satélite) no horizonte.

    m: base mensal histórica (saída de build_admin_monthly + macro).
    last: última linha de m (estado inicial).
    Retorna DataFrame com v_admin mensal projetado.
    """
    cats = [c for c in ADMIN_CATS if est.get(c) is not None and f"v_{c}" in last.index]
    # séries de projeção dos regressores
    dln_c = np.log(cambio_path).diff().fillna(0) * 100
    brent_rl = brent_path * cambio_path
    dln_b = np.log(brent_rl).diff().fillna(0) * 100

    state = {c: float(last[f"v_{c}"]) for c in cats}
    ipca12 = float(ipca12_path.iloc[0]) if len(ipca12_path) else float(last.get("ipca12", 0))
    rows = []
    for i in range(horizon):
        pred_cats = {}
        for c in cats:
            p = est[c]["params"]
            x = {
                "const": 1.0, "y_1": state[c],
                "ipca12_1": ipca12, "dln_cambio_1": float(dln_c.iloc[i]) if i < len(dln_c) else 0.0,
                "dln_brent_rl": float(dln_b.iloc[i]) if i < len(dln_b) else 0.0,
            }
            for mo in (1, 5, 7, 10):
                x[f"d_{mo}"] = 1.0 if (mo in p and i < len(dln_c)) else 0.0
            val = sum(p.get(k, 0.0) * v for k, v in x.items())
            pred_cats[c] = val
            state[c] = val
        w = {c: float(last[f"w_{c}"]) for c in cats}
        total_w = sum(w.values())
        pred_cats["v_admin"] = sum(pred_cats[c] * w[c] for c in cats) / total_w
        rows.append(pred_cats | {"month": i})
        ipca12 = ipca12  # mantém indexação passada constante na projeção curta
    return pd.DataFrame(rows)
