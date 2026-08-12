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
| 1 | **Estimação conjunta** | Estado-espaço bayesiano: hiato+neutro latentes com as equações | 2 estágios (hiato primeiro) + bloco bayesiano parcial | **Alta** (P3) |
| 2 | **Inflação importada** | IC-Br em R$ como desvio da meta, 3 componentes; câmbio como desvio da PPC | IC-Br agregado % + Δe nominal | **Média** (P2) |
| 3 | **Clima** | El Niño/La Niña assimétricos | ONI simétrico | **Baixa** (P2) |
| 4 | **Expectativas consistentes** | φ2 ≈ 0,12 no padrão | só no modo `consistent` | **Média** (P4) |
| 5 | **Admin** | Calibrado por regra (B9) | **Calibrado agora** (`--admin calibrado`), repasses nos alvos B9 | ✓ (P1) |
| 6 | **IS** | Fiscal ciclo-corrigido, incerteza, hiato mundial | Primário cru | **Média** (P5) |
| 7 | **UIP** | Prêmio de risco (CDS 5a) | Constante (sem CDS público) | Baixa (dado indisponível) |
| 8 | **Juro neutro** | Latente no estado | Fixo (5,0% do cenário) | **Média** (P3) |
| 9 | **Especialistas curto prazo** | Nowcasts livres/admin | Sem | Baixa (julgamento) |
| 10 | **Dados do hiato** | PIB, Nuci, desocupação, Caged | IBC-Br, PIB, desocupação (Nuci/Caged não obtidos) | **Média** (P3, candidatos) |

## 3. Roadmap para o modelo `bcb` fiel ao teórico
- **P1 ✓ — Admin calibrado** (B9): estrutura por regra + repasses calibrados nos alvos de
  IRF do anexo; in-sample corr ~0,40 vs SGS 11427 (o agregado SIDRA não reproduz a cesta
  oficial — documentado); MAE vs RPM **0,46 p.p.** (era 0,59 com admin OLS).
- **P2 — Phillips agregada fiel**: inflação importada em R$ (desvio da meta), câmbio como
  desvio da PPC, clima assimétrico, suportes do RI dez/2021, amostra 2003T4–2019T4.
- **P3 — Estado-espaço conjunto bayesiano**: hiato + juro neutro latentes com PIB/Nuci/
  desocupação/Caged (candidatos Nuci/Caged a confirmar).
- **P4 — Expectativas consistentes no padrão** (φ2 como o BCB).
- **P5 — IS completa** (fiscal ciclo-corrigido, incerteza, hiato mundial).
- **P6 — Decomposição de inflação** (WP 440) como validação.

## 4. Notas de fidelidade
- Parâmetros numéricos das 24 equações de admin **não são publicados**; a réplica calibra
  repasses nos **alvos de IRF do anexo B9** (1,8 / 1,3 p.p.) e a sazonalidade na série
  oficial — método documentado em `admin_calibrado.py`.
- A réplica não reproduz a cesta oficial de administrados a partir do SIDRA 2020+
  (corr ~0,1) — os itens livres reproduzem a 0,98. Por isso o admin calibrado usa a
  série oficial como alvo, não o agregado SIDRA.
