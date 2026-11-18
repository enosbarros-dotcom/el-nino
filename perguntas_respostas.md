# Lista de perguntas e respostas por intenção — Agente El Niño

Este documento lista **todas as intenções** que o agente (`app_el_nino.py`) reconhece,
as palavras-gatilho de cada uma, exemplos de perguntas e o tipo de resposta entregue.
O agente é 100% offline (sem API de LLM): o roteamento é feito por regras sobre o
texto normalizado e a recuperação lê fatias de `saida/facts.json`.

Ordem de prioridade do roteador (`responder`):
saudação → métricas/modelagem → definição → UF → confirmação → região → ranking →
calor → seca → chuva → saúde → oficial → dados/metodologia → fallback.

---

## 1. saudacao_ajuda

**Gatilhos:** `oi`, `ola`, `hello`, `help`, `ajuda`, `bom dia`, `boa tarde`, `boa noite`.

**Exemplos de pergunta:**
- "Oi"
- "Olá, ajuda"
- "Bom dia"

**Resposta:** apresentação do agente + lista do que ele responde
(confirmação, estados mais impactados, impactos por região, orientações de proteção)
e duas sugestões de pergunta.

---

## 2. metricas_modelagem  *(NOVA)*

**Gatilhos:** `indice de impacto`, `indice impacto`, `o que e indice`,
`como e calculado`, `como funciona`, `modelo`, `modelagem`, `z-score`, `z score`,
`calor_z`, `seca_z`, `chuva_z`, `frac_quente`, `frac_calor`, `padroniza`,
`normaliz`, `climatolog`, `desvio padrao`, `metodologia`, `metodo de calculo`.

**Exemplos de pergunta:**
- "O que é o índice de impacto?"
- "Como é calculado o z-score?"
- "O que é calor_z, seca_z e chuva_z?"
- "Explique a metodologia"
- "Como funciona o modelo?"

**Resposta:** explicação estruturada em 4 blocos:
1. **Z-score (anomalia padronizada)** — `(observado - média do mês) / desvio-padrão da estação`;
   `z_limiar = 1.5` marca mês anômalo; `z_calor_conf = 1.0` é o corte da confirmação.
2. **Confirmação da anomalia** — `temp_z médio ≥ 1.0` **e** ≥ 40% das estações com z ≥ 1.0.
3. **Índice de impacto por UF** —
   `indice = perfil.calor * calor_z + perfil.seca * seca_z + perfil.chuva * chuva_z`,
   com perfil regional (Sul: chuva; N/NE: seca; CO/SE: calor).
4. **Variáveis de suporte** — `perc_meses_quentes/seco/umidos`,
   `dias_calor_extremo` (Tmax ≥ 35 °C), `dias_chuva_intensa` (≥ 50 mm), `frac_quente`.
Informa período, n.° de estações e UFs, e ressalva de que não é previsão meteorológica.

---

## 3. definicao_el_nino

**Gatilhos:** `o que e` (genérico), `explica` + `nino`, `el nino` + `que`.

**Exemplos de pergunta:**
- "O que é o El Niño?"
- "Explique o El Niño"

**Resposta:** definição do fenômeno (aquecimento anômalo do Pacífico Equatorial, enfraquecimento
dos ventos alísios) e os padrões no Brasil: chuva no Sul, seca no Norte/Nordeste,
calor e chuva irregular no Sudeste/Centro-Oeste.

---

## 4. uf_especifica

**Gatilhos:** sigla da UF em maiúsculas (`RS`, `SP`, `BA`, …) ou nome completo
do estado (com normalização de acentos).

**Exemplos de pergunta:**
- "E no Rio Grande do Sul?"
- "Como está São Paulo?"
- "RS"

**Resposta (ficha da UF):** índice de impacto e ranking, anomalias `calor_z`/`seca_z`/`chuva_z`,
`%` de meses quentes, dias de calor extremo, n.° de estações, impacto esperado
(por região) e orientação.

---

## 5. quando_confirmada

**Gatilhos:** `quando`, `confirmad`, `data`, `inicio`, `comecou`, `detectad`.

**Exemplos de pergunta:**
- "Quando a anomalia foi confirmada?"
- "Em que mês começou?"

**Resposta:** mês de confirmação, mês de início sustentado, `%` das estações com calor anômalo,
z médio nacional, critério aplicado e assinatura regional (temp_z e precip_z por região)
na janela de confirmação. Se não confirmado, informa o motivo.

---

## 6. regiao_especifica

