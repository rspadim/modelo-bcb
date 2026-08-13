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
| IRF demanda −1 p.p. (hiato) → IPCA 4T | **0,40–0,55 p.p.** (calibrado) | −0,45 p.p. |
| IRF câmbio +10% → admin (4T) | ~1,9 p.p. | ~1,8 p.p. |
| IRF Selic +1 p.p. | **~0,20 p.p.** (transmissão presente) | ~0,26 p.p. (implícito no RI) |
| MAE vs RPM jun/2026 | **~0,58 p.p.** (expectativas híbridas) | — |
| Balanço de riscos P(fora [1,5;4,5]) | ~1,0 no curto (2026Q3-Q4) → 0,02 (2028) | ~0,79 (2026) |
| Backtest integrado (29 vintages PIT) | MAE 1T **0,75** · geral **1,96** p.p. | — |
| Juro real neutra (estado) | média ~5% | ~3,6% (2021) |

> **Notas de método (P1–P4, "o mais próximo do BCB")**:
> - **Calibração ao RI (default)**: `a4=0,14`, `a2=0,018`, `b1=0,74` (β1 do RI — destrava
>   a transmissão) e hiato resscalado (~±1%). `--sem-calibrar` mantém os estimados.
> - **Transmissão monetária**: `b2=0,55` (β2 do RI) **diverge** com o juro real atual
>   (~10% vs neutra ~5) — o hiato vai a −39. Gate de estabilidade usa **b2=0,15**:
>   Selic IRF ~0,20 (consistente com os ~0,26 p.p. implícitos no RI). β2=0,55 não é
>   alcançável de forma estável — documentado como teto do cenário público.
> - **Setorial**: `--nivel setorial` (3 Phillips 2020+), hiato setorial calibrado 0,14.
> - **Fan chart + balanço de riscos** do integrado (incerteza da posterior).
> - **Convergência**: R-hat > 1,05 em `rbar`/`ldesoc` — aumentar tune ajuda.
> - **Expectativas**: φ2 fixado no RI (0,12), φ1/φ3 com priors; projeção híbrida ancorada.
> - **PIT**: auditado (sem `bfill`, sem `pt_latest`, FRED trimestral corrigido).

> A convergência para o BCB "oficial" esbarra em três fronteiras que não são de modelagem:
> dados (Nuci/Caged, CDS, vintages), julgamento de especialistas e parâmetros internos
> não publicados. O que é reproduzível está sendo aproximado estruturalmente e validado
> pelas IRFs do RI.
