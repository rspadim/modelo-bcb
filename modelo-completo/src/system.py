"""Sistema completo: 3 Phillips setoriais + IS + Taylor + UIP + admin + identidade.

Expectativas: modo "hybrid" (convergência ad-hoc para a meta) ou "consistent"
(fixed-point: itera o sistema até E_t[pi_{t+1}] = pi_{t+1} projetado).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import sector


class CompleteSystem:
    def __init__(self, est: dict, q: pd.DataFrame, cfg: dict):
        self.est = est
        self.q = q
        self.cfg = cfg
        # pesos setoriais (média da amostra disponível) — em fração (0..1)
        w = q[["w_servicos", "w_industriais", "w_alimentacao", "w_admin"]].mean() / 100.0
        self.w = {"servicos": float(w["w_servicos"]), "industriais": float(w["w_industriais"]),
                  "alimentacao": float(w["w_alimentacao"]), "admin": float(w["w_admin"])}
        self.w_livres = self.w["servicos"] + self.w["industriais"] + self.w["alimentacao"]

    def _simulate(self, periods, sim, state, gap2, selic2, meta, neutra, scenario,
                  selic_path, shock_cambio_pp, e_seq=None, shock_gap_pp=0.0,
                  admin_path=None):
        p = {s: self.est["phillips"][s]["params"] for s in sector.SETORES if s != "admin"}
        p_is = self.est["is"]["params"]
        p_tay = self.est["taylor"]["params"]
        p_uip = self.est["uip"]["params"]
        p_adm = self.est["admin"]["params"]
        ppc_q = 0.25  # % por trimestre (PPC ~1% a.a.), desvio do câmbio

        lastval = lambda c: float(sim[c].dropna().iloc[-1]) if sim[c].notna().any() else float("nan")
        cambio = lastval("cambio")
        ff = lastval("ff")
        fiscal = lastval("fiscal")
        pi_com = lastval("pi_com")
        oni = lastval("oni")
        brent = lastval("brent") if "brent" in sim.columns and sim["brent"].notna().any() else float("nan")
        state["_brent"] = brent  # nível inicial do Brent (para o repasse no 1º período)

        rows = []
        for i, period in enumerate(periods):
            if e_seq is not None:
                e = float(e_seq[i])
            else:
                e = 0.8 * state["e_pi_next"] + 0.2 * (meta / 4)
            state["e_pi_next"] = e

            if scenario is not None and period in scenario.index:
                sc = scenario.loc[period]
                selic = float(sc["selic"]) if pd.notna(sc.get("selic", np.nan)) else float("nan")
                dln_c = float(sc["dln_cambio"]) if pd.notna(sc.get("dln_cambio", np.nan)) else float("nan")
                if "brent" in scenario.columns and pd.notna(sc.get("brent", np.nan)):
                    brent = float(sc["brent"])
                if "oni" in scenario.columns and pd.notna(sc.get("oni", np.nan)):
                    oni = float(sc["oni"])
            elif selic_path is not None and period in selic_path.index:
                selic = float(selic_path.loc[period])
                dln_c = p_uip.get("const", 0) + p_uip.get("diff_juros", 0) * (state["selic"] - ff)
            else:
                selic = (p_tay["const"] + p_tay["selic_1"] * state["selic"]
                         + p_tay["selic_2"] * selic2 + p_tay["dev_pi"] * (e - meta))
                dln_c = p_uip.get("const", 0) + p_uip.get("diff_juros", 0) * (state["selic"] - ff)
            if not np.isfinite(selic):
                selic = p_tay["const"] + p_tay["selic_1"] * state["selic"] \
                    + p_tay["selic_2"] * selic2 + p_tay["dev_pi"] * (e - meta)
            if not np.isfinite(dln_c):
                dln_c = 0.0
            selic = 0.85 * state["selic"] + 0.15 * selic

            if shock_cambio_pp and i == 0:
                dln_c += shock_cambio_pp  # depreciação de nível de 10% no 1º trimestre
            cambio = cambio * np.exp(dln_c / 100)
            if np.isfinite(brent) and brent > 0:
                dln_brent = np.log(brent / state.get("_brent", brent)) * 100 if state.get("_brent") else 0.0
            else:
                dln_brent = 0.0
            state["_brent"] = brent if np.isfinite(brent) else state.get("_brent", brent)

            rreal = state["selic"] - 4 * e
            gap = (p_is["const"] + p_is["gap_1"] * state["gap"] + p_is["gap_2"] * gap2
                   + p_is["rreal_1"] * rreal + p_is["dln_cambio"] * dln_c + p_is["fiscal"] * fiscal)
            if shock_gap_pp and i == 0:
                gap += shock_gap_pp

            sec = {}
            dev_ppc = dln_c - ppc_q  # câmbio como desvio da PPC (como no BCB)
            for s in ["servicos", "industriais", "alimentacao"]:
                pp = p[s]
                sec[s] = (pp["const"] + pp["pi_1"] * state[s] + pp["e_pi_next"] * e
                          + pp["gap_1"] * state["gap"] + pp.get("dev_ppc", pp.get("dln_cambio", 0)) * dev_ppc
                          + pp["pi_com"] * pi_com + pp["oni"] * oni)

            pi_l = sec["servicos"] * self.w["servicos"] / self.w_livres \
                + sec["industriais"] * self.w["industriais"] / self.w_livres \
                + sec["alimentacao"] * self.w["alimentacao"] / self.w_livres
            if admin_path is not None and period in admin_path.index:
                pi_a = float(admin_path.loc[period])
            else:
                pi_a = (p_adm["const"] + p_adm["pi_a_1"] * state["pi_a"]
                        + p_adm["pi_l_1"] * pi_l + p_adm.get("dln_cambio", 0) * dln_c)
                if "dln_brent" in p_adm and np.isfinite(dln_brent):
                    pi_a += p_adm["dln_brent"] * dln_brent
            pi = self.w_livres * pi_l + self.w["admin"] * pi_a

            rows.append({"period": str(period), "pi": pi, "pi_l": pi_l, "pi_a": pi_a,
                         "servicos": sec["servicos"], "industriais": sec["industriais"],
                         "alimentacao": sec["alimentacao"], "selic": selic, "gap": gap,
                         "dln_cambio": dln_c, "e_pi_next": e, "brent": brent, "oni": oni})

            state["servicos"], state["industriais"], state["alimentacao"] = sec.values()
            state["pi_a"], state["gap"], state["selic"] = pi_a, gap, selic
            gap2 = state["gap"]

        out = pd.DataFrame(rows)
        pi_hist = sim["pi"].tolist()
        all_pi = pi_hist + out["pi"].tolist()
        cum = (1 + pd.Series(all_pi) / 100).rolling(4).apply(np.prod, raw=True)
        out["pi4"] = ((cum - 1) * 100).iloc[len(pi_hist):].reset_index(drop=True)
        return out

    def _base_state(self):
        q = self.q.copy()
        sim = q.iloc[max(0, q.index.get_loc(q.index[-1]) - 3):].copy()
        state = {k: float(sim[k].iloc[-1]) for k in
                 ["servicos", "industriais", "alimentacao", "pi_a", "gap", "e_pi_next", "selic"]}
        gap2 = float(sim["gap"].iloc[-2]) if len(sim) > 1 else state["gap"]
        selic2 = float(sim["selic"].iloc[-2]) if len(sim) > 1 else state["selic"]
        return sim, state, gap2, selic2

    def forecast(self, horizon: int = 12, selic_path: pd.Series | None = None,
                 shock_cambio_pp: float = 0.0, scenario: pd.DataFrame | None = None,
                 expect_mode: str = "hybrid", expect_tol: float = 1e-3,
                 expect_maxiter: int = 40, shock_gap_pp: float = 0.0,
                 admin_path: pd.Series | None = None) -> pd.DataFrame:
        q = self.q.copy()
        last_q = q.index[-1].to_period("Q")
        periods = pd.period_range(last_q + 1, periods=horizon, freq="Q")
        meta = 3.0
        neutra = 5.0
        if scenario is not None and "juro_real_neutra" in scenario.columns:
            neutra = float(scenario["juro_real_neutra"].iloc[0])

        sim, state0, gap20, selic20 = self._base_state()

        def run(e_seq=None):
            return self._simulate(periods, sim, dict(state0), gap20, selic20, meta, neutra,
                                  scenario, selic_path, shock_cambio_pp, e_seq=e_seq,
                                  shock_gap_pp=shock_gap_pp, admin_path=admin_path)

        if expect_mode != "consistent":
            return run()

        # fixed-point: E_t[pi_{t+1}] = pi_{t+1} projetado pelo próprio modelo
        e_seq = list(run()["e_pi_next"])  # semente = trajetória híbrida
        for _ in range(expect_maxiter):
            out = run(e_seq)
            nxt = out["pi"].shift(-1).tolist()
            nxt[-1] = meta / 4  # ancoragem terminal na meta
            e_new = [float(v) for v in nxt]
            if max(abs(a - b) for a, b in zip(e_new, e_seq)) < expect_tol:
                e_seq = e_new
                break
            e_seq = e_new
        return run(e_seq)
