"""Sistema agregado fiel ao BCB (RI dez/2021) com projeção e expectativas consistentes.

Equações:
  Phillips : πL = c + α1·πL_1 + (1−α1)·Eπ + α2t·imp_total_dev + α2e·imp_energia
                 + α3·dev_ppc + α4·gap_1 + α5·ElNiño + α6·LaNiña
  IS (bcb) : gap = β1·gap_1 + β2·(r̄−rreal) + β3·fisc_cc + β4·incert + β5·us_gap
  Expect   : Eπ_t = φ1·Eπ_{t-1} + φ2·Eπ_modelo + φ3·πL_{t-1}
  Taylor/UIP/admin: estimadas no estimate_all (usadas como no modelo atual).

A projeção condiciona Selic (Focus), câmbio (PPC), Brent, ONI (RONI), IC-Br (flat),
fiscal/us_gap/incerteza (flat). As expectativas consistentes (Eπ_modelo = π_{t+1} do
próprio sistema) são resolvidas por fixed-point.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from equacoes_bcb import _hp_cycle

PPC_AA = 1.0
META = 3.0
W_LIVRES = 0.76
NEUTRA = 5.0


class BcbSystem:
    def __init__(self, est: dict, q: pd.DataFrame):
        self.p_phi = est["phillips_bcb"]["params"]
        self.p_is = est["is_bcb"]["params"]
        self.p_expect = est["expect_bcb"]["params"]
        self.p_tay = est["taylor"]["params"]
        self.p_uip = est["uip"]["params"]
        self.p_adm = est["admin"]["params"]
        self.q = q

    def _sim(self, periods, sim, state, gap2, scenario, e_seq=None, shock_gap_pp=0.0,
             shock_cambio_pp=0.0):
        p, pi_, pe = self.p_phi, self.p_is, self.p_expect
        lastval = lambda c: float(self.q[c].dropna().iloc[-1]) if self.q[c].notna().any() else float("nan")
        cambio = lastval("cambio")
        brent = lastval("brent")
        ff = lastval("ff")
        pi_com = lastval("pi_com")
        oni = lastval("oni")
        us_gap = lastval("us_gap")
        incert = lastval("incert")
        fisc_cc = float(_hp_cycle(self.q["fiscal"]).iloc[-1])  # série cheia (HP precisa de amostra)
        meta_q = META / 4

        rows = []
        for i, period in enumerate(periods):
            e = float(e_seq[i]) if e_seq is not None else (
                pe.get("e_prev", 0) * state["e_prev"] + pe.get("pi_prev", 0) * state["pi_prev"])
            sc = scenario.loc[period] if scenario is not None and period in scenario.index else None
            if sc is not None:
                selic = float(sc["selic"])
                dln_c = float(sc["dln_cambio"])
                brent = float(sc["brent"]) if pd.notna(sc.get("brent", np.nan)) else brent
                oni = float(sc["oni"]) if pd.notna(sc.get("oni", np.nan)) else oni
            else:
                selic = (self.p_tay["const"] + self.p_tay["selic_1"] * state["selic"]
                         + self.p_tay["selic_2"] * state["selic_2"] + self.p_tay["dev_pi"] * (e - META))
                dln_c = self.p_uip.get("const", 0) + self.p_uip.get("diff_juros", 0) * (state["selic"] - ff)
            selic = 0.85 * state["selic"] + 0.15 * selic
            if shock_cambio_pp and i == 0:
                dln_c += shock_cambio_pp
            cambio = cambio * np.exp(dln_c / 100)
            if np.isfinite(brent) and brent > 0:
                dln_b = np.log(brent / state.get("_brent", brent)) * 100 if state.get("_brent") else 0.0
            else:
                dln_b = 0.0
            state["_brent"] = brent if np.isfinite(brent) else state.get("_brent", brent)

            imp_total = (pi_com + dln_c) - meta_q
            imp_energia = dln_b
            dev_ppc = dln_c - PPC_AA / 4
            rreal = state["selic"] - 4 * e
            gap = (pi_["gap_1"] * state["gap"]
                   + pi_["rreal_gap"] * (NEUTRA - rreal)
                   + pi_["fisc_cc"] * fisc_cc
                   + pi_["incert"] * incert
                   + pi_["us_gap"] * us_gap)
            if shock_gap_pp and i == 0:
                gap += shock_gap_pp

            pi_l = (p["pi_l_1"] * state["pi_l"] + p["e_pi_next"] * e
                    + p.get("imp_total", 0) * imp_total + p.get("imp_energia", 0) * imp_energia
                    + p["dev_ppc"] * dev_ppc + p["gap_1"] * state["gap"]
                    + p["elnino"] * max(oni, 0) + p["lanina"] * max(-oni, 0))
            pi_a = (self.p_adm["const"] + self.p_adm["pi_a_1"] * state["pi_a"]
                    + self.p_adm["pi_l_1"] * pi_l + self.p_adm["dln_cambio"] * dln_c)
            pi = W_LIVRES * pi_l + (1 - W_LIVRES) * pi_a

            rows.append({"period": str(period), "pi": pi, "pi_l": pi_l, "pi_a": pi_a,
                         "e_pi_next": e, "selic": selic, "gap": gap, "dln_cambio": dln_c})
            state["pi_l"], state["pi_a"], state["gap"], state["selic"] = pi_l, pi_a, gap, selic
            state["selic_2"] = state["selic"]
            state["e_prev"], state["pi_prev"] = e, pi_l
            gap2 = gap

        out = pd.DataFrame(rows)
        hist = sim["pi"].tolist()
        allp = hist + out["pi"].tolist()
        cum = (1 + pd.Series(allp) / 100).rolling(4).apply(np.prod, raw=True)
        out["pi4"] = ((cum - 1) * 100).iloc[len(hist):].reset_index(drop=True)
        return out

    def forecast(self, horizon: int = 12, scenario=None, expect_mode: str = "consistent",
                 expect_tol: float = 1e-3, expect_maxiter: int = 40,
                 shock_gap_pp: float = 0.0, shock_cambio_pp: float = 0.0) -> pd.DataFrame:
        q = self.q.copy()
        last_q = q.index[-1].to_period("Q")
        periods = pd.period_range(last_q + 1, periods=horizon, freq="Q")
        sim = q.iloc[max(0, q.index.get_loc(q.index[-1]) - 3):].copy()
        state = {k: float(sim[k].iloc[-1]) for k in ["pi_l", "pi_a", "gap", "selic", "e_pi_next"]}
        state.setdefault("selic_2", state["selic"])
        state["e_prev"] = state["e_pi_next"]
        state["pi_prev"] = state["pi_l"]
        gap2 = float(sim["gap"].iloc[-2]) if len(sim) > 1 else state["gap"]
        _shock_c = shock_cambio_pp

        def run(e_seq=None):
            return self._sim(periods, sim, dict(state), gap2, scenario, e_seq,
                             shock_gap_pp=shock_gap_pp, shock_cambio_pp=_shock_c)

        if expect_mode != "consistent":
            return run()
        pe = self.p_expect
        e_seq = list(run()["e_pi_next"])
        e_prev0 = state["e_pi_next"]
        for _ in range(expect_maxiter):
            out = run(e_seq)
            pi_all = out["pi"].tolist() + [META / 4]
            pil = out["pi_l"].tolist()
            e_new = []
            for i in range(len(e_seq)):
                eprev = e_seq[i - 1] if i > 0 else e_prev0
                e_new.append(pe.get("e_prev", 0) * eprev + pe.get("e_consistent", 0) * pi_all[i + 1]
                             + pe.get("pi_prev", 0) * pil[i])
            if max(abs(a - b) for a, b in zip(e_new, e_seq)) < expect_tol:
                e_seq = e_new
                break
            e_seq = e_new
        return run(e_seq)
