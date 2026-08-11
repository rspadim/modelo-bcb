"""Meta de inflação (CMN) por ano."""
import pandas as pd

META_POR_ANO = {
    1999: 8.0, 2000: 6.0, 2001: 4.0, 2002: 3.5, 2003: 8.5, 2004: 5.5,
    2005: 4.5, 2006: 4.5, 2007: 4.5, 2008: 4.5, 2009: 4.5, 2010: 4.5,
    2011: 4.5, 2012: 4.5, 2013: 4.5, 2014: 4.5, 2015: 4.5, 2016: 4.5,
    2017: 4.5, 2018: 4.5, 2019: 4.25, 2020: 4.0, 2021: 3.75, 2022: 3.5,
    2023: 3.25, 2024: 3.0, 2025: 3.0, 2026: 3.0,
}


def meta_series(q: pd.DataFrame, tol: float = 1.5) -> pd.Series:
    years = q.index.year
    return years.map(META_POR_ANO)
