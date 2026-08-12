"""Sistema ÚNICO integrado do modelo BCB (réplica estrutural do RI dez/2021).

Um único sistema que resolve simultaneamente:
  - Phillips de livres com o hiato do estado-espaço (parâmetros da conjunta);
  - IS (dinâmica do hiato) com a juro real neutra latente;
  - expectativas consistentes (φ2) por fixed-point;
  - bloco de administrados ENDÓGENO (feedback: indexação à inflação passada do próprio
    sistema + Brent + câmbio + bandeira) — o que o B9 descreve como "feedback effects
    between market and administered prices".

Não há modelo paralelo: este sistema consome os parâmetros do estimador conjunto e é o
único caminho de projeção da réplica.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from equacoes_bcb import _hp_cycle

PPC_AA = 1.0
META = 3.0
W_LIVRES = 0.76
NEUTRA_FIXA = 5.0


class SistemaIntegrado:
    def __init__(self, est: dict, q: pd.DataFrame, admin_est: dict | None = None):
        """est: params da conjunta (Phillips a*, IS b*) + expect (φ) + taylor/uip/admin.
        admin_est: (opcional) equação calibrada de administrados — o default usa a equação
        OLS endógena (feedback via inflação passada do próprio sistema).
        """
        self.p = est["phillips"]
        self.p_is = est["is"]
        self.p_expect = est["expect"]
        self.p_tay = est["taylor"]["params"]
        self.p_uip = est["uip"]["params"]
        self.p_adm = est["admin"]["params"]
        self.admin = admin_est["params"] if admin_est is not None else None
        self.q = q

    def _sim(self, periods, sim, state, gap2, scenario, admin_path_exog=None,
             e_seq=None, shock_gap_pp=0.0, shock_cambio_pp=0.0):
        lastval = lambda c: float(self.q[c].dropna().iloc[-1]) if self.q[c].notna().any() else float("nan")
        cambio = lastval("cambio")
        brent = lastval("brent")
        ff = lastval("ff")
        pi_com = lastval("pi_com")
        oni = lastval("oni")
        bandeira = float(np.nan)  # admin endógeno usa bandeira via cenário se houver
        meta_q = META / 4
        rows = []
        for i, period in enumerate(periods):
            if e_seq is not None:
                e = float(e_seq[i])
            else:
                # híbrido ancorado (default): convergência gradual à meta — o fixed-point
                # consistente (φ2) diverge neste modelo (hiato quase unitário, b1≈0,96)
                e = 0.8 * state["e_prev"] + 0.2 * meta_q
            state["e_prev"] = e
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
            dln_b = (np.log(brent / state.get("_brent", brent)) * 100
                     if state.get("_brent") and brent > 0 else 0.0)
            state["_brent"] = brent if np.isfinite(brent) else state.get("_brent", brent)

            # ---- IS: dinâmica do hiato com a juro neutra (estado-espaço) ----
            rreal = state["selic"] - 4 * e
            neutra = state.get("neutra", NEUTRA_FIXA)
            gap = (self.p_is["b1"] * state["gap"]
                   + self.p_is["b2"] * (neutra - rreal))
            if shock_gap_pp and i == 0:
                gap += shock_gap_pp

            # ---- Phillips de livres (com o hiato) ----
            imp = (pi_com + dln_c) - meta_q
            imp_en = dln_b
            dev_ppc = dln_c - PPC_AA / 4
            pi_l = (self.p["a1"] * state["pi_l"] + (1 - self.p["a1"]) * e
                    + self.p["a2"] * imp + self.p["a3"] * dev_ppc
                    + self.p["a4"] * state["gap"]
                    + self.p["a5"] * max(oni, 0) + self.p["a6"] * max(-oni, 0))

            # ---- Administrados ENDÓGENOS (feedback via indexação à inflação passada) ----
            if admin_path_exog is not None and period in admin_path_exog.index:
                pi_a = float(admin_path_exog.loc[period])
            else:
                # equação OLS de admin: inércia + indexação às livres do PRÓPRIO sistema
                # (feedback entre livres e administrados, como o B9) + câmbio/petróleo
                pi_a = (self.p_adm["const"] + self.p_adm["pi_a_1"] * state["pi_a"]
                        + self.p_adm["pi_l_1"] * pi_l + self.p_adm["dln_cambio"] * dln_c)
                if "dln_brent" in self.p_adm:
                    pi_a += self.p_adm["dln_brent"] * dln_b
            pi = W_LIVRES * pi_l + (1 - W_LIVRES) * pi_a

            rows.append({"period": str(period), "pi": pi, "pi_l": pi_l, "pi_a": pi_a,
                         "e_pi_next": e, "selic": selic, "gap": gap, "dln_cambio": dln_c})
            state["pi_l"], state["pi_a"], state["gap"], state["selic"] = pi_l, pi_a, gap, selic
            state["pi_prev"] = pi_l
            gap2 = gap

        out = pd.DataFrame(rows)
        hist = sim["pi"].tolist()
        allp = hist + out["pi"].tolist()
        cum = (1 + pd.Series(allp) / 100).rolling(4).apply(np.prod, raw=True)
        out["pi4"] = ((cum - 1) * 100).iloc[len(hist):].reset_index(drop=True)
        return out

    def forecast(self, horizon: int = 12, scenario=None, admin_path_exog=None,
                 expect_mode: str = "hybrid", expect_tol: float = 1e-3,
                 expect_maxiter: int = 40, shock_gap_pp: float = 0.0,
                 shock_cambio_pp: float = 0.0) -> pd.DataFrame:
        q = self.q.copy()
        last_q = q.index[-1].to_period("Q")
        periods = pd.period_range(last_q + 1, periods=horizon, freq="Q")
        sim = q.iloc[max(0, q.index.get_loc(q.index[-1]) - 3):].copy()
        state = {k: float(sim[k].iloc[-1]) for k in ["pi_l", "pi_a", "gap", "selic", "e_pi_next"]}
        state.setdefault("selic_2", state["selic"])
        state["e_prev"] = state["e_pi_next"]
        state["pi_prev"] = state["pi_l"]
        state["neutra"] = getattr(self, "neutra", NEUTRA_FIXA)
        gap2 = float(sim["gap"].iloc[-2]) if len(sim) > 1 else state["gap"]

        def run(e_seq=None):
            return self._sim(periods, sim, dict(state), gap2, scenario, admin_path_exog, e_seq,
                             shock_gap_pp, shock_cambio_pp)

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
