# Modelo BCB — réplica do Modelo de Pequeno Porte em Python

Reconstrução pública do **modelo semiestrutural de pequeno porte (MPP) do Banco Central do Brasil**, em Python, com dados coletados por API e um framework **point-in-time** que impede vazamento de informação futura nas projeções.

Reconstruído **diretamente das fontes documentais do BCB** (Relatório de Política Monetária e seus anexos — especificação do modelo e das equações) e validado contra as projeções oficiais publicadas.

## Estrutura

```
modelo-bcb/
├── downloader/            # coleta e preparação dos dados (compartilhada)
│   ├── config/            # códigos SGS, regras PIT, settings
│   ├── src/               # clientes: SGS, Focus, SIDRA, FRED, NOAA + motor PIT
│   ├── scripts/           # 01_download.py · 02_build_dataset.py
│   └── data/              # raw/ (cache) · processed/ · snapshots/pt_<YYYYQn>/
├── modelo-agregado/       # réplica agregada — valida esqueleto + projeção
├── modelo-completo/       # 3 Phillips setoriais + 24 eq. admin + Kalman
└── docs/                  # documentação
```

## Pipeline

```
01_download.py        → baixa/atualiza data/raw (idempotente)
02_build_dataset.py   → data/processed/series.parquet + snapshots point-in-time
modelo-agregado       → hiato + equações + projeção + fan chart + comparação RPM
modelo-completo       → versão desagregada + Kalman + backtest rolante
```

### Uso

```bash
pip install -r downloader/requirements.txt

python downloader/scripts/01_download.py
python downloader/scripts/02_build_dataset.py
```

Reexecutar mais tarde atualiza a pasta de dados: o download só busca o que está desatualizado (janela de cache em `config/settings.yaml`) e o build regenera os snapshots.

## Point-in-time (anti-vazamento)

Cada observação carrega `available_from` (data em que ficou pública). Os snapshots são cortados por `ref_date <= cutoff` **e** `available_from <= cutoff`, então uma projeção feita na vintage `2026Q2` só vê o que existia até 30/06/2026. Regras em `downloader/config/availability.yaml` e detalhes em `docs/point-in-time.md`.

## Fontes de dados

| Fonte | Endpoint | Séries |
|---|---|---|
| BCB/SGS | `api.bcb.gov.br` | IPCA, livres/admin, IBC-Br, Selic, câmbio, IC-Br, EMBI+ |
| Focus | OLINDA OData | expectativas de mercado (IPCA, Selic, câmbio) |
| IBGE/SIDRA | `apisidra.ibge.gov.br` | IPCA por subitem (setorização) |
| NOAA | CPC | ONI (El Niño/La Niña) |
| FRED | `fred.stlouisfed.org` | Fed Funds (melhor esforço) |

Catálogo completo em `docs/sources.md`.

## Estado

- [x] Documentação (arquitetura, fontes, point-in-time, equações, validação)
- [x] Coleta e pipeline point-in-time (download + snapshots)
- [x] Modelo agregado (hiato HP + OLS + fan chart + comparação RPM + backtest rolante)
- [x] Modelo completo (3 Phillips setoriais + bloco de 24 admin documentado + estado-espaço/Kalman + repasse cambial)
- [x] Benchmark vs realizado + Focus + naive
- [x] Auditoria point-in-time / look-ahead bias (correções aplicadas — ver `docs/validacao.md`)
- [ ] Transcrição completa dos RPMs históricos (esquema em `config/rpm_historico.csv`, pendente)
- [ ] IpeaData (setoriais longas) — endpoint instável; setorial usa SIDRA 2020+

## Resultados principais (resumo)

- **Aderência ao RPM jun/2026** (modelo agregado): MAE **0,20 p.p.** (11 trimestres),
  projeção oficial dentro do leque de 50% em todos os trimestres sobrepostos.
- **Backtest rolante** (2019Q1–2026Q1, 29 vintages): MAE médio **1,83 p.p.** vs
  benchmark naive **2,84 p.p.** (viés −0,77 p.p.).
- **Setorização validada**: livres setorial vs oficial com correlação 0,98.
- **Modelo completo (setorial, 2020+)**: MAE **1,07 p.p.** — amostra curta limita a
  robustez das Phillips setoriais (documentado).
- Detalhes e limitações honestas em `docs/validacao.md`.

## Fontes de referência da implementação

A especificação do modelo (equações, variáveis, estrutura) vem exclusivamente dos documentos do BCB:

- Relatório de Política Monetária (RPM) — cenários e projeções oficiais.
- Anexos dos RPM/RI: atualização dos modelos semiestruturais de pequeno porte e o modelo de preços administrados (24 equações).

Ver `docs/equacoes.md` e `docs/validacao.md`.

## Notas de implementação (o que descobrimos ao vivo)

- SGS `1`/`11`/`432` são séries **diárias** na API atual (pedem janela ≤10 anos); usamos as mensais `3696`/`4189`/`4390`.
- OLINDA (Focus) rejeita codificação `+` do `requests` — a URL precisa ser montada manualmente com `%20`/`%27`, e `$top` grande (10 000) para paginação eficiente.
- `ExpectativaMercadoMensais` é **singular**; `ExpectativasMercadoMensais` não existe.
- EMBI+ (18621) está indisponível (índice descontinuado em 2024); limitação documentada.
