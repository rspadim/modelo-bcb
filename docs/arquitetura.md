# Arquitetura

## Visão geral

```
                            ┌─────────────────────────┐
                            │     downloader/         │
                            │   (uma única pasta de   │
                            │    dados compartilhada) │
                            └────────────┬────────────┘
                                         │  data/snapshots/pt_<YYYYQn>/
                                         ▼
                              modelo-integrado/
                              estimação bayesiana conjunta (PyMC):
                              hiato + juro neutra latentes + Phillips/IS/expectativas
                              sistema único → projeção → IRFs · backtest PIT · decomposição
```

É **um único modelo** (não há modelos paralelos). As versões parciais anteriores
(`modelo-agregado`, `modelo-completo`) foram removidas ao convergir.

O modelo **lê exclusivamente** `downloader/data/snapshots/pt_<vintage>/`. Nenhum modelo toca os dados brutos diretamente — a porta de entrada é o corte point-in-time.

## downloader

```
downloader/
├── config/
│   ├── series.yaml        # códigos SGS + fontes (Focus, SIDRA, FRED, NOAA)
│   ├── availability.yaml  # regra de disponibilidade (lag de publicação) por série
│   └── settings.yaml      # paths, janela de snapshots, HTTP
├── src/
│   ├── io_utils.py        # paths, config, HTTP com retry, cache
│   ├── sgs.py             # BCB/SGS (api.bcb.gov.br)
│   ├── focus.py           # Focus (OLINDA OData, com paginação)
│   ├── sidra.py           # IBGE/SIDRA (tabela 7060, IPCA por subitem)
│   ├── fred.py            # FRED (melhor esforço; não fatal)
│   ├── noaa.py            # NOAA ONI (El Niño/La Niña)
│   └── pit.py             # motor point-in-time (available_from, cutoffs)
├── scripts/
│   ├── 01_download.py     # coleta idempotente → data/raw
│   └── 02_build_dataset.py# série longa PIT + snapshots por trimestre
└── data/
    ├── raw/               # JSON/CSV brutos + manifest.json (fetched_at)
    ├── processed/series.parquet   # série longa: ref_date | value | available_from
    └── snapshots/pt_2019Q1 …      # um data.parquet por vintage
```

## Formato da série longa

`data/processed/series.parquet` — colunas:

| coluna | descrição |
|---|---|
| `source` | `sgs`, `focus`, `sidra`, `noaa`, `fred` |
| `series` | chave da série (ex.: `ipca`, `ibc_br`, `oni`, `focus_trimestrais`) |
| `ref_date` | data de referência da observação |
| `value` | valor numérico |
| `available_from` | data em que a observação ficou pública (motor PIT) |
| extras | por fonte: `code`, `name`, `item_code`, `survey_date`, `indicador` etc. |

## Snapshot point-in-time

`data/snapshots/pt_<YYYYQn>/data.parquet` contém todas as linhas com
`ref_date <= fim do trimestre` **e** `available_from <= fim do trimestre`.
A vintage de referência da projeção é `pt_2026Q2` (cutoff 30/06/2026, mesma do RPM de jun/2026). O snapshot `latest` usa o cutoff de hoje.

## Regra de ouro

> **Nenhuma observação com `available_from > cutoff` pode entrar em estimação ou projeção daquela vintage.**

Isto é garantido por construção no build e deve ser re-assertado no início de cada pipeline de modelo (a ser implementado na etapa seguinte).
