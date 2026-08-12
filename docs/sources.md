# Fontes de dados

Todas as séries são coletadas por API pública (sem chave). Códigos SGS conferidos ao vivo em 11/08/2026.

## BCB/SGS — `https://api.bcb.gov.br/dados/serie/bcdata.sgs.{código}/dados`

| chave | código | série | uso no modelo |
|---|---|---|---|
| `ipca` | 433 | IPCA — variação mensal (%) | inflação total (identidade) |
| `ipca_12m` | 13522 | IPCA — acumulado 12 meses (%) | validação/análise |
| `ipca_livres` | 11428 | IPCA — itens livres (%) | curva de Phillips |
| `ipca_admin` | 11427 | IPCA — itens administrados (%) | bloco de administrados |
| `ipca15` | 7474 | IPCA-15 mensal (%) | curto prazo / validação |
| `selic_over_aa` | 4189 | Selic over/efetiva anualizada (% a.a.) | regra de Taylor, juro real |
| `selic_meta_acum` | 4390 | Meta Selic acumulada no mês (%) | cenário de juros |
| `cambio_media` | 3696 | PTAX dólar venda — média do período (R$/US$) | UIP, repasse cambial |
| `ibc_br` | 24363 | IBC-Br índice (sem ajuste sazonal) | atividade (proxy PIB) |
| `ibc_br_saz` | 24364 | IBC-Br índice (com ajuste sazonal) | hiato do produto |
| `icbr_indice` | 28515 | IC-Br índice de commodities | pressão externa (Phillips) |
| `icbr_var` | 28451 | IC-Br variação mensal (%) | idem (vintage recente) |
| `nucleo_ex0` | 4466 | Núcleo IPCA por exclusão (EX0) — mensal (%) | análise/validação |
| `embi` | 18621 | EMBI+ Brasil (pontos) | prêmio de risco (UIP) — **indisponível na prática** |

Observações sobre códigos verificados:

- As séries `1` (câmbio fim de período), `11` (Selic acumulada) e `432` (meta Selic) são **diárias** na API atual (exigem janela ≤ 10 anos, retorno 406 sem `dataInicial`/`dataFinal`). Usamos as versões mensais `3696`, `4189`, `4390`.
- O par `11427/11428` é o consistente com o IPCA total (livres + admin com pesos ~76/24). Os códigos `4448/4449` não reproduzem o total — não são usados.
- Série de IC-Br tem duas vintagens: índice antigo (`28515`, ~1990–2019) e variação mensal nova (`28451`, ~2013–2025). A etapa de modelos encadeia as duas.
- Séries de grupo de IPCA em códigos `7060/7165/7170` **foram descontinuadas em 2009**; a setorização vem do SIDRA (tabela 7060).
- **EMBI+ (18621)**: o endpoint retorna 200 com corpo vazio/erros persistentes. O índice foi **descontinuado pelo J.P. Morgan em meados de 2024**, então não há série pública confiável. A série 21619 (que retorna valores estáveis 2–7% por 17 anos) não foi identificada com segurança e **não é usada**. O prêmio de risco na UIP será tratado como termo residual/constante na estimação (documentado como limitação).
- **Focus**: `Selic_trimestrais`, `Selic_12meses` e `Câmbio_12meses` retornam 0 observações — combinações sem dados no serviço (Selic tem o entity set próprio `ExpectativasMercadoSelic`, por reunião do Copom; `12meses` só existe para índices de preço).

## Focus — OLINDA OData

`https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/{endpoint}`

| endpoint | conteúdo |
|---|---|
| `ExpectativasMercadoTrimestrais` | expectativas por trimestre (IPCA, Selic, câmbio) |
| `ExpectativasMercadoAnuais` | expectativas por ano civil |
| `ExpectativasMercadoInflacao12Meses` | expectativa de inflação p/ 12 meses |
| `ExpectativasMercadoMensais` | expectativas por mês |

