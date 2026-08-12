# Status — o que é e o que ainda não é o modelo BCB nesta réplica

**Leia primeiro**: este repositório é uma *réplica pública em construção* do Modelo de
Pequeno Porte (MPP) do Banco Central do Brasil. O **único** componente chamado de
"modelo BCB" daqui em diante é o **modelo integrado** (`modelo-integrado/`). As pastas
`modelo-agregado/` e `modelo-completo/` são **experimentos/legado** — aproximações
parciais que serviram para fechar peças, mas **não** são o modelo BCB.

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
| IRF demanda −1 p.p. (hiato) → IPCA 4T | ~0,38 p.p. | −0,45 p.p. |
| IRF câmbio +10% → admin (4T) | ~1,9 p.p. | ~1,8 p.p. |
| MAE vs RPM jun/2026 | ~0,7 p.p. (sensível a amostras) | — |
| Juro real neutra (estado) | média ~5%, fim ~5-6% | ~3,6% (2021) |
| Decomposição 2024 (importada) | ~0,0 (canal fraco na amostra pública) | 0,72 p.p. |

> A convergência para o BCB "oficial" esbarra em três fronteiras que não são de modelagem:
> dados (Nuci/Caged, CDS, vintages), julgamento de especialistas e parâmetros internos
> não publicados. O que é reproduzível está sendo aproximado estruturalmente e validado
> pelas IRFs do RI.
