# Validação — metodologia, métricas e metas de referência

## 1. Duas formas de medir o erro

**A) Aderência ao cenário oficial (projeção 2026Q2 → 2029Q2).**
O RPM de junho/2026 publica a trajetória trimestral do IPCA acumulado em 4 trimestres
(Tabela 2.2.1). Comparamos a projeção do modelo com essa trajetória oficial.
São dois *forecasts* — não é erro contra realizado (2026T3 em diante é futuro).

Métricas: MAE ao longo dos 12 trimestres; diferença no 1º trimestre; parcela dos
trimestres em que a projeção oficial cai dentro do leque (50% e 90%) do modelo.

**B) Acuracidade real (backtest rolante por vintage point-in-time).**
Para cada vintage `pt_2019Q1 … pt_2026Q1`: estimar com dados até o cutoff, projetar
12 trimestres e comparar com o IPCA realizado. Métricas: MAE, RMSE e viés por
horizonte; comparação com benchmarks (Focus, naive/persistência).

## 2. Resultados do modelo agregado (vintage pt_2026Q2)

- **MAE vs RPM (11 trimestres): 0,20 p.p.**; Selic Taylor similar (0,21 p.p.).
- **1º trimestre (2026Q2): 4,54% vs 4,80%** do RPM (dif. −0,26 p.p.).
- **Cenário oficial dentro do leque de 50% do modelo em todos os trimestres
  sobrepostos** (11/11); dentro do de 90% igualmente.
- Projeção do modelo converge para ~3,1% a.a. (2028Q4), igual ao RPM.

## 3. Resultados do modelo completo (setorial, 2020+)

- **MAE vs RPM: 1,07 p.p.** (11 trimestres) — pior que o agregado.
- **Limitação dominante**: as Phillips setoriais são estimadas em apenas ~23
  trimestres (SIDRA 2020+), produzindo coeficientes instáveis (ex.: hiato na
  alimentação com coeficiente muito elevado). O bloco setorial é o componente de
  menor robustez da réplica e deve ser lido com cautela.

## 4. Backtest rolante (modelo agregado, 29 vintages, 293 observações)

| Horizonte | MAE | RMSE | Viés |
|---:|---:|---:|---:|
| 1 | 0,73 | 1,03 | −0,11 |
| 4 | 2,34 | 3,08 | −0,62 |
| 8 | 1,94 | 3,10 | −1,24 |
| 12 | 1,44 | 2,40 | −0,84 |

- **MAE médio: 1,83 p.p.**; RMSE 2,72; viés −0,77 p.p. (modelo subprojeta inflação,
  concentrado no período 2021–2023 de surpresas inflacionárias).
- **Benchmark naive (persistência): MAE 2,84 p.p.** → o modelo ganha do benchmark
  em ~1 p.p. no MAE médio.

## 5. Repasse cambial (+10% USD/BRL, choque de nível no 1º trimestre)

Benchmark publicado no anexo B9 do RPM jun/2025 (IRF sem reação de política): efeito
máximo no acumulado 4T de **+1,8 p.p. em administrados**, **+0,7 p.p. em livres** e
**+1,0 p.p. no IPCA** após ~4 trimestres.

Resultado da réplica: ver `modelo-completo/output/repasse_cambial.csv`. **Atenção**:
nas estimações OLS com amostra 2002–2026 (agregado) e 2020+ (setorial), os
coeficientes de câmbio nas Phillips saem fracos e de sinal negativo (período de
apreciação cambial combinada com inflação alta em 2021–2023 confunde a estimação),
de modo que o exercício **não reproduz o repasse positivo do BCB**. Isso é uma
limitação honesta da réplica com estimação reduzida por equação, e não um
defeito da especificação do BCB.

## 6. Metas de referência (benchmarks)

| Métrica | Meta de referência | Réplica |
|---|---:|---:|
| MAE 12 trimestres vs RPM | ~0,47 p.p. | 0,20 p.p. (agregado) / 1,07 (completo) |
| Diferença 1º trimestre | ~0,03 p.p. | −0,26 p.p. (2026Q2) |
| RPM dentro do leque 50% | maioria dos trimestres | 11/11 (agregado) |
| MAE backtest vs naive | ganho positivo | 1,83 vs 2,84 p.p. |

Estas metas são apenas pontos de referência numéricos de comparação; a
implementação e a documentação usam exclusivamente as fontes do BCB
(ver `docs/equacoes.md`).

## 7. Benchmark contra projeções oficiais históricas (RPMs)

Planejado: transcrever o cenário de referência de cada RPM (2019Q1–2026Q1) para
`modelo-agregado/config/rpm_historico.csv` e medir nosso erro vs o erro do BCB em
cada vintage. **Status**: esquema criado; transcrição pendente (extração manual de
~30 PDFs). O benchmark Focus/naive do backtest já cobre a comparação com o mercado.

## 8. Como reproduzir

```bash
python downloader/scripts/01_download.py
python downloader/scripts/02_build_dataset.py
python modelo-agregado/scripts/run_aggregate.py     # projeção + fan chart + comparação
python modelo-agregado/scripts/backtest.py          # backtest rolante
python modelo-completo/scripts/run_complete.py      # setorial + repasse cambial
python modelo-completo/scripts/validate_sector.py   # validação da setorização
```

Saídas em `*/output/`: tabelas CSV, fan charts e gráficos de erro.
