"""Gera todas as figuras da documentação com estilo unificado.

Lê os artefatos já produzidos pelos scripts de modelo (output/*.csv) e
recalcula o que é leve (base trimestral, hiato HP, modelo agregado, setores).
Grava em docs/figures/.

Uso:
    python scripts/make_figures.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "modelo-completo"))       # pacote src = modelo-completo/src
sys.path.insert(0, str(ROOT / "modelo-agregado" / "src"))  # módulos planos (data, equations, gap, system, rpm)

import data as agg_data          # noqa: E402
import equations                 # noqa: E402
import gap as agg_gap            # noqa: E402
import system as agg_system      # noqa: E402
import rpm as rpm_mod            # noqa: E402
from src import data as complete_data  # noqa: E402 (modelo-completo)
from src import sector as sector_mod   # noqa: E402 (modelo-completo)

FIGDIR = ROOT / "docs" / "figures"
FIGDIR.mkdir(exist_ok=True)

# ------------------------- estilo unificado -------------------------
BLUE = "#0b6fb5"
RED = "#c0392b"
GREEN = "#1e8449"
ORANGE = "#e67e22"
GRAY = "#7f8c8d"
META = "#111111"

plt.rcParams.update({
    "figure.facecolor": "white", "axes.facecolor": "white",
    "axes.grid": True, "grid.alpha": 0.25, "grid.linestyle": "-",
    "axes.spines.top": False, "axes.spines.right": False,
    "font.size": 10, "axes.titlesize": 12, "axes.titleweight": "bold",
    "legend.frameon": False, "lines.linewidth": 1.8,
})


def _save(fig, name: str) -> None:
    path = FIGDIR / name
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  {path.name}")


def _meta_lines(ax) -> None:
    ax.axhline(3.0, color=META, ls=":", lw=1)
    ax.axhspan(1.5, 4.5, color=GRAY, alpha=0.10)


# ------------------------- dados -------------------------
def _quarterly(vintage: str = "pt_2026Q2"):
    df = agg_data.load_snapshot(vintage)
    q = agg_data.build_quarterly(df)
    q = agg_gap.add_gap(q)
    return q.loc["2000Q1":]


def _fan(q, horizon=12):
    est = equations.estimate_all(q.loc["2002Q1":])
    model = agg_system.ModelSystem(est, q.loc["2002Q1":], {"w_livres": agg_data.W_LIVRES})
    last_q = q.index[-1].to_period("Q")
    nxt = last_q + 1
    cfg = rpm_mod.load()
    sp = rpm_mod.selic_path(cfg, str(nxt), str(nxt + horizon - 1))
    fc = model.forecast(horizon=horizon, selic_path=sp)
    fan = agg_system.monte_carlo(model, horizon=horizon, n_draws=1500, seed=42)
    rpm_path = rpm_mod.rpm_ipca_path(cfg)
    return fc, fan, rpm_path, est


# ------------------------- figuras -------------------------
def fig_serie(q):
    print("1/11 serie_ipca")
    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.plot(q.index, q["pi4"], color=BLUE, lw=2, label="IPCA acumulado em 4 trimestres")
    ax.bar(q.index, q["pi"], color=BLUE, alpha=0.18, width=80, label="IPCA trimestral")
    _meta_lines(ax)
    ax.set_title("Inflação brasileira (2000–2026)")
    ax.set_ylabel("% a.a.")
    ax.legend(loc="upper left", fontsize=9)
    _save(fig, "serie_ipca.png")


def fig_componentes(q, qc):
    print("2/11 componentes")
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4.2))
    a1.plot(q.index, q["pi4_l"], color=BLUE, lw=2, label="Preços livres")
    a1.plot(q.index, q["pi4_a"], color=RED, lw=2, label="Administrados")
    _meta_lines(a1)
    a1.set_title("Livres vs Administrados (acum. 4T)")
    a1.set_ylabel("% a.a.")
    a1.legend(fontsize=9)
    s = qc.loc["2020Q1":]
    a2.plot(s.index, s["servicos"], color=BLUE, lw=1.6, label="Serviços")
    a2.plot(s.index, s["industriais"], color=GREEN, lw=1.6, label="Bens industriais")
    a2.plot(s.index, s["alimentacao"], color=ORANGE, lw=1.6, label="Alimentação no domicílio")
    a2.set_title("Setores livres (var. trimestral, %)")
    a2.set_ylabel("% trimestre")
    a2.legend(fontsize=8)
    _save(fig, "componentes.png")


def fig_hiato(q, qc):
    print("3/11 hiato")
    fig, ax = plt.subplots(figsize=(11, 4))
    qg = q.loc["2003Q1":]
    ax.plot(qg.index, qg["gap"], color=BLUE, lw=2, label="Filtro HP (IBC-Br)")
    ax.axhline(0, color=META, lw=1)
    ax.set_title("Hiato do produto")
    ax.set_ylabel("%")
    ax.legend(loc="upper left", fontsize=9)
    _save(fig, "hiato.png")


def fig_equacoes(q):
    print("4/11 equacoes")
    est = equations.estimate_all(q.loc["2002Q1":])
    panels = {
        "phillips": ["pi_l_1", "e_pi_next", "gap_1", "dln_cambio", "pi_com", "oni"],
        "is": ["gap_1", "gap_2", "rreal_1", "dln_cambio", "fiscal"],
        "taylor": ["selic_1", "selic_2", "dev_pi"],
    }
    titles = {"phillips": "Curva de Phillips (livres)", "is": "Curva IS", "taylor": "Regra de Taylor"}
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    for ax, (key, cols) in zip(axes, panels.items()):
        r = est[key]
        names = [c.replace("_", " ").title() for c in cols]
        vals = [r["params"][c] for c in cols]
        errs = [1.96 * r["stderr"][c] for c in cols]
        colors = [BLUE if r["pvalues"][c] < 0.05 else GRAY for c in cols]
        ax.barh(range(len(cols)), vals, xerr=errs, color=colors, alpha=0.85, height=0.55)
        ax.set_yticks(range(len(cols)), labels=names)
        ax.set_title(titles[key])
        ax.axvline(0, color=META, lw=0.8)
        ax.set_xlabel("Coeficiente (± 1,96 se)")
    fig.suptitle("Coeficientes estimados (OLS, 2002–2026) — azul = significativo a 5%", fontweight="bold")
    _save(fig, "equacoes.png")


def fig_fan(q):
    print("5/11 fan_chart")
    fc, fan, rpm_path, _ = _fan(q)
    periods = fc["period"]
    pidx = pd.PeriodIndex(periods, freq="Q")
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.plot(pidx.astype(str), rpm_path.reindex(pidx)["rpm_ipca4"], "o-", color=RED, lw=2.5,
            label="Cenário oficial (RPM jun/2026)")
    ax.plot(pidx.astype(str), fc["pi4"].values, "o-", color=BLUE, lw=2.5, label="Modelo (Selic condicionada)")
    ax.fill_between(pidx.astype(str), fan["25"], fan["75"], color=BLUE, alpha=0.25, label="Leque 50%")
    ax.fill_between(pidx.astype(str), fan["5"], fan["95"], color=BLUE, alpha=0.10, label="Leque 90%")
    _meta_lines(ax)
    ax.set_title("Projeção de inflação — modelo agregado vs cenário oficial do BCB")
    ax.set_ylabel("IPCA acumulado em 4 trimestres (% a.a.)")
    ax.legend(loc="upper right", fontsize=9)
    ax.tick_params(axis="x", rotation=45)
    _save(fig, "fan_chart.png")


def fig_comparacao_trimestral(q):
    print("6/11 comparacao_trimestral")
    fc, fan, rpm_path, _ = _fan(q)
    comp = fc.set_index("period")[["pi4"]].copy()
    comp.index = pd.PeriodIndex(comp.index, freq="Q")
    comp = comp.join(rpm_path)
    comp = comp.dropna(subset=["pi4", "rpm_ipca4"])
    x = np.arange(len(comp))
    w = 0.38
    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.bar(x - w / 2, comp["pi4"], w, color=BLUE, label="Modelo")
    ax.bar(x + w / 2, comp["rpm_ipca4"], w, color=RED, alpha=0.85, label="Cenário oficial (RPM)")
    ax.set_xticks(x, labels=[str(p) for p in comp.index], rotation=45, fontsize=9)
    ax.set_title("Modelo vs cenário oficial — por trimestre (acum. 4T)")
    ax.set_ylabel("% a.a.")
    ax.legend()
    _save(fig, "comparacao_trimestral.png")


def fig_backtest_horizonte():
    print("7/11 backtest_horizonte")
    res = pd.read_csv(ROOT / "modelo-agregado" / "output" / "backtest.csv")
    full = pd.read_parquet(ROOT / "downloader" / "data" / "processed" / "series.parquet")
    m = full[(full["source"] == "sgs") & (full["series"] == "ipca")][["ref_date", "value"]].dropna()
    m = m.set_index("ref_date")["value"]
    def comp(x):
        x = x.dropna()
        return (np.prod(1 + x / 100.0) - 1) * 100 if len(x) >= 3 else np.nan
    q4 = ((1 + m.resample("QE").apply(comp) / 100).rolling(4).apply(np.prod, raw=True) - 1) * 100
    q4.index = q4.index.to_period("Q")
    q4 = q4.dropna()
    res["vint_p"] = pd.PeriodIndex(res["vintage"].str[3:], freq="Q")
    res["last_q"] = res["vint_p"] - 1
    res["naive"] = res["last_q"].map(lambda p: q4.get(p, np.nan))
    res["e_m"] = (res["modelo"] - res["realizado"]).abs()
    res["e_n"] = (res["naive"] - res["realizado"]).abs()
    g = res.groupby("horizon").agg(mae_modelo=("e_m", "mean"), mae_naive=("e_n", "mean"))
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(g.index, g["mae_naive"], "s--", color=GRAY, label="Naive (persistência)")
    ax.plot(g.index, g["mae_modelo"], "o-", color=BLUE, lw=2.5, label="Modelo")
    ax.set_xticks(g.index)
    ax.set_xlabel("Horizonte (trimestres à frente)")
    ax.set_ylabel("MAE (p.p.)")
    ax.set_title("Backtest por vintage (2019Q1–2026Q1) — MAE do modelo vs benchmark naive")
    ax.legend()
    _save(fig, "backtest_horizonte.png")


def fig_backtest_serie():
    print("8/11 backtest_serie")
    res = pd.read_csv(ROOT / "modelo-agregado" / "output" / "backtest.csv")
    res["t"] = pd.PeriodIndex(res["target"], freq="Q").to_timestamp(how="end")
    res["erro"] = res["modelo"] - res["realizado"]
    h1 = res[res["horizon"] == 1].set_index("t")["erro"]
    h4 = res[res["horizon"] == 4].set_index("t")["erro"]
    fig, ax = plt.subplots(figsize=(11, 4.2))
    ax.plot(h1.index, h1, "o-", color=BLUE, ms=4, label="Erro h=1 (modelo − realizado)")
    ax.plot(h4.index, h4, "s-", color=RED, ms=4, label="Erro h=4")
    ax.axhline(0, color=META, lw=1)
    ax.set_title("Erros de previsão ao longo do tempo (p.p.)")
    ax.set_ylabel("p.p.")
    ax.legend(fontsize=9)
    _save(fig, "backtest_serie.png")


def fig_longhorizon():
    print("9/11 longhorizon")
    lh = pd.read_csv(ROOT / "modelo-agregado" / "output" / "longhorizon.csv")
    x = pd.PeriodIndex(lh["vintage"].astype(str), freq="Q").to_timestamp(how="end")
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(x, lh["real_4q"], "k-", lw=2, label="Realizado (acum. 4T)")
    ax.plot(x, lh["prev_1q"], "o-", color=BLUE, ms=3, lw=1.2, label="Modelo — 1T à frente")
    ax.plot(x, lh["prev_4q"], "s--", color=RED, ms=3, lw=1.2, label="Modelo — 4T à frente (fora de amostra)")
    _meta_lines(ax)
    ax.set_title("Modelo vs realizado — projeção recursiva (2011–2025)")
    ax.set_ylabel("IPCA acumulado em 4 trimestres (% a.a.)")
    ax.legend(loc="upper left", fontsize=9)
    _save(fig, "longhorizon.png")


def fig_setorizacao():
    print("10/11 setorizacao")
    df = pd.read_parquet(ROOT / "downloader" / "data" / "snapshots" / "pt_2026Q2" / "data.parquet")
    sub = df[(df["source"] == "sidra") & (df["variable"].isin([63, 66]))]
    v, w = sector_mod.build_sectoral_monthly(sub)
    sgs = df[df["source"] == "sgs"][["ref_date", "series", "value"]]
    sgs = sgs[sgs["series"].isin(["ipca_livres", "ipca_admin"])]
    sgs = sgs.pivot(index="ref_date", columns="series", values="value")
    j = pd.concat([v["livres"], sgs["ipca_livres"]], axis=1, join="inner").dropna()
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4.2))
    a1.plot(j.index, j["livres"], color=BLUE, lw=1.6, label="Setorial (SIDRA, ponderado)")
    a1.plot(j.index, j["ipca_livres"], color=RED, lw=1.6, alpha=0.85, label="Oficial (SGS)")
    a1.set_title("Preços livres: setorial vs oficial (mensal, %)")
    a1.set_ylabel("%")
    a1.legend(fontsize=8)
    corr = j["livres"].corr(j["ipca_livres"])
    a2.scatter(j["ipca_livres"], j["livres"], s=14, color=BLUE, alpha=0.6)
    lim = [min(j.min().min(), -1), max(j.max().max(), 1)]
    a2.plot(lim, lim, "k--", lw=1)
    a2.set_xlabel("Oficial (SGS)")
    a2.set_ylabel("Setorial (SIDRA)")
    a2.set_title(f"Correlação = {corr:.3f}")
    _save(fig, "setorizacao.png")


def fig_repasse():
    print("11/11 repasse_cambial")
    rp = pd.read_csv(ROOT / "modelo-completo" / "output" / "repasse_cambial.csv")
    r0 = rp.iloc[0]
    labels = ["Serviços", "Bens industriais", "Alimentação"]
    vals = [r0["dservicos"], r0["dindustriais"], r0["dalimentacao"]]
    fig, ax = plt.subplots(figsize=(9, 4.2))
    bars = ax.bar(labels, vals, color=[BLUE, GREEN, ORANGE], alpha=0.85)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.02, f"{v:+.2f}", ha="center", fontsize=9)
    ax.axhline(0, color=META, lw=1)
    ax.set_title("Repasse cambial: choque de +10% USD/BRL (impacto no 1º trimestre, p.p.)")
    ax.set_ylabel("p.p. (variação do setor)")
    ax.text(0.99, 0.02, "Benchmark BCB (anexo B9): admin +1,8 · livres +0,7 · IPCA +1,0 p.p. em 4T.\n"
            "Sinal negativo na réplica = limitação da amostra OLS (ver docs/validacao.md).",
            transform=ax.transAxes, ha="right", va="bottom", fontsize=7.5, color=GRAY)
    _save(fig, "repasse_cambial.png")


def main() -> None:
    print("Gerando figuras ->", FIGDIR)
    q = _quarterly()
    df = pd.read_parquet(ROOT / "downloader" / "data" / "snapshots" / "pt_2026Q2" / "data.parquet")
    qc = complete_data.build_complete_quarterly(df)
    fig_serie(q)
    fig_componentes(q, qc)
    fig_hiato(q, qc)
    fig_equacoes(q)
    fig_fan(q)
    fig_comparacao_trimestral(q)
    fig_backtest_horizonte()
    fig_backtest_serie()
    fig_longhorizon()
    fig_setorizacao()
    fig_repasse()
    print("Concluído.")


if __name__ == "__main__":
    main()
