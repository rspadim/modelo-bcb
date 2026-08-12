"""Bloco de preços administrados CALIBRADO — regras institucionais (anexo B9 do RPM jun/2025).

O BCB não estima as 24 equações de administrados: "these are not estimated equations,
but calibrated equations based on the current institutional framework" (B9). A estrutura
de cada item segue a regra de reajuste; as constantes sazonais (tamanho/época dos
reajustes) vêm de estimação 2020+ combinada com julgamento.

Nesta réplica, cada item é modelado por:
    pi_item,t = Σ_m δ_m·D_m(t)  +  a·ipca12_{t-1}  +  b·Δpetróleo(R$)_t
                + g·Δcâmbio_t   +  θ·Δbandeira_t   +  ε

com canais ligados/desligados por teoria (B9):
  - ipca12 ≥ 0            : indexação à inflação passada (todos os itens)
  - petróleo(R$) ≥ 0      : gasolina, etanol, diesel, GLP, gás encanado
  - câmbio ≥ 0            : energia (Itaipu), medicamentos, telecom
  - bandeira ≥ 0          : energia elétrica (sinal de escassez, adicional ANEEL)

A agregação usa os pesos dos subitens (SIDRA v=66) e valida contra a série oficial
(SGS 11427). As IRFs alvo (B9): câmbio +10% → admin ≈ +1,8 p.p. em 4T; petróleo +10%
→ ≈ +1,3 p.p.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import lsq_linear

CONFIG = __import__("pathlib").Path(__file__).resolve().parent.parent / "config" / "bandeiras.csv"

# item_code -> canais da regra (B9)
ADMIN_ITEMS: dict[str, dict] = {
    "7485": {"name": "energia_eletrica", "ipca": True, "fx": True, "oil": False, "bandeira": True},
    "7657": {"name": "gasolina", "ipca": True, "fx": False, "oil": True, "bandeira": False},
    "7658": {"name": "etanol", "ipca": True, "fx": False, "oil": True, "bandeira": False},
    "7659": {"name": "diesel", "ipca": True, "fx": False, "oil": True, "bandeira": False},
    "7482": {"name": "gas_botijao", "ipca": True, "fx": False, "oil": True, "bandeira": False},
    "7483": {"name": "gas_encanado", "ipca": True, "fx": False, "oil": True, "bandeira": False},
    "7696": {"name": "plano_saude", "ipca": True, "fx": False, "oil": False, "bandeira": False},
    "47668": {"name": "telefonia_fixa", "ipca": True, "fx": True, "oil": False, "bandeira": False},
    "47669": {"name": "telefonia_movel", "ipca": True, "fx": True, "oil": False, "bandeira": False},
    "47670": {"name": "tv_assinatura", "ipca": True, "fx": True, "oil": False, "bandeira": False},
    "107688": {"name": "internet", "ipca": True, "fx": True, "oil": False, "bandeira": False},
    "47672": {"name": "combo_telecom", "ipca": True, "fx": True, "oil": False, "bandeira": False},
    "7628": {"name": "onibus_urbano", "ipca": True, "fx": False, "oil": False, "bandeira": False},
    "7629": {"name": "taxi", "ipca": True, "fx": False, "oil": False, "bandeira": False},
    "7630": {"name": "trem", "ipca": True, "fx": False, "oil": False, "bandeira": False},
    "7631": {"name": "onibus_intermunicipal", "ipca": True, "fx": False, "oil": False, "bandeira": False},
    "7632": {"name": "onibus_interestadual", "ipca": True, "fx": False, "oil": False, "bandeira": False},
    "7635": {"name": "metro", "ipca": True, "fx": False, "oil": False, "bandeira": False},
    "7639": {"name": "transporte_escolar", "ipca": True, "fx": False, "oil": False, "bandeira": False},
    "7642": {"name": "emplacamento_licenca", "ipca": True, "fx": False, "oil": False, "bandeira": False},
    "7728": {"name": "conselho_classe", "ipca": True, "fx": False, "oil": False, "bandeira": False},
    "7451": {"name": "agua_esgoto", "ipca": True, "fx": False, "oil": False, "bandeira": False},
    "7789": {"name": "correio", "ipca": True, "fx": False, "oil": False, "bandeira": False},
    "7759": {"name": "cigarro", "ipca": True, "fx": False, "oil": False, "bandeira": False},
}

# Repasses por item do anexo B9 (RPM jun/2025): fração do choque repassada em 4T.
# Frações de repasse (câmbio = Δe, petróleo = Δpetróleo em R$), por categoria.
B9_PT = {
    "energia_eletrica": {"fx": 0.08},          # Itaipu ~8% do custo de energia
    "gasolina": {"oil": 0.50},                 # ~50% em 4T
    "etanol": {"oil": 0.50},                   # segue gasolina
    "diesel": {"oil": 0.65},                   # menor carga de imposto -> maior repasse
    "gas_botijao": {"oil": 0.20},              # ~20% em 4T (margem/custo alto)
    "gas_encanado": {"oil": 0.30},             # petróleo + gás de botijão
    "medicamentos": {"fx": 0.15},              # insumos importados
    "telefonia_fixa": {"fx": 0.10}, "telefonia_movel": {"fx": 0.10},
    "tv_assinatura": {"fx": 0.10}, "internet": {"fx": 0.10}, "combo_telecom": {"fx": 0.10},
}
# medicamentos (folhas de produtos farmacêuticos, CMED) — tratados como uma categoria
MED_CODES = ["7663", "7664", "7665", "7666", "12412", "7669", "7670",
             "7671", "47651", "7673", "7674", "107659", "7677", "47652"]
CATEGORY_OF: dict[str, str] = {code: it["name"] for code, it in ADMIN_ITEMS.items()}
for c in MED_CODES:
    CATEGORY_OF[c] = "medicamentos"


def load_bandeiras(path=CONFIG) -> pd.DataFrame:
    b = pd.read_csv(path)
    b["mes"] = pd.to_datetime(b["mes"])
    b = b.set_index("mes")["adicional_rl_mwh"].astype(float).sort_index()
    return b


def build_monthly(df: pd.DataFrame, bandeiras: pd.DataFrame | None = None) -> pd.DataFrame:
    """Série mensal por categoria (variação, peso) + macro mensal (ipca12, petróleo R$, câmbio, bandeira)."""
    sub = df[(df["source"] == "sidra") & (df["variable"].isin([63, 66]))].copy()
    sub["ref_date"] = pd.to_datetime(sub["ref_date"])
    sub = sub[sub["item_name"].astype(str).str.match(r"^\d{7,}\.")].copy()
    sub["cat"] = sub["item_code"].astype(str).map(CATEGORY_OF)
    sub = sub.dropna(subset=["cat"])

    wide = sub.pivot_table(index=["ref_date", "cat"], columns="variable", values="value").reset_index()
    wide.columns = ["ref_date", "cat", "v", "w"]  # 63 (variação) antes de 66 (peso)

    cats = [c for c in wide["cat"].unique()]
    out = pd.DataFrame(index=pd.date_range(wide["ref_date"].min(), wide["ref_date"].max(), freq="MS"))
    for c in cats:
        d = wide[wide["cat"] == c].set_index("ref_date")
        out[f"v_{c}"] = d["v"]
        out[f"w_{c}"] = d["w"]

    # macro mensal
    sgs = df[df["source"] == "sgs"]
    def _sgs(key):
        s = sgs[sgs["series"] == key][["ref_date", "value"]]
        return s.set_index(pd.to_datetime(s["ref_date"]))["value"].astype(float).sort_index()
    ipca12 = _sgs("ipca_12m")
    cambio = _sgs("cambio_media")
    brent = df[(df["source"] == "fred") & (df["series"] == "brent")][["ref_date", "value"]]
    brent = brent.set_index(pd.to_datetime(brent["ref_date"]))["value"].astype(float).sort_index()

    out["ipca12"] = ipca12.reindex(out.index)
    out["dln_cambio"] = np.log(cambio.reindex(out.index)).diff() * 100
    out["dln_brent_rl"] = np.log(brent.reindex(out.index) * cambio.reindex(out.index)).diff() * 100
    # suavização MA-3: preserva o repasse acumulado do B9 (choque de nível) reduzindo ruído mensal
    out["dln_cambio3"] = out["dln_cambio"].rolling(3, min_periods=1).mean()
    out["dln_brent_rl3"] = out["dln_brent_rl"].rolling(3, min_periods=1).mean()

    if bandeiras is not None:
        b = bandeiras.reindex(out.index).ffill()
        out["d_bandeira"] = b.diff().fillna(0.0)
    else:
        out["d_bandeira"] = 0.0

    cats_present = [c for c in cats if f"v_{c}" in out.columns]
    out["v_admin_raw"] = sum(out[f"v_{c}"] * out[f"w_{c}"] for c in cats_present) / \
        sum(out[f"w_{c}"] for c in cats_present)
    return out


def _bounds(spec: dict) -> tuple[list, list]:
    """Bounds por regressor conforme os canais teóricos do item."""
    lo, hi = [], []
    # ordem: const, 11 dummies mensais (referência = dezembro), ipca12, dln_brent_rl, dln_cambio, d_bandeira
    lo.append(-np.inf); hi.append(np.inf)                    # const
    for _ in range(11):
        lo.append(-np.inf); hi.append(np.inf)                # dummies sazonais
    lo.append(0.0); hi.append(np.inf)                        # ipca12 >= 0 (indexação)
    lo.append(0.0 if spec["oil"] else -np.inf); hi.append(np.inf)
    lo.append(0.0 if spec["fx"] else -np.inf); hi.append(np.inf)
    lo.append(0.0 if spec["bandeira"] else -np.inf); hi.append(np.inf)
    return lo, hi


def calibrate(df: pd.DataFrame, start: str = "2020-03", bandeiras: pd.DataFrame | None = None) -> dict:
    """Calibra as equações por item (estrutura B9 + constantes sazonais por estimação)."""
    m = build_monthly(df, bandeiras).loc[start:].copy()
    cats = [c for c in {CATEGORY_OF[c] for c in CATEGORY_OF} if f"v_{c}" in m.columns]
    out: dict = {}
    for cat in cats:
        y = m[f"v_{cat}"]
        X = pd.DataFrame({"const": 1.0}, index=m.index)
        for mo in range(1, 12):
            X[f"d{mo}"] = (y.index.month == mo).astype(float)
        X["ipca12_1"] = m["ipca12"].shift(1)
        X["dln_brent_rl"] = m["dln_brent_rl"]
        X["dln_cambio"] = m["dln_cambio"]
        X["d_bandeira"] = m["d_bandeira"]

        spec = {"oil": cat in {"gasolina", "etanol", "diesel", "gas_botijao", "gas_encanado"},
                "fx": cat in {"energia_eletrica", "medicamentos", "telefonia_fixa",
                              "telefonia_movel", "tv_assinatura", "internet", "combo_telecom"},
                "bandeira": cat == "energia_eletrica"}
        d = pd.concat([y, X], axis=1).dropna()
        if len(d) < 40:
            continue
        lo, hi = _bounds(spec)
        res = lsq_linear(d[X.columns].values, d[y.name].values, bounds=(lo, hi))
        params = dict(zip(X.columns, res.x))
        out[cat] = {
            "params": {k: float(v) for k, v in params.items()},
            "spec": spec, "n": int(len(d)),
            "weight": float(m[f"w_{cat}"].iloc[-1]),
        }
    return out


def _predict(est: dict, m: pd.DataFrame) -> pd.DataFrame:
    pred = {}
    for cat, r in est.items():
        p = r["params"]
        X = pd.DataFrame({"const": 1.0}, index=m.index)
        for mo in range(1, 12):
            X[f"d{mo}"] = (m.index.month == mo).astype(float)
        X["ipca12_1"] = m["ipca12"].shift(1)
        X["dln_brent_rl"] = m["dln_brent_rl"]
        X["dln_cambio"] = m["dln_cambio"]
        X["d_bandeira"] = m["d_bandeira"]
        pred[cat] = sum(p.get(k, 0.0) * X[k] for k in X.columns)
    out = pd.DataFrame(pred, index=m.index)
    w = pd.DataFrame({c: m[f"w_{c}"] for c in pred}, index=m.index)
    out["v_admin"] = sum(out[c] * w[c] for c in pred) / w.sum(axis=1)
    return out


def _irf_scale(df: pd.DataFrame, est: dict, shock: str, coeff: float,
               bandeiras: pd.DataFrame | None = None, horizon: int = 12) -> float:
    """Resposta de pico do acumulado 4T de admin a um choque permanente de nível.

    shock='fx' (câmbio +10%) ou 'oil' (petróleo +10%). Retorna Δ p.p. no pico.
    """
    sgs = df[(df["source"] == "sgs") & (df["series"] == "cambio_media")][["ref_date", "value"]]
    last = pd.Timestamp(sgs["ref_date"].max())
    idx = pd.date_range(last + pd.DateOffset(months=1), periods=horizon, freq="MS")
    c0 = float(sgs.set_index(pd.to_datetime(sgs["ref_date"]))["value"].astype(float).dropna().iloc[-1])
    br = df[(df["source"] == "fred") & (df["series"] == "brent")][["ref_date", "value"]]
    b0 = float(br.set_index(pd.to_datetime(br["ref_date"]))["value"].astype(float).dropna().iloc[-1])
    ipca12 = pd.Series(4.5, index=idx)
    band_fut = bandeiras.reindex(idx).ffill().fillna(0.0) if bandeiras is not None \
        else pd.Series(0.0, index=idx)

    def run(cx, bx):
        est2 = dict(est)
        est2["params"] = {**est["params"]}
        if shock == "fx":
            est2["params"]["dln_cambio"] = coeff
        else:
            est2["params"]["dln_brent_rl"] = coeff
        mono = forecast_admin_calibrado(est2, df, pd.Series(bx, index=idx),
                                        pd.Series(cx, index=idx), ipca12, band_fut, horizon)
        q = mono.resample("QE").apply(lambda x: (np.prod(1 + np.asarray(x) / 100) - 1) * 100)
        q4 = ((1 + q / 100).rolling(4).apply(np.prod, raw=True) - 1) * 100
        return q4

    base = run(c0, b0)
    shk = run(c0 * 1.10, b0) if shock == "fx" else run(c0, b0 * 1.10)
    diff = (shk - base).dropna()
    return float(diff.abs().max()) if len(diff) else 0.0


def b9_weighted_passthrough(df: pd.DataFrame) -> dict:
    """Repasse agregado ponderado pelos pesos dos itens e pelas frações do B9."""
    m = build_monthly(df, None)
    w = {c: m[f"w_{c}"].iloc[-1] for c in set(B9_PT)}
    tot = sum(w.values())
    fx = sum(w.get(c, 0) * pt.get("fx", 0) for c, pt in B9_PT.items())
    oil = sum(w.get(c, 0) * pt.get("oil", 0) for c, pt in B9_PT.items())
    return {"fx": fx / tot if tot else 0.0, "oil": oil / tot if tot else 0.0}


def calibrate_aggregate(df: pd.DataFrame, start: str = "2020-03",
                        bandeiras: pd.DataFrame | None = None,
                        fx_target: float = 1.8, oil_target: float = 1.3) -> dict:
    """Calibra o AGREGADO de administrados sobre a série oficial (SGS 11427).

    Estrutura do B9 (constantes sazonais + indexação + petróleo R$ + câmbio + bandeira),
    com canais de sinal teórico (≥0). Os repasses de câmbio e petróleo são CALIBRADOS
    nos alvos do anexo B9 (câmbio +10% → admin +1,8 p.p. em 4T; petróleo +10% → +1,3 p.p.):
    o coeficiente é ajustado numericamente para reproduzir o alvo (linear → um passo).
    O restante (sazonalidade + indexação + bandeira) é ajustado sobre a série oficial.
    """
    m = build_monthly(df, bandeiras).loc[start:].copy()
    sgs = df[(df["source"] == "sgs") & (df["series"] == "ipca_admin")][["ref_date", "value"]]
    sgs = sgs.set_index(pd.to_datetime(sgs["ref_date"]))["value"].astype(float)
    y = sgs.reindex(m.index)
    X = pd.DataFrame({"const": 1.0}, index=m.index)
    for mo in range(1, 12):
        X[f"d{mo}"] = (m.index.month == mo).astype(float)
    X["ipca12_1"] = m["ipca12"].shift(1)
    X["dln_brent_rl"] = m["dln_brent_rl3"]
    X["dln_cambio"] = m["dln_cambio3"]
    X["d_bandeira"] = m["d_bandeira"]
    d = pd.concat([y, X], axis=1).dropna()

    # contribuição fixa dos repasses (calibrada depois) e ajuste sazonal/indexação/bandeira.
    # Inicial calibrado empiricamente (0,19/0,14 reproduz os alvos com melhor ajuste);
    # a composição por item do B9 está documentada em B9_PT (referência).
    fx_passthrough, oil_passthrough = 0.19, 0.14
    fixed = fx_passthrough * d["dln_cambio"] + oil_passthrough * d["dln_brent_rl"]
    rest = d[y.name] - fixed
    regs = [c for c in X.columns if c not in ("dln_cambio", "dln_brent_rl")]
    lo = [-np.inf] + [-np.inf] * 11 + [0.0, 0.0]  # const, dummies(11), ipca12>=0, bandeira>=0
    hi = [np.inf] * (len(regs))
    res = lsq_linear(d[regs].values, rest.values, bounds=(lo, hi))
    params = dict(zip(regs, res.x))
    params["dln_cambio"] = fx_passthrough
    params["dln_brent_rl"] = oil_passthrough

    # calibra os repasses para bater os alvos do B9 (composto 4T é levemente não-linear -> itera)
    est = {"params": params, "n": int(len(d))}
    g_fx, g_oil = fx_passthrough, oil_passthrough
    for _ in range(6):
        est["params"]["dln_cambio"] = g_fx
        est["params"]["dln_brent_rl"] = g_oil
        resp_fx = _irf_scale(df, est, "fx", g_fx, bandeiras)
        resp_oil = _irf_scale(df, est, "oil", g_oil, bandeiras)
        if resp_fx > 1e-9:
            g_fx = g_fx * fx_target / resp_fx
        if resp_oil > 1e-9:
            g_oil = g_oil * oil_target / resp_oil
    params["dln_cambio"] = g_fx
    params["dln_brent_rl"] = g_oil
    return {"params": params, "n": int(len(d))}


def validate(df: pd.DataFrame, start: str = "2020-03", bandeiras: pd.DataFrame | None = None) -> pd.DataFrame:
    """Ajuste in-sample do agregado calibrado vs SGS 11427."""
    est = calibrate_aggregate(df, start, bandeiras)
    m = build_monthly(df, bandeiras).loc[start:].copy()
    p = est["params"]
    X = pd.DataFrame({"const": 1.0}, index=m.index)
    for mo in range(1, 12):
        X[f"d{mo}"] = (m.index.month == mo).astype(float)
    X["ipca12_1"] = m["ipca12"].shift(1)
    X["dln_brent_rl"] = m["dln_brent_rl3"]
    X["dln_cambio"] = m["dln_cambio3"]
    X["d_bandeira"] = m["d_bandeira"]
    fit = sum(p.get(k, 0.0) * X[k] for k in X.columns)
    sgs = df[(df["source"] == "sgs") & (df["series"] == "ipca_admin")][["ref_date", "value"]]
    sgs = sgs.set_index(pd.to_datetime(sgs["ref_date"]))["value"].astype(float)
    out = pd.DataFrame({"oficial": sgs.reindex(fit.index), "calibrado": fit}).dropna()
    return out


def forecast_admin_calibrado(est: dict, df: pd.DataFrame, brent_path: pd.Series,
                             cambio_path: pd.Series, ipca12_path: pd.Series,
                             bandeira_path: pd.Series | None = None,
                             horizon: int = 12, start: str = "2020-03") -> pd.Series:
    """Projeta o IPCA administrado mensal usando a EQUAÇÃO AGREGADA calibrada (SGS 11427).

    brent_path/cambio_path: séries mensais (nível). O choque de nível no 1º período é
    capturado relativo ao último valor histórico (repasse do B9). Canais suavizados
    em MA-3, coerentes com a calibração.
    """
    p = est["params"]
    # último nível histórico mensal de brent e câmbio (para o diff do 1º período)
    sgs = df[(df["source"] == "sgs") & (df["series"] == "cambio_media")][["ref_date", "value"]]
    c_last = float(sgs.set_index(pd.to_datetime(sgs["ref_date"]))["value"].astype(float).dropna().iloc[-1])
    br = df[(df["source"] == "fred") & (df["series"] == "brent")][["ref_date", "value"]]
    b_last = float(br.set_index(pd.to_datetime(br["ref_date"]))["value"].astype(float).dropna().iloc[-1])

    def ma3(x: pd.Series) -> pd.Series:
        return x.rolling(3, min_periods=1).mean()

    c_all = pd.concat([pd.Series([c_last]), cambio_path])
    b_all = pd.concat([pd.Series([b_last]), brent_path])
    dln_c = ma3(np.log(c_all).diff().fillna(0.0) * 100).iloc[1:].reset_index(drop=True)
    dln_b = ma3(np.log(b_all * c_all).diff().fillna(0.0) * 100).iloc[1:].reset_index(drop=True)

    ipca12 = float(ipca12_path.iloc[0]) if len(ipca12_path) else 0.0
    db = bandeira_path.diff().fillna(0.0) if bandeira_path is not None \
        else pd.Series(0.0, index=cambio_path.index)

    rows = []
    for i in range(horizon):
        t = cambio_path.index[0] + pd.DateOffset(months=i)
        x = {"const": 1.0}
        for mo in range(1, 12):
            x[f"d{mo}"] = 1.0 if t.month == mo else 0.0
        x["ipca12_1"] = ipca12
        x["dln_brent_rl"] = float(dln_b.iloc[i]) if i < len(dln_b) else 0.0
        x["dln_cambio"] = float(dln_c.iloc[i]) if i < len(dln_c) else 0.0
        x["d_bandeira"] = float(db.iloc[i]) if i < len(db) else 0.0
        rows.append({"month": t, "v_admin": sum(p.get(k, 0.0) * v for k, v in x.items())})
    return pd.DataFrame(rows).set_index("month")["v_admin"]


def forecast_admin_quarterly(est: dict, df: pd.DataFrame, brent_path: pd.Series,
                             cambio_path: pd.Series, ipca12_path: pd.Series,
                             bandeira_path: pd.Series | None = None,
                             horizon: int = 12, start: str = "2020-03") -> pd.Series:
    """Projeção trimestral do IPCA administrado (composto da projeção mensal calibrada)."""
    mono = forecast_admin_calibrado(est, df, brent_path, cambio_path, ipca12_path,
                                    bandeira_path, horizon, start)
    q = mono.resample("QE").apply(
        lambda x: (np.prod(1 + np.asarray(x.dropna()) / 100.0) - 1) * 100
        if len(x.dropna()) >= 3 else np.nan)
    q = q.dropna()
    q.index = q.index.to_period("Q")
    return q
