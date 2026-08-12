# Equações do modelo — réplica do Modelo de Pequeno Porte do BCB

Documento de referência da implementação. As especificações seguem as publicações
do Banco Central do Brasil (RPM/RI e seus anexos), descritas abaixo. O que **não**
foi possível determinar a partir das fontes públicas está marcado como "não
determinável".

Fontes principais:

- *Atualização dos modelos semiestruturais de pequeno porte* — RI de junho/2024 (anexo B12).
- *Atualização do modelo para projeção de médio prazo dos preços administrados* — RPM de junho/2025 (anexo B9, 24 equações).
- Relatório de Política Monetária (RPM) — cenários, condicionantes e projeções oficiais.

---

## 1. Modelo agregado

### 1.1 Curva de Phillips — preços livres

```
π^L_t = c + φ1·π^L_{t-1} + (1−φ1)·E_t[π_{t+1}] + φ2·ĥ_{t-1} + φ3·Δe_t + φ4·π^com_t + φ5·ONI_t + ε
```

- `π^L`: variação trimestral dos preços livres (SGS 11428).
- `E_t[π_{t+1}]`: expectativa Focus (trimestral, composta do Focus mensal), última
  pesquisa ≤ cutoff para o trimestre-alvo.
- `ĥ`: hiato do produto. No modelo agregado, filtro HP (λ=1600) sobre log(IBC-Br saz).
- `Δe`: variação do câmbio nominal (PTAX média, SGS 3696).
- `π^com`: variação do índice de commodities (IC-Br; encadeamento 28515 → 28451).
- `ONI`: anomalia climática (Oceanic Niño Index, NOAA) — proxy para choques de safra.
- A restrição novo-keynesiana (soma de inércia e expectativa = 1) é imposta na estimação.

### 1.2 Curva IS

```
ĥ_t = c + β1·ĥ_{t-1} + β2·ĥ_{t-2} − β3·(r_{t-1} − r̄*) + β4·Δe_t + β5·fisc_t + ε
```

- `r = Selic − 4·E_t[π_{t+1}]` (juro real ex-ante aproximado).
- `fisc`: resultado primário do setor público % PIB (acum. 12m, SGS 10844).
- **Não determinável nas fontes**: hiato externo (não há série pública simples de
  hiato do mundo) — termo omitido e documentado.

### 1.3 Regra de Taylor

```
i_t = c + ρ1·i_{t-1} + ρ2·i_{t-2} + γ·(E_t[π_{t+1}] − meta) + ε
```

- Sem termo de hiato, conforme nota do BCB (estimação conjunta de 2024 registra que
  o coeficiente do hiato não foi identificado).
- `meta`: meta de inflação (CMN; contínua 3% desde 2025, histórico em `src/meta.py`).

### 1.4 Paridade descoberta de juros (UIP)

```
Δe_t = c + δ·(i_{t-1} − i*_{t-1}) + ε
```

- `i*`: Fed Funds (FRED FEDFUNDS).
- **Não determinável**: prêmio de risco explícito (EMBI+ descontinuado; CDS sem
  histórico gratuito). O prêmio é absorvido na constante — limitação documentada.

### 1.5 Curva de expectativas

```
E_t[π_{t+1}] = c + λ1·E_{t-1}[π_t] + λ2·π_{t-1} + ε
```

Na projeção, a expectativa converge gradualmente à meta (0,8·E + 0,2·meta/4 por
trimestre), em linha com o tratamento de ancoragem dos modelos do BCB.

### 1.6 Preços administrados (agregado)

```
π^A_t = c + γ1·π^A_{t-1} + γ2·π^L_{t-1} + γ3·Δe_t + ε
```

### 1.7 Identidade

```
π_t = w·π^L_t + (1−w)·π^A_t        (w ≈ 0,76; configurável)
```

---

## 2. Modelo completo (desagregado)

### 2.1 Setorização da inflação livre

A inflação livre é decomposta em **serviços**, **bens industriais** e **alimentação
no domicílio**, a partir dos subitens do IPCA (SIDRA tabela 7060, variação v=63 e
peso v=66):

- Classificação de cada subitem em admin/serviços/industriais/alimentação por
  regras de nome e grupo (`src/sector.py`).
