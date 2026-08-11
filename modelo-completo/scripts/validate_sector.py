"""Valida a setorização: setorial ponderado vs SGS livres/admin."""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src import sector

SNAPSHOT = ROOT.parent / "downloader" / "data" / "snapshots" / "pt_2026Q2" / "data.parquet"
df = pd.read_parquet(SNAPSHOT)
sub = df[(df.source == 'sidra') & (df.variable.isin([63, 66]))][
    ['ref_date', 'item_code', 'item_name', 'variable', 'value']]
vars_df, weights_df = sector.build_sectoral_monthly(sub)

sgs = df[df.source == 'sgs'][['ref_date', 'series', 'value']]
sgs = sgs[sgs.series.isin(['ipca_livres', 'ipca_admin', 'ipca'])]
sgs = sgs.pivot(index='ref_date', columns='series', values='value')

comp = vars_df.join(sgs).dropna()
print('Correlação / nível:')
for col in ['servicos', 'industriais', 'alimentacao', 'admin', 'livres']:
    off_name = 'ipca_livres' if col == 'livres' else 'ipca_admin' if col == 'admin' else None
    if off_name is not None:
        j = pd.concat([vars_df[col], sgs[off_name]], axis=1, join='inner').dropna()
        print(f'  {col:12s} vs {off_name}: corr={j[col].corr(j[off_name]):.3f} '
              f'mean_off={(j[col]-j[off_name]).mean():.3f} p.p.')
print()
print('Pesos médios por setor (% IPCA):')
print(weights_df.mean().round(2).to_string())
print()
print('Amostra vars (2024-2026):')
print(vars_df.loc['2024-01-01':].round(2).tail(8).to_string())
