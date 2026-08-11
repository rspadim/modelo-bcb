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
                 ┌───────────────────────┴──────────────────────┐
                 ▼                                              ▼
      modelo-agregado/                                modelo-completo/
      hiato HP + OLS + fan chart                      3 Phillips setoriais + 24 eq.
      + comparação com o RPM                          admin + Kalman + backtest
```

A divisão em duas pastas de modelo é intencional:

- **modelo-agregado** — réplica enxuta (Phillips agregada de livres + admin agregado + IS + Taylor + UIP + expectativas, hiato por filtro HP). Serve para validar o esqueleto e para comparar a projeção com o cenário oficial do RPM (ver `docs/validacao.md`).
- **modelo-completo** — réplica do sistema divulgado: inflação livre desagregada em serviços / bens industriais / alimentação no domicílio, bloco de 24 equações de administrados, hiato e juro neutro por estado-espaço (filtro de Kalman) e backtest rolante por vintage.

Ambos **leem exclusivamente** `downloader/data/snapshots/pt_<vintage>/`. Nenhum modelo toca os dados brutos diretamente — a porta de entrada é o corte point-in-time.

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
