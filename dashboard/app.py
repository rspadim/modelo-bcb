"""Dashboard interativo da réplica do Modelo de Pequeno Porte do BCB.

Lê os artefatos gerados pelo pipeline (output/ e docs/figures/) e exibe
projeção, backtest, long horizon, modelo completo e setorização.

Rodar:
    streamlit run dashboard/app.py
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "modelo-agregado" / "output"
OUT_COMPLETO = ROOT / "modelo-completo" / "output"
FIG = ROOT / "docs" / "figures"

st.set_page_config(page_title="Modelo BCB — réplica do MPP", layout="wide", page_icon="🇧🇷")

st.title("🇧🇷 Modelo BCB — réplica do Modelo de Pequeno Porte")
st.caption("Reconstrução pública do modelo de projeção de inflação do Banco Central do Brasil. "
           "Dados point-in-time, equações estimadas, backtest e comparação com o cenário oficial.")

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["📈 Projeção", "🎯 Backtest", "🕐 Long horizon", "🧩 Modelo completo", "🗂 Setores"]
)


def _load(path: Path) -> pd.DataFrame | None:
    if path.exists():
        return pd.read_csv(path)
    return None


def _img(name: str, caption: str, width: int | None = None) -> None:
    p = FIG / name
    if p.exists():
        st.image(str(p), caption=caption, width=width, use_container_width=True)
    else:
        st.warning(f"Figura `{name}` ainda não foi gerada (rode `python scripts/make_figures.py`).")


# ---------------- Projeção ----------------
with tab1:
    st.subheader("Projeção de inflação vs cenário oficial (RPM jun/2026)")
    _img("fan_chart.png", "IPCA acumulado em 4 trimestres — modelo (leque 50/90%) vs cenário oficial.")
    _img("comparacao_trimestral.png", "Comparação por trimestre.")
    comp = _load(OUT / "comparacao_rpm.csv")
    if comp is not None:
        v = comp.dropna(subset=["pi4_modelo_cond", "rpm_ipca4"]).copy()
        st.dataframe(v[["period", "pi4_modelo_cond", "pi4_modelo_taylor", "rpm_ipca4"]].round(2),
                     use_container_width=True, hide_index=True)
        mae = (v["pi4_modelo_cond"] - v["rpm_ipca4"]).abs().mean()
        st.metric("MAE vs cenário oficial", f"{mae:.2f} p.p.", f"{len(v)} trimestres")

# ---------------- Backtest ----------------
with tab2:
    st.subheader("Backtest rolante por vintage (2019Q1–2026Q1)")
    _img("backtest_horizonte.png", "MAE do modelo vs benchmark naive por horizonte.")
    _img("backtest_serie.png", "Erros de previsão ao longo do tempo (p.p.).")
    bt = _load(OUT / "backtest.csv")
    if bt is not None:
        bt = bt.copy()
        bt["erro"] = bt["modelo"] - bt["realizado"]
        st.metric("MAE médio (todos horizontes)", f"{bt['erro'].abs().mean():.2f} p.p.",
                  f"{bt['vintage'].nunique()} vintages")
        mae_h = bt.groupby("horizon")["erro"].apply(lambda x: x.abs().mean())
        st.dataframe(mae_h.rename("MAE").round(3), use_container_width=True)

# ---------------- Long horizon ----------------
with tab3:
    st.subheader("Modelo vs realizado — projeção recursiva de longo prazo")
    _img("longhorizon.png", "Recursivo: re-estima a cada trimestre e projeta 1T e 4T à frente.")
    lh = _load(OUT / "longhorizon.csv")
    if lh is not None:
        st.dataframe(lh.round(2), use_container_width=True, hide_index=True)

# ---------------- Modelo completo ----------------
with tab4:
    st.subheader("Modelo completo (3 Phillips setoriais + estado-espaço)")
    _img("fan_chart_completo.png", "Versão desagregada vs cenário oficial.")
    _img("repasse_cambial.png", "Repasse cambial: choque de +10% USD/BRL por setor.")
    rp = _load(OUT_COMPLETO / "repasse_cambial.csv")
    if rp is not None:
        st.dataframe(rp.round(3), use_container_width=True, hide_index=True)

# ---------------- Setores ----------------
with tab5:
    st.subheader("Setorização da inflação livre (SIDRA)")
    _img("setorizacao.png", "Preços livres setorial vs oficial — correlação 0,98.")

st.divider()
st.caption("Fonte: BCB (RPM, SGS, Focus, SIDRA), IBGE, NOAA, FRED. "
           "Especificação em `docs/equacoes.md` · Validação em `docs/validacao.md`.")
