"""Setorização da inflação livre a partir dos subitens do IPCA (SIDRA 7060).

Classifica cada subitem como administrado / serviços / bens industriais /
alimentação no domicílio e agrega com pesos mensais (v=66). A soma ponderada
setorial reproduz as séries oficiais de livres (corr ~0,98).
"""
from __future__ import annotations

import re

import pandas as pd

SETORES = ["servicos", "industriais", "alimentacao", "admin"]

_LEAF_RE = re.compile(r"^\d{7,}\.")


def _hier_code(item_name: str) -> str:
    m = re.match(r"^(\d+)\.", str(item_name))
    return m.group(1) if m else ""


ADMIN_KEY = [
    "energia elétrica", "gás de botijão", "gás encanado", "gasolina", "etanol",
    "óleo diesel", "ônibus", "metrô", "trem", "táxi", "transporte escolar",
    "transporte urbano", "intermunicipal", "interestadual", "plano de saúde",
    "farmacêutico", "medicamento", "correio", "telefone fixo", "telefone móvel",
    "telefonia", "telefônico", "internet", "tv por assinatura", "comunicação",
    "água e esgoto", "taxa de água", "emplacamento", "licença", "cigarro",
    "fumo", "conselho de classe", "esgoto", "tarifa", "energia elétrica residencial",
]
SERVICOS_KEY = [
    "serviço", "serviços", "conserto", "manutenção", "reparação", "reforma",
    "aluguel", "condomínio", "mudança", "médico", "dentista", "hospitalização",
    "exame de laboratório", "passagem aérea", "estacionamento", "pedágio",
    "seguro", "clube", "recreação", "restaurante", "refeição", "lanche",
    "cafezinho", "empregado doméstico", "costureira", "depilação", "cartório",
    "despachante", "serviço bancário", "creche", "curso", "educação",
    "mensalidade", "ensino", "escola", "faculdade", "universidade",
    "cabeleireiro", "lavanderia", "manicure", "bares", "alimentação fora",
    "leitura", "jornal diário", "reforma de estofado",
]


def _classify(item_name: str):
    n = item_name.lower()
    for kw in ADMIN_KEY:
        if kw in n:
            return "admin"
    for kw in SERVICOS_KEY:
        if kw in n:
            return "servicos"
    return None


def _classify_by_code(item_name: str) -> str:
    r = _classify(item_name)
    if r:
        return r
    grupo = _hier_code(item_name)[:2]
    if grupo == "11":
        return "alimentacao"
    if grupo == "12":
        return "servicos"
    if grupo in {"31", "32", "41", "42", "43", "44", "63"}:
        return "industriais"
    return "servicos"


def build_sectoral_monthly(sub: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(vars, pesos) mensais por setor, a partir dos subitens-folha do SIDRA 7060."""
    sub = sub.copy()
    sub["ref_date"] = pd.to_datetime(sub["ref_date"])
    sub = sub[sub["item_name"].astype(str).str.match(_LEAF_RE)].copy()
    sub["setor"] = sub["item_name"].map(_classify_by_code)

    wide = sub.pivot_table(index=["ref_date", "item_code"], columns="variable",
                           values="value").reset_index()
    wide.columns = ["ref_date", "item_code", "v", "w"]
    wide = wide.dropna(subset=["v"])
    meta = sub[["item_code", "setor"]].drop_duplicates("item_code")
    wide = wide.merge(meta, on="item_code")
    wide["contrib"] = wide["v"] * wide["w"]

    g = wide.groupby(["ref_date", "setor"]).agg(soma=("contrib", "sum"),
                                                peso=("w", "sum")).reset_index()
    g["var"] = g["soma"] / g["peso"]
    vars_df = g.pivot(index="ref_date", columns="setor", values="var").reindex(columns=SETORES)
    weights_df = g.pivot(index="ref_date", columns="setor", values="peso").reindex(columns=SETORES)
    livres_w = weights_df[["servicos", "industriais", "alimentacao"]].sum(axis=1)
    vars_df["livres"] = (vars_df[["servicos", "industriais", "alimentacao"]] *
                         weights_df[["servicos", "industriais", "alimentacao"]]).sum(axis=1) / livres_w
    weights_df["livres"] = livres_w
    return vars_df, weights_df


def add_sectoral_quarterly(q: pd.DataFrame, df: pd.DataFrame) -> pd.DataFrame:
    """Adiciona as séries setoriais trimestrais (servicos/industriais/alimentacao + pesos)."""
    sub = df[(df["source"] == "sidra") & (df["variable"].isin([63, 66]))]
    v, w = build_sectoral_monthly(sub)

    def to_q(s):
        return s.resample("QE").apply(
            lambda x: (pd.Series(1 + x.dropna() / 100).prod() - 1) * 100
            if len(x.dropna()) >= 3 else float("nan"))

    out = q.copy()
    for c in ["servicos", "industriais", "alimentacao"]:
        out[c] = to_q(v[c]).reindex(out.index)
        out[f"w_{c}"] = w[c].resample("QE").mean().reindex(out.index)
    return out
