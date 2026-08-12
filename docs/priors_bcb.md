# Priors do modelo agregado — Tabela 1 do RI dez/2021 (boxe b7)

Fonte: Banco Central do Brasil, *Revisão do modelo agregado de pequeno porte*, Relatório de
Inflação, dezembro de 2021 (arquivo `docs/referencias/ri202112b7p_priors_agregado.pdf`,
página 4, Tabela 1). Transcrita em 2026-08-12 (ver `docs/proveniencia.md`).

Estimação bayesiana, **2003T4–2019T4** (excluídos o início do regime de metas — elevada
volatilidade — e o período da pandemia). Premissa declarada pelo BCB: **"priori pouco
restritivas, limitando apenas o suporte"** — isto é, restrição de **sinal e faixa** por
parâmetro, sem ancorar o ponto. Moda e intervalo de credibilidade a 90% a posteriori.

| Equação | Parâmetro | Descrição | Priori (suporte) | Posterior moda | IC 90% |
|---|---|---|---|---|---|
| **Phillips** | α1L | Inércia da inflação de livres | Uniforme [0;1] | 0,23756 | [0,0057;0,3739] |
| | α1I | Inércia da inflação IPCA | Uniforme [0;1] | 0,25568 | [0,0067;0,5743] |
| | α2 | Inflação importada | Uniforme [0;1] | 0,01826 | [0,0008;0,0332] |
| | α3 | Variação do câmbio (desvio da PPC) | Uniforme [0;1] | 0,01727 | [0,0044;0,0312] |
| | α4 | Hiato do produto | Uniforme [0;1] | 0,13866 | [0,0865;0,2127] |
| | α5 | El Niño | Uniforme [0;0,01] | 0,00119 | [0,000461;0,001984] |
| | α6 | La Niña | Uniforme [0;0,01] | 0,00104 | [0;0,002319] |
| **IS** | β1 | Autorregressivo da IS | Uniforme [−2;2] | 0,73897 | [0,6773;0,7959] |
| | β2 | Juro real | Uniforme [0;2] | 0,54876 | [0,3903;0,7204] |
| | β3 | Resultado primário | Beta | 0,02985 | [0,0267;0,0332] |
| | β4 | Incerteza da economia | Beta | 0,04073 | [0,0321;0,0477] |
| | β5 | Hiato mundial | Uniforme [0;1] | 0,04342 | [0;0,0957] |
| **Taylor** | θ1 | Suavização, 1ª defasagem | Uniforme [0;2] | 1,45688 | [1,3873;1,5133] |
| | θ2 | Suavização, 2ª defasagem | Uniforme [−1;1] | −0,54402 | [−0,5987;−0,481] |
| | θ3 | Desvio da expectativa vs meta | Uniforme [0;8] | 1,29981 | [0,8121;1,9078] |
| **Expectativas** | φ1 | Inércia das expectativas | Uniforme [0;1] | 0,73260 | [0,629;0,8277] |
| | φ2 | Expectativa consistente com o modelo | Uniforme [0;1] | 0,12271 | [0,0749;0,1529] |
| | φ3 | Inflação passada | Uniforme [0;1] | 0,04370 | [0,0019;0,0828] |
| **Outras** | δ | Diferencial de juros (UIP) | Uniforme [0;10] | 1,71813 | [0,397;3,196] |
| | γnuci | Proporcionalidade da Nuci (hiato) | Uniforme [0;3] | 2,08871 | [1,8233;2,3782] |
| | γemprego | Proporcionalidade do emprego (hiato) | Uniforme [0;3] | 1,08412 | [0,953;1,2412] |
| | γcaged | Proporcionalidade do Caged (hiato) | Uniforme [0;3] | 0,77959 | [0,6842;0,8809] |

*"As distribuições uniformes são definidas com os limites dos intervalos da distribuição"* (nota do BCB).

## Leitura para a réplica
- **Suportes com sinal imposto** (teoria): inércia e repasse/hiato/commodities/clima em
  [0, ·]; juro real e θ2 e β1 com suporte simétrico onde a teoria é ambígua.
- **Expectativas**: a componente **consistente com o modelo** (φ2 = 0,12) — endogeneidade
  das expectativas — é parte padrão do modelo do BCB (a réplica tem isso só no modo
  `--expect consistent`).
- **Hiato**: quatro indicadores (PIB, Nuci, desocupação, Caged) com coeficientes de
  proporcionalidade (γ) estimados — a réplica usa IBC-Br + PIB + desocupação (Nuci e
  Caged não obtidos).
