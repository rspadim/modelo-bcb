# Relatório — Réplica do Modelo de Pequeno Porte do BCB

Reconstrução pública em Python do modelo de projeção de inflação do Banco Central do Brasil, baseada nas publicações oficiais (RPM/RI e anexos), com dados point-in-time e validação contra o cenário oficial.

**Resultado central:** MAE de **0,20 p.p.** contra o cenário de referência do RPM de jun/2026 ao longo de 11 trimestres; a projeção oficial cai dentro do leque de 50% do modelo em todos os trimestres sobrepostos.

---

## 1. Dados e inflação de referência

IPCA trimestral e acumulado em 4 trimestres (2000–2026), com meta (3%) e banda de tolerância (1,5–4,5%):

![Série do IPCA](figures/serie_ipca.png)

Decomposição livre vs administrados e os três setores livres:

![Componentes](figures/componentes.png)

## 2. Hiato do produto

Filtro HP (λ=1600) sobre o log do IBC-Br dessazonalizado — a aproximação da réplica para a variável não observável (o BCB usa estado-espaço desde 2020; a versão completa do repositório usa Kalman):

![Hiato](figures/hiato.png)

## 3. Estimação — coeficientes

OLS por equação, amostra 2002–2026. Barras em azul = significativos a 5% (intervalo ±1,96 se):

![Coeficientes](figures/equacoes.png)

| Equação | Destaques |
|---|---|
| Phillips (livres) | inércia 0,32 · expectativa 0,68 (restrição NK imposta) · hiato ~0,00 (n.s.) |
| IS | persistência 0,72/–0,17 · juro real –0,065 · câmbio –0,062 · fiscal 1,08 |
| Taylor | suavização 1,66/–0,70 · resposta à expectativa 0,33 |
| UIP | diferencial de juros com sinal fraco (prêmio absorvido na constante) |
| Administrados | inércia 0,24 · repasse de livres 0,23 |
| Expectativas | persistência 0,44 |

## 4. Projeção vs cenário oficial (RPM jun/2026)

![Fan chart](figures/fan_chart.png)

Comparação trimestral (IPCA acumulado em 4 trimestres):

![Comparação trimestral](figures/comparacao_trimestral.png)

| Trimestre | Modelo | RPM | Diferença |
|---|---:|---:|---:|
| 2026Q2 | 4,54 | 4,80 | −0,26 |
| 2026Q3 | 5,00 | 4,80 | +0,20 |
| 2026Q4 | 5,38 | 5,20 | +0,18 |
| 2027Q1 | 4,32 | 4,60 | −0,28 |
| 2027Q2 | 3,85 | 4,00 | −0,15 |
| 2027Q3 | 3,61 | 4,10 | −0,49 |
| 2027Q4 | 3,46 | 3,70 | −0,24 |
| 2028Q1 | 3,35 | 3,20 | +0,15 |
| 2028Q2 | 3,28 | 3,20 | +0,08 |
| 2028Q3 | 3,22 | 3,10 | +0,12 |
| 2028Q4 | 3,17 | 3,10 | +0,07 |

**MAE: 0,20 p.p.** · Leque 50% cobre o cenário oficial em 11/11 trimestres.

## 5. Backtest por vintage

Para cada vintage (2019Q1–2026Q1) o modelo é re-estimado com dados **disponíveis até lá** (point-in-time) e projeta 12 trimestres:

![MAE por horizonte](figures/backtest_horizonte.png)

| Horizonte | MAE modelo | MAE naive | Ganho |
|---:|---:|---:|---:|
| 1 | 0,73 | 1,07 | ✔ |
| 2 | 1,46 | 1,66 | ✔ |
| 4 | 2,34 | 2,54 | ✔ |
| 6 | 2,28 | 3,23 | ✔ |
| 8 | 1,94 | 3,62 | ✔ |
| 12 | 1,44 | 3,53 | ✔ |

- MAE médio: **1,83 p.p.** vs **2,84 p.p.** (naive/persistência).
- O modelo vence o naive em **63,8%** das 293 observações; o ganho médio é de ~1 p.p.
- Viés médio −0,77 p.p. (subprojeção, concentrada no choque inflacionário de 2021–23).

