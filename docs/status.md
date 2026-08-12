# Status — o que é e o que ainda não é o modelo BCB nesta réplica

**Leia primeiro**: este repositório é uma *réplica pública em construção* do Modelo de
Pequeno Porte (MPP) do Banco Central do Brasil. O **único** componente chamado de
"modelo BCB" é o **modelo integrado** (`modelo-integrado/`). As versões parciais
anteriores (`modelo-agregado/` e `modelo-completo/`) foram **removidas** — seus números
ficam registrados como histórico em `docs/validacao.md`.

## O que o modelo integrado reproduz (estrutura do RI dez/2021, boxe b7)

| Componente | Status |
|---|---|
| Hiato do produto como estado latente (AR com dinâmica da IS) | ✓ conjunta plena (PyMC) |
| Juro real neutra como estado latente (passeio aleatório) | ✓ conjunta plena |
| Phillips de livres (inércia + expectativas + importada IC-Br R$ + câmbio PPC + hiato + clima assimétrico) | ✓ |
| Expectativas com componente consistente com o modelo (φ2) | ✓ (resolvidas por fixed-point) |
| Bloco de administrados calibrado (anexo B9, regras institucionais) | ✓ (`--admin calibrado` no legado; endógeno no integrado via equação OLS) |
| IS com fiscal ciclo-corrigido, incerteza, hiato mundial (proxy EUA) | ✓ |
| UIP / Taylor | ✓ |
| Decomposição de inflação (WP 440) | ✓ |

## O que ainda NÃO é o modelo BCB (limites de dados/método, documentados)

1. **Estimação conjunta plena**: implementada (PyMC), mas os parâmetros finais dependem de
   convergência e de priors — o BCB usa priors de anos de experiência; a réplica usa os
   suportes publicados do RI dez/2021.
2. **Nuci (FGV) e Caged (MTE)**: indisponíveis via API pública → o hiato usa IBC-Br + PIB +
   desocupação (4 indicadores do BCB não reproduzíveis).
3. **Prêmio de risco (CDS 5 anos)**: sem série pública confiável → absorvido na constante da UIP.
4. **Julgamento de especialistas de curto prazo** (livres ~2T, admin ~5T): não replicável.
5. **Parâmetros numéricos das 24 equações de administrados**: não publicados → calibrados
   nos alvos de IRF do anexo B9 (câmbio +10% → admin ≈ +1,8 p.p.; petróleo +10% → ≈ +1,3 p.p.).
6. **Vintages reais do IBC-Br**: indisponíveis → proxy PIT com lag documentado.
7. **Fan chart**: incerteza de parâmetro (posterior) + resíduos — o BCB calibra o leque com
   julgamento.

## Fidelidade medida (validação vs PDF)

| Validação | Réplica integrada | Alvo (BCB) |
|---|---|---|
| IRF demanda −1 p.p. (hiato) → IPCA 4T | ~0,25 p.p. (híbrido) / ~0,6 (consistente) | −0,45 p.p. |
| IRF câmbio +10% → admin (4T) | ~1,9 p.p. | ~1,8 p.p. |
| IRF Selic +1 p.p. | ~0,02 p.p. (transmissão fraca) | não nula |
| MAE vs RPM jun/2026 | **~0,50 p.p.** (expectativas híbridas) | — |
| Juro real neutra (estado) | média ~5% | ~3,6% (2021) |
| Decomposição 2024 (importada) | ~0,0 (canal fraco na amostra pública) | 0,72 p.p. |
| Backtest integrado (29 vintages PIT) | MAE 1T **0,75** · geral **1,96** p.p. | — |

> **Notas de estabilidade/PIT** (auditoria agressiva):
> - **Expectativas**: o componente consistente (φ2) NÃO é estimado com `pi.shift(-1)`
>   (look-ahead de 1T); φ2 é fixado no valor do RI (0,12) e φ1/φ3 são estimados com
>   priors ancorados no RI. A projeção usa por padrão **expectativas híbridas ancoradas
>   à meta** (`--expect hybrid`, estável); o modo `--expect consistent` (fixed-point φ2)
>   diverge neste modelo (hiato quase unitário, b1≈0,93) — documentado.
> - **Escala do hiato (P1)**: reestimação com crescimento potencial latente + loading
>   `gibc` + prior em σ_g NÃO reduziu a amplitude do ciclo (~±6% vs ~±1% do BCB); os
>   dados públicos identificam o hiato com essa amplitude. Consequência: a4 (~0,06 vs
>   0,14) e b2 (~0,02 vs 0,55) e as IRFs de demanda/Selic ficam abaixo do RI — teto
>   honesto da reestimação sem os dados internos do BCB.
> - **Convergência**: a conjunta plena roda no Docker (g++, ~1 min p/ 400/300); R-hat >
>   1,05 apenas no estado `rbar` (juro neutra) — aumentar tune ajuda.

> A convergência para o BCB "oficial" esbarra em três fronteiras que não são de modelagem:
> dados (Nuci/Caged, CDS, vintages), julgamento de especialistas e parâmetros internos
> não publicados. O que é reproduzível está sendo aproximado estruturalmente e validado
> pelas IRFs do RI.
