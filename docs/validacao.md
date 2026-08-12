# Validação — metodologia, métricas e metas de referência

## 0. Auditoria point-in-time e look-ahead bias

Uma auditoria dedicada foi executada sobre todo o pipeline (downloader → snapshots →
modelos) buscando vazamento de informação futura. Achados corrigidos:

- **C1 — `longhorizon.py`**: o filtro HP do hiato era calculado sobre a série
  completa (`pt_latest`) e depois fatiado por vintage, contaminando o gap com
  dados posteriores ao corte. **Corrigido**: o hiato agora é recalculado com
  dados apenas até cada vintage.
- **C2 — ONI (NOAA)**: a estação de 3 meses entrava no snapshot com lag zero
  (disponível ~1 mês antes da publicação real). **Corrigido**: `ref_date` = fim do
  mês final da estação + `lag_days: 10`.

Invariantes verificados em execução: em `pt_2026Q2` (cutoff 30/06/2026), 100% das
linhas satisfazem `ref_date ≤ cutoff` e `available_from ≤ cutoff`; a última pesquisa
Focus no snapshot é 30/06/2026; nenhum exógeno da projeção usa valor posterior ao
cutoff; os modelos estimam somente com `snapshots/pt_<vintage>/`.

Caveats remanescentes (documentados, não são vazamento):

- **M1 — IC-Br com lacuna 2024H2–2025Q3** (série nova `28451` tem buraco): a Phillips
  agregada é estimada até 2024Q2, excluindo o ciclo de aperto de 2024–25. No modelo
  completo, `pi_com` é preenchido com ffill (regressor ~constante pós-gap).
- **M2/M4 — timing da comparação 2026Q2**: o snapshot `pt_2026Q2` só tem IPCA até
  mai/2026 (junho sairia 10/07), então a base termina em 2026Q1 e o "1º trimestre"
  da projeção (2026Q2) mistura previsão com nowcast. O RPM já conhecia abr–mai.
- **M3 — condicionamento exógeno incompleto**: a projeção condiciona apenas a Selic
  ao cenário do RPM; `pi_com`, `oni`, `fiscal` e câmbio seguem flat no último valor
  realizado (o cenário assume El Niño forte e Brent 90–100). A comparação com o RPM
  reflete também essa diferença de condicionantes.
- **M5 — filtros bidirecionais**: HP e Kalman usam suavização dentro da amostra de
  cada vintage (método declarado, análogo à prática do BCB); para strict real-time
  seria necessário versões recursivas (one-sided).

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

- **MAE vs RPM: 0,46 p.p.** (11 trimestres) com o cenário de referência completo
  condicionado (Selic Focus, câmbio PPC, Brent, RONI) **e bloco de administrados
  calibrado** (`--admin calibrado`, default). Sem os condicionantes o MAE era ~1,07 p.p.;
  com admin OLS, 0,59 p.p.

## 3.0 Modelo integrado (o modelo BCB da réplica) — `run_integrado.py`

Estimação bayesiana **conjunta plena** (PyMC, hiato + juro neutra latentes + Phillips +
IS + expectativas) com o sistema único (admin endógeno + expectativas):

- **MAE vs RPM jun/2026: ~0,50 p.p.** (expectativas híbridas ancoradas — default; o modo
  `--expect consistent` diverge neste modelo, documentado).
- **IRF demanda −1 p.p. (hiato) → IPCA 4T**: ~0,22 p.p. (híbrido) / ~0,6 (consistente)
  — RI: −0,45. O canal de hiato (a4≈0,06) é menor que o do RI (0,14).
- **Juro real neutra** (estado latente): média ~4,5%.
- **PIT**: φ2 (consistente) não é estimado com `pi.shift(-1)` — fixado no RI (0,12) e
  φ1/φ3 com priors ancorados; rodada no Docker com g++ (conjunta ~1 min p/ 400/300).

Este é o único componente tratado como "modelo BCB" na réplica (ver `docs/status.md`);
`modelo-agregado/` e `modelo-completo/` são experimentos legado.

## 3.1 Modelo agregado fiel ao BCB (RI dez/2021) — `run_bcb.py`

Estimação bayesiana com os **priors publicados** do RI dez/2021 (amostra 2003T4–2019T4),
comparação com as modas a posteriori do BCB:

| Equação | Parâmetro | Réplica | RI 2021 | Leitura |
|---|---|---|---|---|
| Phillips | inércia | 0,35 | 0,24 | mesmo ballpark |
| | hiato | 0,05 | 0,14 | menor (hiato HP vs estado-espaço) |
| | importada / câmbio-PPC | 0,006 / 0,006 | 0,018 / 0,017 | canais fracos na amostra pública |
| IS | AR | 0,77 | 0,74 | próximo |
| | fiscal ciclo-corrigido | 0,029 | 0,030 | próximo |
| | incerteza | 0,052 | 0,041 | próximo |
| | hiato mundial (proxy EUA) | 0,18 | 0,04 | proxy mais alto |
| Expectativas | inércia / consistente | 0,43 / 0,42 | 0,73 / 0,12 | proxy da consistente infla φ2 |

- **Juro real neutra latente** (Kalman): média **3,6%**, cai de ~5% para ~2% no fim da
  amostra — consistente com a narrativa do BCB.
