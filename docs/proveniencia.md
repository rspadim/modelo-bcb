# Proveniência — conversões PDF → MD e especificação do modelo como dado point-in-time

Este documento registra, para cada **transcrição** de documentos do Banco Central do Brasil
para este repositório: a fonte exata, o método de conversão, a data, o status de verificação
e a fidelidade. Também trata a **especificação do modelo como dado point-in-time**: priors,
regras de calibração e cenários são "vintages" da publicação do BCB — ao reestimar numa
vintage `t`, usa-se a especificação com `available_from ≤ t` (análogo ao `available_from`
das séries econômicas), e o código avisa quando há vazamento de especificação.

Os PDFs-fonte ficam em [`docs/referencias/`](referencias/). O manifesto máquina de
especificações e o check estão em `modelo-completo/config/spec_manifesto.yaml` e
`modelo-completo/src/spec_manifesto.py`.

---

## 1. Referências baixadas (docs/referencias/)

| Arquivo | Publicação | Disponível (available_from) | Conteúdo |
|---|---|---|---|
| `ri202112b7p_priors_agregado.pdf` | RI dez/2021 | 2021-12-31 | **Tabela de priors** do modelo agregado + especificação |
| `ri202009b7p_novo_modelo_bayesiano.pdf` | RI set/2020 | 2020-09-30 | Novo modelo agregado bayesiano |
| `ri202406b10p_hiato.pdf` | RI jun/2024 | 2024-06-28 | Medidas de hiato (Jarociński-Lenza, componentes principais) |
| `ri202406b11p_juro_neutra.pdf` | RI jun/2024 | 2024-06-28 | Medidas de juro real neutra |
| `ri202406b12p_semiestruturais.pdf` | RI jun/2024 | 2024-06-28 | Atualização dos modelos semiestruturais |
| `rpm202506b9i_admin_24_equacoes.pdf` | RPM jun/2025 | 2025-06-30 | **24 equações de administrados** + IRFs |
| `ri202303b4p_sistema_projecoes.pdf` | RI mar/2023 | 2023-03-31 | Sistema de análise e projeções do BC |
| `aneel_Bandeira_Tarifária_-_Acionamento.csv` | ANEEL (dados abertos) | — | Acionamento mensal da bandeira (2015→) |
| `aneel_Bandeira_Tarifária_-_Adicional.csv` | ANEEL (dados abertos) | — | Valores dos adicionais (R$/MWh) por REH |

Working papers (não baixados, referência em `docs/sources.md`): **WP 305** (Preços
Administrados: projeção e repasse cambial), **WP 440** (Decomposição de inflação).

## 2. Transcições registradas

### 2.1 Tabela de priors (RI dez/2021, boxe b7) → `docs/priors_bcb.md`
- **Fonte**: `ri202112b7p_priors_agregado.pdf`, página 4, **Tabela 1 – Parâmetros estimados**.
- **Método**: extração automática de texto (pdfplumber) + revisão manual dos números.
- **Transcrito em**: 2026-08-12 · **Verificação**: moda e intervalo de credibilidade a 90%
  conferidos contra o PDF; suportes das priors copiados literalmente.
- **Fidelidade**: valores numéricos preservados; fórmulas matemáticas não transcritas
  (presentes no PDF). Notas de rodapé do BCB (ex.: "as distribuições uniformes são
  definidas com os limites dos intervalos") mantidas.

### 2.2 Regras das 24 equações de administrados (RPM jun/2025, anexo B9) → `docs/modelagem_bcb.md` + `admin_calibrado.py`
- **Fonte**: `rpm202506b9i_admin_24_equacoes.pdf` (versão em inglês), páginas 1–8.
- **Método**: extração de texto (pdfplumber) + revisão manual das regras institucionais.
- **Transcrito em**: 2026-08-12 · **Verificação**: regras conferidas contra o texto
  (energia/ANEEL+Itaipu+bandeiras, CMED, ANS/IVDA, combustíveis/ICMS no 1ºT, etc.).
- **Fidelidade**: **parâmetros numéricos das 24 equações NÃO são publicados** pelo BCB
  (o anexo traz as equações em notação/imagens). A réplica implementa a ESTRUTURA
  (regras) e calibra: canais de repasse nos **alvos de IRF do próprio anexo** (câmbio
  +10% → admin ≈ +1,8 p.p. em 4T; petróleo +10% → ≈ +1,3 p.p.) e sazonalidade/indexação
  ajustadas à série oficial (SGS 11427).

### 2.3 Cenário do RPM jun/2026 → `modelo-agregado/config/rpm_2026q2.yaml`
- **Fonte**: `rpm202606p.pdf` (RPM jun/2026, Tabela 2.2.1 e seção 2.2), págs. 65–70.
- **Método**: transcrição manual do PDF (cabeçalho do arquivo documenta a fonte).
- **Transcrito em**: 2026-07 (rodada anterior) · **Verificação**: valores conferidos na
  transcrição original; `data_divulgacao: 2026-06-25`.
- **Fidelidade**: trajetórias de IPCA/livres/admin 4T, Selic Focus, câmbio PPC, Brent,
  juro real neutra e RONI transcritos numericamente.

### 2.4 Especificação dos semiestruturais (RI jun/2024, boxe b12) → usado na auditoria
- **Fonte**: `ri202406b12p_semiestruturais.pdf`.
- **Status**: leitura para auditoria de lacunas (não há transcrição numérica — o boxe
  atualiza o modelo semestrual; a tabela de priors do agregado é a do RI dez/2021).

### 2.5 Bandeira tarifária → `modelo-completo/config/bandeiras.csv`
- **Fonte**: ANEEL, dados abertos ("Bandeiras Tarifárias"): CSVs de Acionamento e Adicional.
- **Método**: download dos CSVs + transformação (mês, bandeira, adicional em R$/MWh).
- **Transcrito em**: 2026-08-12 · **Verificação**: ciclo 2021 (escassez hídrica) e
  2024–25 conferidos contra o histórico público.

## 3. Especificação como dado PIT

O manifesto `modelo-completo/config/spec_manifesto.yaml` registra cada artefato de
especificação com `vintage` (edição do BCB) e `available_from` (data de publicação):

| Módulo / artefato | Fonte | Vintage | available_from |
|---|---|---|---|
| Priors do agregado | RI dez/2021 (b7) | 2021Q4 | 2021-12-31 |
| Equações de administrados (calibradas) | RPM jun/2025 (B9) | 2025Q2 | 2025-06-30 |
| Cenário de referência | RPM jun/2026 | 2026Q2 | 2026-06-25 |
| Atualização semiestruturais | RI jun/2024 (b12) | 2024Q2 | 2024-06-28 |
| Hiato (JL) | RI jun/2024 (b10) | 2024Q2 | 2024-06-28 |
| Juro real neutra | RI jun/2024 (b11) | 2024Q2 | 2024-06-28 |
| Sistema de projeções | RI mar/2023 (b4) | 2023Q1 | 2023-03-31 |

`spec_manifesto.py::check_spec(name, cutoff)` avisa (warning) quando a especificação
carregada tem `available_from > cutoff` do snapshot — isto é, quando uma reestimação por
vintage usaria uma especificação que ainda não tinha sido publicada naquele momento
(vazamento de especificação). Os pontos de uso: `rpm.load()`, calibração de administrados
e (futuro) carregamento de priors.