- Agregação ponderada mensal → trimestral.
- **Validação**: a série de livres setorial reproduz a série oficial (SGS 11428)
  com correlação 0,98 e desvio médio < 0,05 p.p.
- **Limitação**: o SIDRA (classificação atual) cobre apenas 2020 em diante;
  períodos anteriores usam outra estrutura de classificação (não obtida).

### 2.2 Phillips setoriais (3 equações)

```
π^j_t = c_j + φ1_j·π^j_{t-1} + (1−φ1_j)·E_t[π_{t+1}] + φ2_j·ĥ_{t-1} + φ3_j·Δe_t + φ4_j·π^com_t + φ5_j·ONI_t + ε
```
para j ∈ {serviços, bens industriais, alimentação no domicílio}, com restrição
novo-keynesiana e pesos na identidade:

```
π^L_t = w_serv·π^serv + w_ind·π^ind + w_alim·π^alim   (pesos em fração dos livres)
```

### 2.3 Hiato do produto e juro neutro (estado-espaço)

- **Estágio 1**: decomposição do log(IBC-Br saz) em tendência local + ciclo
  amortecido (AR) via `UnobservedComponents` (filtro de Kalman). O ciclo é o hiato.
  **Alternativa multi-indicador** (`--gap multi`): fator comum de Δlog(IBC-Br),
  PIB trimestral (crescimento YoY, SIDRA 5932) e desocupação (PNAD Contínua, SIDRA
  4099) via `DynamicFactor`, calibrado à escala do hiato em %. Na amostra curta o
  fator é dominado pelo IBC-Br (corr ~1,0 com o ciclo univariado).
- **Estágio 2**: as demais equações são estimadas condicionadas ao hiato suavizado.
- **Estimação bayesiana conjunta** (`--est bayes`, `src/bayes.py`): Phillips
  setoriais + IS + admin estimadas juntas no PyMC, com priors informativos
  centrados no OLS; **repasse cambial imposto positivo** (HalfNormal) e **prior
  informativo do hiato na Phillips** (N(0,4; 0,3), evitando coeficientes explosivos
  da amostra curta). Taylor/UIP/expectativas permanecem do OLS.
- O BCB desde 2020 estima hiato e juro neutro como latentes conjuntamente; a réplica
  trata o hiato em estágio separado (documentado) e usa o juro neutro de 5,0% do
  cenário do RPM como referência nas simulações.

### 2.4 Bloco de preços administrados — 24 equações (anexo B9 do RPM jun/2025)

Estrutura geral por item: indexação à inflação passada (IPCA acum. 4T), repasse de
câmbio e de petróleo (em reais), e componentes institucionais de reajuste. Itens
com regra sazonal de reajuste usam dummies trimestrais; os demais usam a forma:

```
π^item_t = c + α1·π^item_{t-1} + α2·IPCA4_{t-1} + α3·Δpetróleo_{t}(R$) + α4·Δe_t + dummies + ε
```

Itens (código SIDRA e peso no IPCA, maio/2025):

| # | Item | Código | Peso % | Mecanismo principal |
|---|---|---|---|---|
| 1 | Gasolina | 5104001 | 5,24 | petróleo (R$) + margem |
| 2 | Plano de saúde | 6203 | 4,06 | IVDA/ANS (reajuste anual) |
| 3 | Energia elétrica residencial | 2202003 | 3,78 | reajuste ANEEL + bandeiras + câmbio (Itaipu ~8%) |
| 4 | Produtos farmacêuticos | 6101 | 3,46 | tabela CMED/Anvisa (IPCA12m + Fator Y) |
| 5 | Emplacamento e licença | 5102004 | 2,69 | inflação passada / 4, 1º trimestre |
| 6 | Taxa de água e esgoto | 2101004 | 1,84 | reajuste regulado |
| 7 | Gás de botijão | 2201004 | 1,25 | petróleo (R$) + margem (dissídio no 3ºT) |
| 8 | Ônibus urbano | 5101001 | 1,12 | inflação passada |
| 9 | Jogos de azar | 7201063 | 0,44 | inflação passada |
| 10 | Ônibus intermunicipal | 5101006 | 0,41 | inflação passada |
| 11 | Óleo diesel | 5104003 | 0,25 | petróleo (R$) + margem |
| 12 | Plano de telefonia fixa | 9101002 | 0,22 | regulado |
| 13 | Táxi | 5101002 | 0,20 | inflação passada |
| 14 | Gás encanado | 2201005 | 0,15 | inflação + petróleo (R$) + gás de botijão |
| 15 | Ônibus interestadual | 5101007 | 0,11 | inflação passada |
| 16 | Multa | 5102006 | 0,088 | inflação passada |
| 17 | Pedágio | 5102015 | 0,087 | inflação passada |
| 18 | Gás veicular | 5104005 | 0,070 | inflação + petróleo (R$) + gasolina |
| 19 | Metrô | 5101011 | 0,066 | inflação passada |
| 20 | Correio | 9101001 | 0,065 | inflação passada |
| 21 | Integração transporte público | 5101053 | 0,052 | inflação passada |
| 22 | Conselho de classe | 7101090 | 0,048 | inflação passada / 4, 1º trimestre |
| 23 | Trem | 5101004 | 0,038 | inflação passada |
| 24 | Cartório | 7101034 | 0,023 | inflação passada |

