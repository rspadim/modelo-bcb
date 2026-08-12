# 🇧🇷 Modelo BCB — réplica do Modelo de Pequeno Porte em Python

**Reconstrução pública do modelo de projeção de inflação do Banco Central do Brasil (MPP)**, com dados point-in-time, equações estimadas, backtest e comparação com o cenário oficial.

> **⚠️ Status — leia antes de usar**
> Esta é uma **réplica em construção**. O **único "modelo BCB"** é o **modelo integrado**
> (`modelo-integrado/`, estimação bayesiana conjunta: hiato + juro neutra latentes +
> Phillips/IS/expectativas). `modelo-agregado/` e `modelo-completo/` são **experimentos
> legado** (aproximações parciais). Veja [`docs/status.md`](docs/status.md) para o que é
> e o que ainda **não** é o modelo BCB.

![Fan chart — modelo vs cenário oficial](docs/figures/fan_chart.png)

> **MAE de 0,20 p.p. contra o cenário oficial do RPM jun/2026** (11 trimestres) — a projeção oficial cai **dentro do leque de 50% do modelo em todos os trimestres**.

---

## 📊 Números principais

| Métrica | Resultado |
|---|---:|
| MAE vs cenário oficial (RPM jun/2026, 11 trimestres) | **0,20 p.p.** |
| Diferença no 1º trimestre (2026Q2) | −0,26 p.p. |
| Cenário oficial dentro do leque 50% do modelo | **11/11** |
| Backtest (29 vintages, 2019–2026) — MAE médio | **1,83 p.p.** |
| Benchmark naive (persistência) — MAE médio | 2,84 p.p. |
| Setorização (livres setorial vs oficial) | **corr 0,98** |
| Long horizon recursivo — MAE 1T / 4T à frente | 0,67 / 2,07 p.p. |

---

## O que é

O Banco Central publica a **estrutura** do seu Modelo de Pequeno Porte (curva de Phillips, IS, regra de Taylor, paridade de juros, expectativas e o bloco de 24 equações de preços administrados), mas não divulga código nem a base tratada. Este repositório reconstrói esse modelo **a partir das fontes documentais do BCB** e valida contra as projeções oficiais.

- **Dados 100% via API pública** (BCB/SGS, Focus, IBGE/SIDRA, NOAA, FRED), com framework **point-in-time** que impede vazamento de informação futura (auditado).
- **Dois modelos**: agregado (Phillips única) e completo (3 Phillips setoriais + estado-espaço).
- Tudo reproduzível e auditável.

## Modelos

![Componentes — livres vs administrados e setores](docs/figures/componentes.png)

| Modelo | Descrição | Status |
|---|---|---|
| **Integrado** ⭐ | Estimação bayesiana conjunta (hiato + juro neutra latentes + Phillips/IS/expectativas) + admin endógeno + expectativas consistentes | **o modelo BCB da réplica** |
| Agregado | Phillips livre + IS + Taylor + UIP + admin + hiato HP (MAE vs RPM **0,20 p.p.**) | experimento legado |
| Completo | 3 Phillips setoriais + admin calibrado (B9) (MAE **0,46 p.p.**) | experimento legado |

O modelo integrado é o alvo; os legados servem de diagnóstico e referência. Reprodução: `python modelo-integrado/scripts/run_integrado.py`.

\* Amostra setorial limitada a 2020+ (SIDRA) — menor robustez, documentado.

![Hiato do produto](docs/figures/hiato.png)

![Fan chart paramétrico (incerteza da posterior)](docs/figures/fan_chart_parametrico.png)

## Validação

**Backtest** — para cada vintage (2019Q1–2026Q1), o modelo é re-estimado com dados disponíveis até lá e projeta 12 trimestres. O modelo ganha do benchmark naive em quase todos os horizontes:

![MAE por horizonte — modelo vs naive](docs/figures/backtest_horizonte.png)

**Long horizon** — projeção recursiva modelo vs realizado:

![Modelo vs realizado](docs/figures/longhorizon.png)

**Setorização** — preços livres setorial vs oficial (corr 0,98):

![Setorização](docs/figures/setorizacao.png)

## 🐳 Abre e usa (Docker)

```bash
# 1. Reproduz tudo (dados → snapshots → modelos → figuras → resumo)
docker compose run pipeline

# 2. Dashboard interativo
docker compose up dashboard   # abre http://localhost:8501
```

Sem Docker, basta `pip install -r requirements.txt` e:

```bash
python main.py                 # pipeline completo + resumo
python scripts/make_figures.py # figuras da documentação
streamlit run dashboard/app.py # dashboard
```

Modelo fiel ao BCB (RI dez/2021): `python modelo-agregado/scripts/run_bcb.py`.

## Como funciona (fluxo)

```
dados brutos (SGS · Focus · SIDRA · NOAA · FRED)
      ↓  point-in-time (available_from por observação)
snapshots por trimestre (pt_2019Q1 … pt_2026Q2)
      ↓
trimestralização + hiato (HP / Kalman)
      ↓
estimação das equações (OLS)
      ↓
sistema simultâneo → projeção 12T → fan chart (Monte Carlo)
      ↓
validação vs cenário oficial (RPM) · backtest rolante · long horizon
```

## Documentação

- [📄 Relatório completo](docs/relatorio.md) — todas as figuras, tabelas e limitações.
- [🚦 Status — o que é e o que não é o modelo BCB](docs/status.md) — **leia primeiro**.
- [📐 Equações](docs/equacoes.md) — especificação + bloco de administrados (anexo B9).
- [🛡 Validação](docs/validacao.md) — metodologia, métricas e auditoria point-in-time.
- [🏛 Modelagem no BCB × réplica](docs/modelagem_bcb.md) — auditoria de lacunas e roadmap.
- [🧬 Priors do BCB (RI dez/2021)](docs/priors_bcb.md) — tabela transcrita.
- [🗂 Fontes de dados](docs/sources.md) · [⏱ Point-in-time](docs/point-in-time.md) · [🏗 Arquitetura](docs/arquitetura.md) · [🔍 Proveniência](docs/proveniencia.md)

## Limitações honestas

- **IC-Br** com lacuna 2024H2–2025Q3 → Phillips estimada até 2024Q2.
- **Prêmio de risco** (EMBI+/CDS) sem histórico público → absorvido na constante da UIP.
- **Repasse cambial**: negativo no OLS (apreciação 2021–23 confunde a amostra); a
  estimação **bayesiana com prior positivo** corrige o sinal (IRF +0,46 p.p. em 4T).
- **Admin calibrado (B9)**: estrutura por regra com repasses nos alvos de IRF do anexo
  (câmbio +1,87 / petróleo +1,31 p.p.); o agregado SIDRA de admin não reproduz a cesta
  oficial (~0,1) — o calibrado usa a série oficial como alvo.
- **Canal de inflação importada fraco** na Phillips do RI (coef ~0 na amostra pública) —
  a decomposição de 2024 atribui menos à importada (0,0 vs 0,72 do ofício 374) e mais ao
  residual; documentado.
- **Hiato externo**, **pesos pré-2020**, **Nuci/Caged** e **priors numéricos das 24
  equações de admin** não determináveis nas fontes públicas.

Detalhes e números atualizados em [`docs/validacao.md`](docs/validacao.md).

---

*Implementação e documentação baseadas exclusivamente em publicações do Banco Central do Brasil (RPM/RI e anexos). Não é código oficial do BCB.*