Erros ao longo do tempo:

![Erros por vintage](figures/backtest_serie.png)

## 6. Long horizon — modelo vs realizado

Projeção recursiva (re-estimação a cada trimestre), 2011Q4–2025Q1:

![Long horizon](figures/longhorizon.png)

MAE 1 trimestre à frente: **0,67 p.p.** · MAE 4 trimestres à frente (fora de amostra): **2,07 p.p.**

## 7. Modelo completo (desagregado)

3 Phillips setoriais (serviços, bens industriais, alimentação no domicílio) + bloco de administrados + estado-espaço para o hiato:

![Modelo completo](figures/fan_chart_completo.png)

MAE: **0,46 p.p.** (cenário de referência completo — Selic Focus, câmbio PPC, Brent e RONI condicionados — e **bloco de administrados calibrado** pelo anexo B9). A robustez é menor que a do agregado porque a setorização (SIDRA, classificação atual) só cobre 2020+ (~23 trimestres de estimação).

**Bloco de administrados calibrado** (como o BCB — "not estimated equations, but calibrated equations", RPM jun/2025): estrutura por regra institucional (energia ANEEL+bandeira+Itaipu, CMED, ANS/IVDA, combustíveis petróleo R$+ICMS 1ºT, transportes/telecom indexados) com repasses de câmbio e petróleo **calibrados nos alvos de IRF do anexo B9**:
- câmbio +10% → admin **+1,87 p.p.** em 4T (alvo 1,8) · petróleo +10% → **+1,31 p.p.** (alvo 1,3);
- aderência in-sample à série oficial (SGS 11427): corr ~0,40, MAE ~0,62 p.p. mensal;
- limitação: o agregado SIDRA de administrados não reproduz a cesta oficial (corr ~0,1) — o calibrado usa a série oficial como alvo.

**Repasse cambial** (+10% USD/BRL, choque de nível):

![Repasse cambial](figures/repasse_cambial.png)

Atenção honesta: nas estimações OLS da réplica o coeficiente de câmbio sai fraco/negativo (apreciação 2021–23 combinada com inflação alta), então o exercício em OLS **não reproduz** o repasse positivo do BCB (anexo B9: admin +1,8 · livres +0,7 · IPCA +1,0 p.p. em 4T). **A estimação bayesiana com prior positivo de repasse corrige o sinal**: IRF de câmbio +10% → **+0,46 p.p.** no IPCA acumulado 4T em ~4 trimestres (ver seção 11).

## 8. Setorização

Preços livres construídos dos subitens do SIDRA (classificação por regras + pesos mensais) vs série oficial:

![Setorização](figures/setorizacao.png)

Correlação **0,98**; pesos médios consistentes com a estrutura do IPCA (serviços 45%, industriais 12%, alimentação 15%, administrados 28%).

## 9. Auditoria point-in-time

- 100% das linhas dos snapshots respeitam `available_from ≤ cutoff`.
- Focus com última pesquisa ≤ cutoff; exógenos da projeção ≤ cutoff.
- Corrigidos na auditoria: hiato no long horizon (HP por vintage) e disponibilidade do ONI (NOAA).
- Caveats documentados: lacuna do IC-Br 2024–25, timing da comparação 2026Q2 (base termina em 2026Q1), condicionamento exógeno parcial (só Selic), filtros bidirecionais HP/Kalman.

## 10. Reprodução

```bash
docker compose run pipeline    # tudo em 1 comando
python main.py                 # sem Docker
```

Etapas: `01_download` → `02_build` → `run_integrado` → `backtest_integrado` → `longhorizon` → `decomposicao` → `make_figures` (ver `docs/validacao.md` §8).

## 11. Diferenças em relação ao modelo interno do BCB

A réplica segue a estrutura documentada (RPM/RI e anexos), mas difere do modelo interno em pontos que as fontes públicas não permitem reproduzir integralmente:

