# Modelagem no BCB × réplica — auditoria de lacunas e roadmap para o modelo fiel

Referências: `docs/referencias/` (RI dez/2021 b7, RI set/2020 b7, RI jun/2024 b10–b12,
RPM jun/2025 B9, RI mar/2023 b4), `docs/priors_bcb.md`, `docs/proveniencia.md`.

## 1. O que o BCB modela (segundo as fontes)

### Modelo agregado (RI dez/2021, boxe b7)
- **Phillips (livres)**: inércia + expectativas + **inflação importada** (IC-Br em R$ como
  desvio da meta, 3 componentes: agropecuária, metal, energia) + **câmbio como desvio da
  PPC** (efeito residual) + hiato + **El Niño/La Niña assimétricos**.
- **IS**: hiato em função de defasagens, **hiato do juro real** (Focus 4T − expectativa 4T
  − juro neutro), **fiscal do governo central corrigido pelo ciclo e por outliers**
  (desvio da tendência), **incerteza econômica**, **hiato mundial**.
- **Taylor**: resposta ao desvio da expectativa de inflação em relação à meta.
- **UIP**: Δcâmbio vs diferencial de juros doméstico/externo ajustado pelo **prêmio de
  risco (CDS 5 anos)**; longo prazo segue PPC.
- **Expectativas**: `Eπ = φ1·Eπ_prev + φ2·Eπ_consistente + φ3·π_passada` — inclui a
  componente **consistente com o modelo** (φ2 ≈ 0,12).
- **Estimação**: bayesiana, estado-espaço com Kalman; **hiato como latente** condicionado
  por PIB, Nuci, desocupação e Caged (γ de proporcionalidade estimados) E pelas próprias
  equações (Phillips, expectativas, IS); **juro real neutro como estado latente**;
  amostra 2003T4–2019T4; priors "limitando apenas o suporte".
- **Processo** (RI mar/2023 b4): especialistas de curto prazo (livres ~2T, admin ~5T),
  modelos satélites, condicionantes exógenos (Selic Focus + câmbio PPC), julgamento do Copom.

### Administrados (RPM jun/2025, anexo B9)
- **24 equações calibradas** (NÃO estimadas): "not estimated equations, but calibrated
  equations based on the current institutional framework".
- Regras por item: energia (ANEEL anual + bandeiras + Itaipu ~8% com câmbio),
  medicamentos (CMED: IPCA12 + Fator Y, abril), plano de saúde (ANS: IVDA + IPCA ex-saúde,
  distribuído 12m), combustíveis (petróleo R$ + ICMS indexado no 1ºT + margem), GLP
  (margem no 3ºT), gás encanado/veicular (regressão IPCA4 + petróleo R$ + item correlato),
  emplacamento/conselho (IPCA ano anterior /4 no 1ºT), demais com/sem sazonalidade.
- **IRFs (sem reação de política)**: câmbio +10% → admin ≈ **+1,8 p.p.** (4T);
  petróleo +10% → ≈ **+1,3 p.p.**; repasse 4T ≈ 50% gasolina, 20% GLP; IVDA +1 p.p. →
  plano +0,8, admin +0,14, IPCA +0,04.

## 2. O que a réplica faz × lacunas (priorizadas)

| # | Aspecto | BCB | Réplica | Lacuna (impacto) |
|---|---|---|---|---|
| 1 | **Estimação conjunta** | Estado-espaço bayesiano: hiato+neutro latentes com as equações | 2 estágios (hiato primeiro) + **juro neutro latente (Kalman, P3)** | **Média** (P3 parcial) |
| 2 | **Inflação importada** | IC-Br em R$ como desvio da meta, 3 componentes; câmbio como desvio da PPC | **IC-Br R$ + câmbio PPC (P2)**; componentes não disponíveis | Baixa |
| 3 | **Clima** | El Niño/La Niña assimétricos | **Assimétrico (P2)** | ✓ |
| 4 | **Expectativas consistentes** | φ2 ≈ 0,12 no padrão | **Estimada com φ2 (P4)**; projeção usa `consistent` | Baixa |
| 5 | **Admin** | Calibrado por regra (B9) | **Calibrado (P1)** | ✓ |
| 6 | **IS** | Fiscal ciclo-corrigido, incerteza, hiato mundial | **Completa (P5)**, incerteza/hiato por proxy | Baixa |
| 7 | **UIP** | Prêmio de risco (CDS 5a) | Constante (sem CDS público) | Baixa (dado indisponível) |
| 8 | **Juro neutro** | Latente no estado | **Latente (P3)**: média 3,6%, cai para ~2% | ✓ |
| 9 | **Especialistas curto prazo** | Nowcasts livres/admin | Sem | Baixa (julgamento) |
| 10 | **Dados do hiato** | PIB, Nuci, desocupação, Caged | IBC-Br, PIB, desocupação (Nuci/Caged não obtidos) | **Média** (dado) |

## 3. Roadmap para o modelo `bcb` fiel ao teórico
- **P1 ✓ — Admin calibrado** (B9): estrutura por regra + repasses calibrados nos alvos de
  IRF do anexo; MAE vs RPM **0,46 p.p.** (era 0,59 com admin OLS).