- **Projeção do agregado BCB** (`system_bcb.py`): expectativas consistentes (fixed-point)
  → **MAE vs RPM: 0,60 p.p.** (11 trimestres), estável, convergindo para ~4% ao fim.
- **Hiato por Kalman**: Phillips hiato 0,05 → **0,27** (RI 0,14); IS enfraquece (AR 0,44)
  — trade-off documentado.
- **Decomposição 2024** (vs ofício 374): inércia 0,33 (0,52) · expectativas 0,65 (0,30) ·
  importada 0,00 (0,72) · hiato 0,11 (0,49) · residual 0,69. O canal de inflação
  importada não é identificado pela amostra pública (coef ~0) — limitação documentada.
- **Bloco de administrados calibrado (anexo B9)**: estrutura por regra institucional,
  repasses de câmbio/petróleo calibrados nos **alvos de IRF do anexo** — verificação:
  câmbio +10% → admin **+1,87 p.p.** em 4T (alvo 1,8); petróleo +10% → **+1,31 p.p.**
  (alvo 1,3). Aderência in-sample à série oficial (SGS 11427): corr ~0,40, MAE ~0,62 p.p.
  mensal. Limitação: o agregado SIDRA de admin não reproduz a cesta oficial (corr ~0,1).
- **Estimação bayesiana (PyMC, conjunta Phillips+IS+admin): MAE 0,60 p.p.**,
  com repasse cambial imposto positivo e prior informativo do hiato na Phillips
  (evita os coeficientes explosivos 4–18 da amostra curta). `run_complete.py --est bayes`.
- **IRFs** (modelo bayesiano, efeito no IPCA acumulado 4T):

  | Choque | Pico (Δ p.p.) | Horizonte |
  |---|---:|---:|
  | Câmbio +10% (depreciação) | +0,46 | ~4T |
  | Demanda +1 p.p. (hiato) | +0,44 | ~4T |
  | Brent +10% (nível, 1º T) | +0,04 | 1T |
  | Selic +1 p.p. | ≈ −0,00 | — (canal de juro real fraco) |

- **Balanço de riscos**: P(IPCA4 fora de [1,5; 4,5]) ≈ **0,80–0,83** em 2026Q4–2028Q4
  (fan chart paramétrico, amostras da posterior) — próximo do ~0,79 do RPM.
- **Satélite de administrados (24+1 equações, `admin24.py`)**: equações por item
  estimadas (SIDRA 2020+). **Limitação**: o agregado ponderado do satélite tem
  correlação ~0,11 com a série oficial (SGS 11427) — a cesta/pesos oficiais dos
  administrados não são reproduzíveis da classificação atual do SIDRA (os livres
  reproduzem a 0,98). O sistema usa a equação agregada de admin estimada sobre a
  série oficial. As 25 equações permanecem como módulo de pesquisa documentado.
- **Limitação dominante**: as Phillips setoriais são estimadas em apenas ~23
  trimestres (SIDRA 2020+), produzindo coeficientes instáveis. O bloco setorial é
  o componente de menor robustez da réplica e deve ser lido com cautela.
- **Expectativas consistentes (fixed-point)**: disponível (`--expect consistent`),
  mas piora o ajuste (MAE 1,54) porque as Phillips de amostra curta têm hiato
  explosivo; o modo híbrido (ancorado na meta) acompanha melhor o RPM.

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

Resultado da réplica: ver `modelo-completo/output/repasse_cambial.csv`. **OLS**:
coeficientes de câmbio nas Phillips saem fracos e de sinal negativo (apreciação
cambial combinada com inflação alta em 2021–2023 confunde a estimação), de modo que
o exercício em OLS não reproduz o repasse positivo do BCB. **Bayesiano** (prior
positivo de repasse, `--est bayes`): IRF de câmbio +10% → **+0,46 p.p.** no IPCA
acumulado 4T em ~4 trimestres — sinal correto e magnitude compatível (mais baixa
que os +1,0 do anexo). Isso é uma limitação honesta da réplica com estimação
reduzida por equação, e não um defeito da especificação do BCB.

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

## 8. Como reproduzir (modelo único integrado)

```bash
python downloader/scripts/01_download.py
python downloader/scripts/02_build_dataset.py
python modelo-integrado/scripts/run_integrado.py   # MODELO BCB (conjunta plena) — projeção + IRFs
python modelo-integrado/scripts/backtest.py        # backtest rolante PIT (29 vintages)
python modelo-integrado/scripts/longhorizon.py     # MAE 1T/4T
python modelo-integrado/scripts/decomposicao.py    # decomposição 2024 vs ofício 374
python scripts/make_figures.py                     # figuras da documentação
```

Rodada oficial (com g++): `docker compose run pipeline` (equivalente a `python main.py`).
Saídas em `modelo-integrado/output/` e `docs/figures/`.

> **Nota histórica**: as versões parciais anteriores (`modelo-agregado`, `modelo-completo`)
> foram removidas ao convergir para o modelo único. Seus resultados: agregado MAE 0,20,
> completo 0,46, backtest agregado 1,83, admin calibrado (IRFs 1,86/1,30).
