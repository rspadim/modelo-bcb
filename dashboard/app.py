"""Dashboard interativo do modelo integrado (réplica do MPP do BCB).

Lê os artefatos gerados por `run_integrado.py`, `backtest.py`, `longhorizon.py` e
`decomposicao.py` em modelo-integrado/output e exibe projeção, IRFs, backtest,
long horizon e decomposição.

Rodar:
    streamlit run dashboard/app.py
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "modelo-integrado" / "output"

st.set_page_config(page_title="Modelo BCB — réplica do MPP (integrado)", layout="wide", page_icon="🇧🇷")

st.title("🇧🇷 Modelo BCB — réplica do Modelo de Pequeno Porte (integrado)")
st.caption("Modelo único: estimação bayesiana conjunta (hiato + juro neutra latentes) + "
           "Phillips/IS/expectativas + administrados. Ver `docs/status.md`.")

tab1, tab2, tab3, tab4 = st.tabs(
    ["📈 Projeção", "🎯 Backtest", "🕐 Long horizon", "🧩 IRFs & Decomposição"]
)


def _load(name: str) -> pd.DataFrame | None:
    p = OUT / name
    return pd.read_csv(p) if p.exists() else None


# ---------------- Projeção ----------------
with tab1:
    st.subheader("Projeção de inflação vs cenário oficial (RPM jun/2026)")
    pr = _load("projecao_integrada.csv")
    if pr is not None:
        v = pr.dropna(subset=["pi4", "rpm_ipca4"]).copy()
        mae = (v["pi4"] - v["rpm_ipca4"]).abs().mean()
        st.metric("MAE vs cenário oficial", f"{mae:.2f} p.p.", f"{len(v)} trimestres")
        st.line_chart(v.set_index("period")[["pi4", "rpm_ipca4"]])
        st.dataframe(v[["period", "pi4", "pi_l", "pi_a", "rpm_ipca4"]].round(2),
                     use_container_width=True, hide_index=True)

# ---------------- Backtest ----------------
with tab2:
    st.subheader("Backtest rolante por vintage (2019Q1–2026Q1, point-in-time)")
    bt = _load("backtest_integrado.csv")
    if bt is not None:
        bt = bt.dropna(subset=["realizado"]).copy()
        bt["erro"] = bt["modelo"] - bt["realizado"]
        st.metric("MAE médio", f"{bt['erro'].abs().mean():.2f} p.p.",
                  f"{bt['vintage'].nunique()} vintages")
        mae_h = bt.groupby("horizon")["erro"].apply(lambda x: x.abs().mean()).round(3)
        st.dataframe(mae_h.rename("MAE por horizonte"), use_container_width=True)

# ---------------- Long horizon ----------------
with tab3:
    st.subheader("Long horizon (recursivo) — MAE 1T e 4T à frente")
    lh = _load("backtest_integrado.csv")
    if lh is not None:
        lh = lh.dropna(subset=["realizado"])
        for h in [1, 4]:
            d = lh[lh["horizon"] == h]
            if len(d):
                st.metric(f"MAE {h}T à frente", f"{(d['modelo'] - d['realizado']).abs().mean():.2f} p.p.",
                          f"{len(d)} vintages")

# ---------------- IRFs & Decomposição ----------------
with tab4:
    st.subheader("IRFs do sistema integrado vs RI dez/2021")
    irf = _load("irfs_integradas.csv")
    if irf is not None:
        st.dataframe(irf.round(3), use_container_width=True, hide_index=True)
        st.caption("RI: demanda −1 p.p. → −0,45 p.p. em 4T · câmbio +10% → admin ≈ +1,8 p.p.")
    st.subheader("Decomposição de inflação 2024 (vs ofício 374)")
    dec = _load("decomposicao_2024_integrada.csv")
    if dec is not None:
        st.dataframe(dec.round(3), use_container_width=True)

st.divider()
st.caption("Fonte: BCB (RPM, SGS, Focus, SIDRA), IBGE, NOAA, FRED. "
           "Status em `docs/status.md` · Validação em `docs/validacao.md`.")