Filtro por `Indicador` (IPCA, Selic, Câmbio), paginação com `$skip`. A coluna `Data` (data da pesquisa) é a própria data de publicação — o Focus é point-in-time por construção.

## IBGE/SIDRA — `https://apisidra.ibge.gov.br/values/...`

- **Tabela 7060**, variável `63` (IPCA — variação mensal), classificação `c315` (hierarquia: índice geral, grupos, subgrupos, itens, subitens). Dá a base para setorizar preços livres (serviços, bens industriais, alimentação no domicílio) e os itens administrados.
- Pesos e a classificação livre/administrado por subitem são entradas da etapa de modelos (documentadas como artefato de dado, não de coleta).

## NOAA — CPC

`https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt` — ONI (anomalia de temperatura da região Niño 3.4, médias móveis de 3 meses). Proxy para anomalias climáticas na curva de Phillips (safra/in natura).

## FRED — `https://fred.stlouisfed.org/graph/fredgraph.csv`

- `DFF` (Fed Funds efetiva diária) e `FEDFUNDS` (média mensal) — juro externo na UIP.
- `MCOILBRENTEU` (média mensal, US$/barril) — petróleo Brent (canais de administrados).
- `GDPC1` (PIB real) e `GDPPOT` (PIB potencial, CBO) — **hiato do produto dos EUA** como
  proxy do hiato mundial na IS completa (RI dez/2021).
- **Não é fatal**: se o host estiver inacessível, o download registra o erro no manifesto e o restante prossegue. O juro externo pode ser suprido por outra fonte em etapa posterior.

## IBGE/SIDRA — tabelas trimestrais

- **Tabela 5932**, variável `6561`, classificação `11255`, categoria `90707` — PIB a preços de
  mercado, taxa trimestral vs mesmo período do ano anterior (%) — indicador de atividade.
- **Tabela 4099**, variável `4099` — PNAD Contínua, taxa de desocupação (%) — mercado de
  trabalho (hiato multi-indicador).

## ANEEL — dados abertos (bandeiras tarifárias)

`https://dadosabertos.aneel.gov.br/dataset/bandeiras-tarifarias` — CSVs de **Acionamento**
(bandeira ativa por mês + adicional em R$/MWh) e **Adicional** (valores por REH). Fonte do
`modelo-completo/config/bandeiras.csv`, usado no bloco de administrados calibrado
(energia elétrica).

## Fontes documentais do modelo (ver `docs/proveniencia.md` e `docs/referencias/`)

| Fonte | Uso |
|---|---|
| RI dez/2021, boxe b7 (`ri202112b7p`) | **Tabela de priors** do agregado |
| RI set/2020, boxe b7 | Novo modelo agregado bayesiano |
| RI jun/2024, boxes b10–b12 | Hiato (JL), juro real neutra, atualização dos semiestruturais |
| RPM jun/2025, anexo B9 (`rpm202506b9i`) | 24 equações de administrados + IRFs-alvo |
| RI mar/2023, boxe b4 | Sistema de análise e projeções do BC |
| WP 305 (RePEc bcb:wpaper:305) | Preços administrados: projeção e repasse cambial |
| WP 440 (RePEc bcb:wpaper:440) | Decomposição de inflação |

## Não disponível (limitações honestas)

| dado | situação |
|---|---|
| EMBI+ (prêmio de risco) | série descontinuada (JPMorgan, 2024) e endpoint do BCB falho → a UIP é estimada com o prêmio absorvido na constante, documentado como limitação |
| CDS Brasil 5 anos | sem histórico gratuito → mesmo tratamento acima |
| Vintages do IBC-Br | SGS só publica a série corrente → proxy PIT com lag de 45 dias (ver `docs/point-in-time.md`) |
| Pesos oficiais do IPCA por subitem | publicados pelo IBGE fora do SIDRA 7060 → entrada de configuração na etapa de modelos |
| IPCA por subitem (SIDRA 7060) | classificação atual só cobre **2020 em diante**; períodos anteriores usam estrutura antiga — encadeamento na etapa de modelos |
