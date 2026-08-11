# Point-in-time (PIT) — como evitamos "roubo" de informação futura

O objetivo do framework é garantir que **uma projeção feita na vintage `t` só use informação disponível até `t`**. Sem isso, comparar projeção com realizado fica viciado (look-ahead bias).

## Como funciona

1. Toda observação recebe uma coluna `available_from` = data em que ficou pública.
2. O snapshot de uma vintage `t` (ex.: `pt_2026Q2`, cutoff 30/06/2026) guarda apenas as linhas com:
   - `ref_date <= cutoff` (o dado se refere a um período já decorrido), **e**
   - `available_from <= cutoff` (o dado já tinha sido publicado até o cutoff).
3. Modelos leem apenas `data/snapshots/pt_<vintage>/` — a porta PIT é o build.

## Regras de disponibilidade

`config/availability.yaml` define, por série, o lag de publicação. Valor padrão:

```
available_from = fim do período de referência + lag_days
```

| série | lag (dias) | justificativa |
|---|---|---|
| IPCA, IPCA-12m, livres, admin, IPCA-15 | 10 | IBGE divulga ~ dia 8–10 do mês seguinte |
| IBC-Br (24363/24364) | 45 | BCB divulga ~45 dias após o mês de referência |
| IC-Br | 30 | BCB divulga no mês seguinte |
| Selic, câmbio, EMBI+, Fed, ONI | 0 | conhecidos na data de referência |
| Focus | — | `available_from = Data` da pesquisa (publicação) |

Para séries mensais, `ref_date` é o 1º dia do mês e o "fim do período de referência" é o último dia do mês.

## Limitações documentadas

- **IBC-Br sem vintages históricas**: o SGS só publica a série revisada corrente. Usamos a série corrente com lag de 45 dias como **proxy PIT**. Como o IBC-Br é revisado, o hiato estimado em vintages antigas pode diferir levemente do que o BCB via na época. É a única violação parcial conhecida e está marcada em `docs/sources.md`.
- **Focus**: a OLINDA guarda o histórico diário de pesquisas, então é PIT real: pegamos a última pesquisa com `Data <= cutoff` para cada `DataReferencia`.
- **IPCA**: praticamente não é revisado — lag fixo de 10 dias é conservador o suficiente.
- **IC-Br**: tem duas vintagens de definição (índice antigo vs. novo); o encadeamento na etapa de modelos deve ser feito com base apenas nos pontos conhecidos até o cutoff.

## Verificação

- O build reporta, por snapshot, a última `ref_date` de cada série (deve ser ≤ cutoff).
- No início de cada pipeline de modelo deve haver um assert: `max(available_from) <= cutoff`.
