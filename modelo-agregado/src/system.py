"""Solução recursiva do sistema e projeção forward (12 trimestres)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import meta as meta_mod

W_LIVRES = 0.76


def _p(p: dict, key: str, default: float = 0.0) -> float:
    return float(p.get(key, default))


class ModelSystem:
    def __init__(self, est: dict, q: pd.DataFrame, cfg: dict):
        self.est = est
        self.q = q
        self.cfg = cfg
        self.w_livres = cfg.get("w_livres", W_LIVRES)

    def forecast(self, horizon: int = 12, selic_path: pd.Series | None = None,
                 shocks: dict | None = None, seed: int | None = None) -> pd.DataFrame:
        """Projeta `horizon` trimestres a partir do último trimestre da base.

        selic_path: trajetória exógena da Selic (por período). Se None, usa a
        regra de Taylor (Selic endógena).
        shocks: dicionário opcional de choques nos resíduos (ex.: fan chart).
        """
        rng = np.random.default_rng(seed)
        q = self.q.copy()
        last_q = q.index[-1].to_period("Q")
        periods = pd.period_range(last_q + 1, periods=horizon, freq="Q")
        periods_str = periods.astype(str)

        start_idx = q.index.get_loc(q.index[-1])
        sim = q.iloc[max(0, start_idx - 3): start_idx + 1].copy()
        pi_hist = sim["pi"].tolist()  # últimos 4 trimestres realizados (para acumular 4T)

        # valores de partida (exógenos usam o último não-NaN disponível)
        def _last(col: str, default: float = 0.0) -> float:
            s = sim[col].dropna()
            return float(s.iloc[-1]) if len(s) else default
        last_pi_com = _last("pi_com")
        last_oni = _last("oni")
        last_fiscal = _last("fiscal")
        last_ff = _last("ff")

        meta = meta_mod.META_POR_ANO.get(q.index[-1].year, 3.0)

        # Valores de partida para variáveis defasadas
        last_selic = float(sim["selic"].iloc[-1])
        last_selic2 = float(sim["selic"].iloc[-2]) if len(sim) > 1 else last_selic
        last_pi_l = float(sim["pi_l"].iloc[-1])
        last_pi_a = float(sim["pi_a"].iloc[-1])
        last_pi = float(sim["pi"].iloc[-1])
        last_gap = float(sim["gap"].iloc[-1])
        last_gap2 = float(sim["gap"].iloc[-2]) if len(sim) > 1 else last_gap
        last_e = float(sim["e_pi_next"].iloc[-1])
        last_cambio = float(sim["cambio"].iloc[-1])

        p_phi = self.est["phillips"]["params"]
        p_is = self.est["is"]["params"]
        p_tay = self.est["taylor"]["params"]
        p_uip = self.est["uip"]["params"]
        p_adm = self.est["admin"]["params"]

        rows = []
        all_pi = list(pi_hist)
        shock_default = lambda: 0.0
        for i, period in enumerate(periods):
            t = period
            epi = last_e  # expectativa defasada

            # Expectativas: convergência gradual à meta (em taxa trimestral)
            e_forward = 0.8 * last_e + 0.2 * (meta / 4)
            last_e = e_forward

            # Selic: condicionada ou endógena (Taylor)
            if selic_path is not None and period in selic_path.index:
                selic = float(selic_path.loc[period])
            else:
                dev = e_forward - meta
                selic = (
                    _p(p_tay, "const") + _p(p_tay, "selic_1") * last_selic
                    + _p(p_tay, "selic_2") * last_selic2 + _p(p_tay, "dev_pi") * dev
                )
            # suavização (evita explosão)
            selic = 0.85 * last_selic + 0.15 * selic

            # Câmbio (UIP)
            dln_cambio = (
                _p(p_uip, "const") + _p(p_uip, "diff_juros") * (last_selic - last_ff)
            )
            if shocks and "dln_cambio" in shocks:
                dln_cambio += shocks["dln_cambio"][i]
            cambio = last_cambio * np.exp(dln_cambio / 100)

            # IS
            rreal_1 = last_selic - 4 * last_e
            gap = (
                _p(p_is, "const") + _p(p_is, "gap_1") * last_gap
                + _p(p_is, "gap_2") * last_gap2
                + _p(p_is, "rreal_1") * rreal_1
                + _p(p_is, "dln_cambio") * dln_cambio
                + _p(p_is, "fiscal") * last_fiscal
            )

            # Commodities e clima: continuidade (sem choque) — flat
            pi_com = last_pi_com
            oni = last_oni

            # Phillips (livres)
            pi_l = (
                _p(p_phi, "const") + _p(p_phi, "pi_l_1") * last_pi_l
                + _p(p_phi, "e_pi_next") * e_forward
                + _p(p_phi, "gap_1") * last_gap
                + _p(p_phi, "dln_cambio") * dln_cambio
                + _p(p_phi, "pi_com") * pi_com
                + _p(p_phi, "oni") * oni
            )

            # Administrados
            pi_a = (
                _p(p_adm, "const") + _p(p_adm, "pi_a_1") * last_pi_a
                + _p(p_adm, "pi_l_1") * last_pi_l
                + _p(p_adm, "dln_cambio") * dln_cambio
            )

            # Identidade
            pi = self.w_livres * pi_l + (1 - self.w_livres) * pi_a

            # Erros (fan chart)
            if shocks:
                pi += shocks.get("pi", [0.0] * horizon)[i]
                pi_l += shocks.get("pi_l", [0.0] * horizon)[i]
                pi_a += shocks.get("pi_a", [0.0] * horizon)[i]

            rows.append({
                "period": str(period), "pi": pi, "pi_l": pi_l, "pi_a": pi_a,
                "selic": selic, "gap": gap, "dln_cambio": dln_cambio,
                "e_pi_next": e_forward, "pi_com": pi_com, "oni": oni,
            })
            all_pi.append(pi)

            # atualiza defasagens
            last_pi_l, last_pi_a, last_pi = pi_l, pi_a, pi
            last_gap, last_gap2 = gap, last_gap
            last_selic, last_selic2 = selic, last_selic
            last_cambio = cambio
            last_fiscal = last_fiscal

        out = pd.DataFrame(rows)
        cum = (1 + pd.Series(all_pi) / 100).rolling(4).apply(np.prod, raw=True)
        out["pi4"] = ((cum - 1) * 100).iloc[len(pi_hist):].reset_index(drop=True)
        return out


def monte_carlo(model: ModelSystem, horizon: int = 12, n_draws: int = 2000,
                seed: int | None = None) -> pd.DataFrame:
    """Fan chart: Monte Carlo dos resíduos das equações estimadas."""
    rng = np.random.default_rng(seed)
    res_pi = np.asarray(model.est["phillips"]["resid"].dropna())
    res_pi_l = res_pi
    res_pi_a = np.asarray(model.est["admin"]["resid"].dropna())
    res_c = np.asarray(model.est["uip"]["resid"].dropna())

    draws = []
    for _ in range(n_draws):
        sh = {
            "pi": rng.choice(res_pi, size=horizon),
            "pi_l": rng.choice(res_pi_l, size=horizon),
            "pi_a": rng.choice(res_pi_a, size=horizon),
            "dln_cambio": rng.choice(res_c, size=horizon),
        }
        draws.append(model.forecast(horizon=horizon, shocks=sh))
    stacked = pd.concat(draws)
    pivot = stacked.pivot_table(index="period", values="pi4", aggfunc="mean")
    pcts = {q_pt: stacked.groupby("period")["pi4"].quantile(q_pt) for q_pt in [0.05, 0.25, 0.5, 0.75, 0.95]}
    fan = pd.DataFrame({"mean": pivot["pi4"], **{str(int(k * 100)): v for k, v in pcts.items()}})
    fan.index.name = "period"
    return fan