1. **Estimação bayesiana conjunta (parcial)**. O BCB estima o MPP conjuntamente (estado-espaço com hiato e juro neutro latentes). A réplica tem um bloco bayesiano (PyMC) para Phillips setoriais + IS + admin com priors informativos, **mas o hiato vem de um estágio anterior** (filtro de Kalman/DynamicFactor), não é latente conjunto. `--est bayes` em `run_complete.py`.
2. **Bloco de 24 equações de administrados — agora calibrado como o BCB** (`admin_calibrado.py`,
   default `--admin calibrado`). O BCB não estima essas equações: "not estimated equations, but
   calibrated equations based on the current institutional framework" (RPM jun/2025, B9). A
   réplica implementa a estrutura por regra e calibra os repasses nos alvos de IRF do anexo.
   **Limitação**: o agregado do satélite SIDRA (2020+) tem baixa correlação com a série oficial
   (~0,1 vs 0,98 dos livres) — cesta/pesos oficiais não reproduzíveis da classificação atual;
   o agregado calibrado usa a série oficial como alvo.
3. **Sem julgamento de especialista de curto prazo.** O BCB usa nowcasts mensais e julgamento para os primeiros trimestres; a réplica projeta o trimestre seguinte diretamente do sistema.
4. **Condicionamento exógeno mais completo que antes, mas ainda parcial.** Câmbio (PPC), Brent e RONI (El Niño) agora são condicionados pelo cenário do RPM; faltam trajetórias oficiais de commodities agregadas, ONI além do RONI e julgamento fiscal.
5. **Expectativas.** O modo padrão ancora à meta (0,8·E + 0,2·meta/4). O modo "consistente" (fixed-point, `E_t[π_{t+1}]=π_{t+1}`) existe, mas as Phillips setoriais de amostra curta (hiato com coeficientes 4–18) tornam o equilíbrio auto-realizável alto; o híbrido acompanha melhor o RPM.
6. **Vintages reais do IBC-Br** não estão disponíveis gratuitamente (proxy point-in-time com lag documentado); **hiato externo** omitido; **prêmio de risco** (EMBI+/CDS) sem histórico público.
7. **Fan chart** com incerteza de parâmetro (amostras da posterior) além dos resíduos — o BCB calibra o leque com julgamento e outros componentes.
8. **Repasse cambial**: negativo no OLS (apreciação 2021–23); corrigido com prior bayesiano positivo (IRF +0,46 p.p. em 4T, vs +1,0 do anexo B9 — mais baixo, mas do sinal certo).

### Resultados novos desta rodada (vintage pt_2026Q2)

- **P1 — Admin calibrado (B9)**: MAE completo **0,46 p.p.** (era 0,59 com admin OLS);
  IRFs do anexo reproduzidas (câmbio +10% → admin **+1,87 p.p.**, petróleo +10% →
  **+1,31 p.p.** em 4T; alvos 1,8/1,3); in-sample vs SGS 11427 corr ~0,40.
- **Proveniência/PIT da especificação**: `docs/proveniencia.md` (conversões PDF→MD,
  fidelidade, `available_from`), `spec_manifesto.yaml` + check de vintage
  (`spec_manifesto.py`), PDFs em `docs/referencias/`, `docs/priors_bcb.md` (tabela do
  RI dez/2021 transcrita).
- **IRFs** (modelo bayesiano): câmbio +10% → +0,46 p.p. (pico 4T) · demanda +1 p.p. → +0,44 · Brent +10% → +0,04 · Selic +1 p.p. → ≈ −0,00 (canal de juro real fraco na amostra curta).
- **Balanço de riscos**: P(IPCA4 fora de [1,5;4,5]) ≈ **0,80–0,83** em 2026Q4–2028Q4 — próximo do ~0,79 reportado pelo RPM.
- **Fan chart paramétrico**: `output/fan_chart_parametrico.png` (bandas P10–P90/P25–P75 da posterior).

---

*Fonte: Banco Central do Brasil (RPM/RI e anexos), IBGE/SIDRA, NOAA, FRED. Não é código oficial do BCB.*
