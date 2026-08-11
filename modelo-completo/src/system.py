"""Sistema completo: 3 Phillips setoriais + IS + Taylor + UIP + admin + identidade."""
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

    def forecast(self, horizon: int = 12, selic_path: pd.Series | None = None,
                 shock_cambio_pp: float = 0.0) -> pd.DataFrame:
        q = self.q.copy()
        last_q = q.index[-1].to_period("Q")
        periods = pd.period_range(last_q + 1, periods=horizon, freq="Q")
        sim = q.iloc[max(0, q.index.get_loc(q.index[-1]) - 3):].copy()

        p = {s: self.est["phillips"][s]["params"] for s in sector.SETORES if s != "admin"}
        p_is = self.est["is"]["params"]
        p_tay = self.est["taylor"]["params"]
        p_uip = self.est["uip"]["params"]
        p_adm = self.est["admin"]["params"]
        meta = 3.0

        state = {k: float(sim[k].iloc[-1]) for k in
                 ["servicos", "industriais", "alimentacao", "pi_a", "gap", "e_pi_next", "selic"]}
        gap2 = float(sim["gap"].iloc[-2]) if len(sim) > 1 else state["gap"]
        selic2 = float(sim["selic"].iloc[-2]) if len(sim) > 1 else state["selic"]
        # exógenos: usa o último valor não-NaN disponível (ex.: IC-Br cessa antes do fim)
        lastval = lambda c: float(sim[c].dropna().iloc[-1]) if sim[c].notna().any() else float("nan")
        cambio = lastval("cambio")
        ff = lastval("ff")
        fiscal = lastval("fiscal")
        pi_com = lastval("pi_com")
        oni = lastval("oni")

        rows = []
        for i, period in enumerate(periods):
            e = 0.8 * state["e_pi_next"] + 0.2 * (meta / 4)
            state["e_pi_next"] = e

            if selic_path is not None and period in selic_path.index:
                selic = float(selic_path.loc[period])
            else:
                selic = (p_tay["const"] + p_tay["selic_1"] * state["selic"]
                         + p_tay["selic_2"] * selic2 + p_tay["dev_pi"] * (e - meta))
            selic = 0.85 * state["selic"] + 0.15 * selic

            dln_c = p_uip.get("const", 0) + p_uip.get("diff_juros", 0) * (state["selic"] - ff)
            if shock_cambio_pp and i == 0:
                dln_c += shock_cambio_pp  # depreciação de nível de 10% no 1º trimestre
            cambio = cambio * np.exp(dln_c / 100)

            rreal = state["selic"] - 4 * e
            gap = (p_is["const"] + p_is["gap_1"] * state["gap"] + p_is["gap_2"] * gap2
                   + p_is["rreal_1"] * rreal + p_is["dln_cambio"] * dln_c + p_is["fiscal"] * fiscal)

            sec = {}
            for s in ["servicos", "industriais", "alimentacao"]:
                pp = p[s]
                sec[s] = (pp["const"] + pp["pi_1"] * state[s] + pp["e_pi_next"] * e
                          + pp["gap_1"] * state["gap"] + pp["dln_cambio"] * dln_c
                          + pp["pi_com"] * pi_com + pp["oni"] * oni)

            pi_l = sec["servicos"] * self.w["servicos"] / self.w_livres \
                + sec["industriais"] * self.w["industriais"] / self.w_livres \
                + sec["alimentacao"] * self.w["alimentacao"] / self.w_livres
            pi_a = (p_adm["const"] + p_adm["pi_a_1"] * state["pi_a"]
                    + p_adm["pi_l_1"] * pi_l + p_adm["dln_cambio"] * dln_c)
            pi = self.w_livres * pi_l + self.w["admin"] * pi_a

            rows.append({"period": str(period), "pi": pi, "pi_l": pi_l, "pi_a": pi_a,
                         "servicos": sec["servicos"], "industriais": sec["industriais"],
                         "alimentacao": sec["alimentacao"], "selic": selic, "gap": gap,
                         "dln_cambio": dln_c, "e_pi_next": e})

            state["servicos"], state["industriais"], state["alimentacao"] = sec.values()
            state["pi_a"], state["gap"], state["selic"] = pi_a, gap, selic
            gap2 = state["gap"]

        out = pd.DataFrame(rows)
        pi_hist = sim["pi"].tolist()
        all_pi = pi_hist + out["pi"].tolist()
        cum = (1 + pd.Series(all_pi) / 100).rolling(4).apply(np.prod, raw=True)
        out["pi4"] = ((cum - 1) * 100).iloc[len(pi_hist):].reset_index(drop=True)
        return out