- **P2 ✓ — Phillips agregada fiel** (`phillips_bcb.py`): IC-Br em R$ (importada), câmbio
  como desvio da PPC, clima assimétrico (El Niño/La Niña), priors do RI dez/2021, amostra
  2003T4–2019T4. Estimação bayesiana (priors Uniform do RI): inércia **0,35** (RI 0,24),
  canais não degenerados (imp 0,006, dev_ppc 0,006, hiato 0,05, clima 0,005).
- **P3 ✓ — Juro real neutra latente** (`estado_espaco_bcb.py`): random walk estimado com a
  IS via Kalman (statsmodels MLEModel). Resultado: média **3,63%**, caindo de ~5% para ~2%
  no fim da amostra — consistente com a narrativa do BCB (3,6% em 2021). A versão completa
  (hiato E neutra conjuntos, bayesiano) fica como evolução — os quatro indicadores de
  atividade do BCB (PIB, Nuci, desocupação, Caged) não estão todos disponíveis.
- **P4 ✓ — Expectativas com componente consistente** (`equacoes_bcb.py::estimate_expect_bcb`):
  φ1 inércia 0,43 (RI 0,73), φ2 consistente 0,42 (RI 0,12 — proxy pelo realizado), φ3 passada
  0,08 (RI 0,04). Usada no modo `--expect consistent` do sistema completo.
- **P5 ✓ — IS completa** (`equacoes_bcb.py::estimate_is_bcb`): fiscal **ciclo-corrigido**
  (desvio HP) + **incerteza** (proxy: vol rolante do câmbio) + **hiato mundial** (proxy:
  hiato do produto dos EUA, FRED GDPC1/GDPPOT). Resultados: AR **0,77** (RI 0,74), fiscal
  **0,029** (RI 0,030), incerteza 0,052 (RI 0,041), hiato mundial 0,18 (RI 0,04 — proxy).
- **P6 ✓ — Decomposição de inflação** (`decomposicao.py`): contribuições ao desvio de
  livres vs meta (inércia, expectativas, importada, câmbio, hiato, clima). 2024: inércia
  0,33, expect 0,65, hiato 0,11, importada 0,00, residual 0,69 — vs ofício 374 (inércia
  0,52, importada 0,72, hiato 0,49, expect 0,30). A diferença reflete o canal de inflação
  importada fraco (coef ~0) e o residual alto da estimação restrita.

### Comparação resumida (réplica vs modas do RI dez/2021)

| Equação | Parâmetro | Réplica | RI 2021 |
|---|---|---|---|
| Phillips | inércia | 0,35 | 0,24 |
| | hiato | 0,05 | 0,14 |
| IS | AR | 0,77 | 0,74 |
| | fiscal ciclo-corrigido | 0,029 | 0,030 |
| | incerteza | 0,052 | 0,041 |
| Expectativas | inércia | 0,43 | 0,73 |
| | consistente | 0,42 | 0,12 |

`modelo-agregado/scripts/run_bcb.py` reproduz tudo e salva `comparacao_bcb_ri2021.csv`.

## 3.1 Rodada de melhorias (P2–P6 refinados)

- **Inflação importada reforçada**: IC-Br em R$ como **desvio da meta** (construção do RI)
  + **componente de energia** (ΔBrent em R$), dois regressores com suporte ≥0. O canal
  continua fraco na amostra pública (imp_total ~0,007 bayesiano; ~0 no OLS restrito) —
  a decomposição de 2024 ainda atribui pouco à importada (0,0 vs 0,72 do ofício), agora
  com o residual explicando a diferença.
- **Hiato por Kalman** no `run_bcb` (`--gap kalman`, default): o hiato da Phillips subiu
  de 0,05 → **0,27** (RI 0,14), mas a IS ficou mais fraca (AR 0,44 vs 0,74; juro real
  0,004 vs 0,55) — trade-off documentado entre o hiato do estado-espaço (mais próximo do
  BCB) e o ajuste da IS.
- **Projeção do agregado BCB** (`system_bcb.py`): sistema com Phillips/IS/expectativas
  BCB, Taylor/UIP/admin do modelo atual, **expectativas consistentes resolvidas por
  fixed-point** (φ2 do RI). **MAE vs RPM: 0,60 p.p.** (estável, convergindo para ~4% ao
  fim do horizonte — mais alto que o agregado simples 0,20, trade-off de fidelidade).
- **Câmbio como desvio da PPC nas Phillips setoriais** (`phillips.py`/`system.py`):
  consistência com o agregado; MAE completo permanece **0,46 p.p.**.
- **Admin por item (B9)**: tabela de repasses por item (`B9_PT`: gasolina ~50%, GLP ~20%,
  diesel ~65%, energia ~8% FX) documentada; a calibração agregada mantém o inicial
  empírico (0,19/0,14) que reproduz os alvos de IRF com melhor ajuste.

## 4. Notas de fidelidade
- Parâmetros numéricos das 24 equações de admin **não são publicados**; a réplica calibra
  repasses nos **alvos de IRF do anexo B9** (1,8 / 1,3 p.p.) e a sazonalidade na série
  oficial — método documentado em `admin_calibrado.py`.
- A réplica não reproduz a cesta oficial de administrados a partir do SIDRA 2020+
  (corr ~0,1) — os itens livres reproduzem a 0,98. Por isso o admin calibrado usa a
  série oficial como alvo, não o agregado SIDRA.