**Gatilhos:** `sul`, `nordeste`, `norte`, `centro-oeste`, `sudeste`
(e tokens como `amazonia`, `parana`, `santa catarina`, `rio grande do sul`).

**Exemplos de pergunta:**
- "Quais os impactos no Nordeste?"
- "E no Sul?"

**Resposta (ficha da região):** impacto esperado, estados da região no ranking
(com índice) e a orientação dominante para aquela região (chuva / seca / calor).

---

## 7. estados_impactados (ranking)

**Gatilhos:** `estado`, `uf`, `impactad`, `afetad`, `ranking`, `onde`, `quais`.

**Exemplos de pergunta:**
- "Quais estados serão mais impactados?"
- "Qual o ranking?"

**Resposta:** top 8 UFs pelo índice de impacto, com região, índice e z de calor/seca/chuva,
seguido dos contatos de emergência.

---

## 8. calor

**Gatilhos:** `calor`, `temperatura alta`, `insolacao`, `estresse termico`, `quente`,
`abafado`, `desidrat`, `hipertermia`.

**Exemplos de pergunta:**
- "Orientações para onda de calor"
- "Como me proteger do calor?"

**Resposta:** `KB_SAUDE_CALOR` (hidratação, evitar sol 10h–16h, grupos de risco,
sinais de insolação) + contatos de emergência.

---

## 9. seca

**Gatilhos:** `seca`, `estiagem`, `queimada`, `fumaca`, `ar seco`, `seco`,
`incendio`, `crise hidrica`, `falta de chuva`.

**Exemplos de pergunta:**
- "O que fazer na seca?"
- "Queimadas e fumaça"

**Resposta:** `KB_SECA` (economia de água, evitar queimadas, qualidade do ar,
hidratação das vias aéreas) + emergências.

---

## 10. chuva

**Gatilhos:** `chuva`, `enchente`, `alagamento`, `temporal`, `inundac`, `tempestade`,
`vendaval`, `deslizamento`, `cheia`.

**Exemplos de pergunta:**
- "Orientações para enchentes"
- "Temporal e deslizamentos"

**Resposta:** `KB_CHUVA` (não atravessar áreas alagadas, afastar-se de encostas,
kit de emergência, seguir Defesa Civil) + emergências.

---

## 11. saude

**Gatilhos:** `saude`, `cuidado`, `prevenc`, `orientac`, `hidrat`, `protecao`, `medic`, `hospital`.

**Exemplos de pergunta:**
- "Quais os cuidados com a saúde?"
- "Como me proteger?"

**Resposta:** concatena `KB_SAUDE_CALOR` + `KB_SECA` + `KB_CHUVA` (guia completo).

---

## 12. oficial

**Gatilhos:** `oficial`, `gov`, `portal`, `ministerio`, `link`, `fonte`,
`governo`, `defesa civil`, `inmet`, `cptec`.

**Exemplos de pergunta:**
- "Onde consultar a fonte oficial?"
- "Link do governo"

**Resposta:** link do Portal Gov.br — El Niño
(`https://www.gov.br/saude/pt-br/assuntos/saude-de-a-a-z/e/el-nino`).

---

## 13. dados_metodologia

**Gatilhos:** `dado`, `estatistic`, `z-score` (redundante com métricas), `amostra`,
`quantas estac`, `metodo`, `serie`, `anomalia`, `periodo analisado`.

**Exemplos de pergunta:**
- "Quantas estações foram analisadas?"
- "Qual o período dos dados?"

**Resposta:** n.° de estações, n.° de UFs, período, total de observações mensais,
método (z-score interno por mês-do-ano) e limiar de anomalia.

---

## 14. fallback (resumo geral)

**Gatilhos:** qualquer pergunta não reconhecida.

**Resposta:** resumo com mês de confirmação, % de estações com calor anômalo,
top 3 estados e padrão regional, além de exemplos de perguntas válidas e emergências.

---

## Observações de engenharia

- **Normalização:** o texto é lowercased e sem acentos (`_norm`), então acentos e
  caixa alta não afetam o roteamento.
- **UF por sigla:** só casa em MAIÚSCULO (`\b(RS|SP|...)\b`) para evitar colisões
  com palavras comuns (`se`, `to`, `pa`).
- **Prioridade:** `metricas_modelagem` fica antes de `definicao_el_nino` para que
  "O que é o índice de impacto?" não seja tratado como "O que é o El Niño?".
- **Offline:** nenhuma chamada de rede na inferência; histórico só em `session_state`.