**Não determinável nas fontes**: os parâmetros numéricos das 24 equações (o anexo
B9 apresenta as equações em notação matemática/imagens, sem os valores estimados);
a projeção do IVDA (julgamento do especialista do BCB) e das bandeiras tarifárias.
Na réplica, esses itens são tratados com a estrutura de indexação acima e dados de
subitem do SIDRA (2020+) — ver `modelo-completo/src/sector.py`.

**Implementação na réplica — calibrada como o BCB** (`modelo-completo/src/admin_calibrado.py`,
`--admin calibrado`, default): o BCB deixa explícito que as equações de administrados **não
são estimadas, mas calibradas** com base no arcabouço institucional ("not estimated
equations, but calibrated equations based on the current institutional framework" — RPM
jun/2025, anexo B9). A réplica implementa a estrutura por regra (energia ANEEL + bandeira +
Itaipu/câmbio; medicamentos CMED; plano de saúde ANS/IVDA; combustíveis petróleo(R$)+ICMS
no 1ºT; GLP margem no 3ºT; transportes/água/telecom indexados), calibra os **repasses de
câmbio e petróleo nos alvos de IRF do próprio anexo** (câmbio +10% → admin ≈ +1,8 p.p. em
4T; petróleo +10% → ≈ +1,3 p.p.) e ajusta sazonalidade + indexação à série oficial
(SGS 11427). `admin24.py` (estimação OLS por item) permanece como módulo de referência.
**Limitação documentada**: o agregado de administrados a partir do SIDRA 2020+ não reproduz
a cesta oficial (corr ~0,1); por isso o agregado calibrado usa a série oficial como alvo.

### 2.5 Expectativas consistentes com o modelo (fixed-point)

Disponível em `run_complete.py --expect consistent`: itera o sistema até
`E_t[π_{t+1}] = π_{t+1}` projetado (ancoragem terminal na meta). Nas Phillips
setoriais de amostra curta o equilíbrio auto-realizável fica alto (MAE 1,54 vs
0,59 do híbrido); o modo padrão ancorado à meta (0,8·E + 0,2·meta/4) acompanha
melhor o RPM e permanece o default.

---

## 3. Condicionantes do cenário de referência (RPM jun/2026)

Transcritos em `modelo-agregado/config/rpm_2026q2.yaml`:

- IPCA acumulado 4T por trimestre (2025Q2–2028Q4) — Tabela 2.2.1 do RPM.
- IPCA livres e administrados (idem).
- Selic (pesquisa Focus): 13,75% fim/2026 · 12,00% fim/2027 · 10,25% fim/2028.
- Câmbio: parte de R$ 5,10/US$ e segue PPC (~1% a.a.).
- Petróleo Brent: US$ 100 em 2026Q2 → US$ 85 em 2027Q1 → +2% a.a.
- Juro real neutra: 5,0%. Meta: 3,0% (±1,5 p.p.). El Niño forte (RONI 2,1 °C em 2026Q4).

**Wiring no sistema** (`rpm.py::scenario_path` + `system.py::forecast(scenario=...)`):
a projeção do modelo completo agora condiciona **câmbio (PPC), Brent, ONI/RONI e
juro real neutra** ao cenário, além da Selic (Focus). O hiato do cenário do Copom
(0,5% em 2026Q1) é referência, não restrição.
