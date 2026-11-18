# Documentação do Agente El Niño

> Agente conversacional **100% offline** (sem chamadas a APIs de LLM) que responde dúvidas sobre a análise do fenômeno El Niño no Brasil com base em dados das estações automáticas do INMET.

---

## 1. Visão geral

O agente foi implementado em `app_el_nino.py` (Streamlit) e consome apenas a saída pré-processada de `analise_el_nino.py` (`saida/facts.json`) somada a uma **base de conhecimento curada em código** (orientações de saúde/proteção e impactos regionais).

Não há orquestração multi-agente remota nem serviços externos: o "roteamento" é feito por uma função de regra (`responder()`) que classifica a intenção do usuário e monta a resposta a partir de fontes locais.

```mermaid
flowchart LR
    user([Pergunta do usuário]) --> norm[Normalização<br>_norm / _palavras]
    norm --> detect[Detecção de entidades<br>UF · Região]
    detect --> route{Intenção?}
    route -->|saudação/ajuda| help[Mensagem de ajuda]
    route -->|o que é El Niño| explain[Explicação do fenômeno]
    route -->|UF citada| state[_ficha_estado]
    route -->|quando/confirmado| confirm[Detalhes da confirmação]
    route -->|região citada| region[_ficha_regiao]
    route -->|estado/impacto/ranking| ranking[Top 8 estados]
    route -->|calor/seca/chuva/saúde| kb[Orientações da KB]
    route -->|oficial/fonte| official[Link Gov.br]
    route -->|dados/metodologia| method[Metodologia e amostra]
    route -->|fallback| summary[Resumo geral + sugestões]
    state --> out([Resposta final])
    confirm --> out
    region --> out
    ranking --> out
    kb --> out
    official --> out
    method --> out
    summary --> out
    help --> out
    explain --> out
```

---

## 2. Roteamento do agente (responder)

A função `responder(pergunta, f)` segue uma **cadeia de regras em ordem de prioridade**. A primeira regra que casa com a pergunta vence.

```mermaid
flowchart TD
    prompt([Pergunta + facts]) --> norm["_norm(pergunta)<br>lowercase · sem acentos"]
    norm --> uf["UFS_RE + NOME_TO_UF<br>código UF em MAIÚSCULO"]
    norm --> reg["Tokens de região<br>N · NE · CO · SE · S"]
    uf --> greet{"Saudação?<br>(palavra completa)"}
    reg --> greet
    greet -- sim --> help[Resposta de ajuda]
    greet -- não --> def{"o que é / explica<br>+ El Niño?"}
    def -- sim --> explain[Explicação do fenômeno]
    def -- não --> uf2{"UF citada?"}
    uf2 -- sim --> state[_ficha_estado]
    uf2 -- não --> when{"quando / confirmado /<br>data / início?"}
    when -- sim --> confirm[Bloco de confirmação<br>+ assinatura regional]
    when -- não --> reg2{"Região citada?"}
    reg2 -- sim --> region[_ficha_regiao]
    reg2 -- não --> rank{"estado / uf /<br>impactado / ranking?"}
    rank -- sim --> ranking[Top 8 + emergências]
    rank -- não --> theme{"calor · seca · chuva ·<br>saúde · oficial · dados?"}
    theme -- sim --> kb[KB correspondente]
    theme -- não --> fallback[Resumo geral + sugestões]
    help --> out([Resposta final])
    explain --> out
    state --> out
    confirm --> out
    region --> out
    ranking --> out
    kb --> out
    fallback --> out
```

### Ordem de prioridade (por que essa sequência?)

1. **Saudação/ajuda** — comparada por **palavra completa** (`_palavras`) para evitar falso positivo em "foi", "coisa", etc.
2. **Definição** ("o que é El Niño") — antes das consultas de dado, pois é texto fixo.
3. **UF citada** — a ficha de estado é a resposta mais específica; deve vencer o ranking genérico.
4. **Confirmação** ("quando foi confirmada?") — consulta o bloco `confirmacao` do `facts.json`.
5. **Região citada** — vem antes do ranking genérico para que "impactos no Nordeste?" retorne a ficha regional.
6. **Ranking de estados** — consulta genérica sobre impactos.
7. **Temas de orientação** (calor, seca, chuva, saúde) — buscam a KB curada.
8. **Fonte oficial / metodologia** — perguntas sobre dados e links.
9. **Fallback** — resumo geral + sugestões de perguntas.

---

## 3. Recuperação de conhecimento (RAG local)

O agente não usa embeddings nem vetor store. A "recuperação" é **seletiva e determinística**: a regra de roteamento escolhe qual fatia de `facts.json` e qual entrada da KB deve ser usada.

```mermaid
flowchart LR
    q([Pergunta roteada]) --> sel[Seletor de fonte<br>pela intenção detectada]

    sel --> facts["saida/facts.json<br>cacheado via @st.cache_data"]
    sel --> kb[Base de conhecimento<br>curada em código]

    facts --> f_conf["confirmacao<br>· mes_confirmacao · temp_z · frac_quente<br>· detalhe_regional · criterio"]
    facts --> f_rank["ranking_estados<br>· uf · regiao · indice_impacto<br>· calor_z · seca_z · chuva_z · dias_calor"]
    facts --> f_serie["serie_nacional<br>· temp_z · precip_z · frac_calor"]
    facts --> f_meta["metadados<br>· n_estacoes · n_ufs · periodo_dados"]

    kb --> kb_impactos["KB_IMPACTOS<br>impacto esperado por região"]
    kb --> kb_calor["KB_SAUDE_CALOR<br>ondas de calor / estresse térmico"]
    kb --> kb_seca["KB_SECA<br>estiagem / queimadas"]
    kb --> kb_chuva["KB_CHUVA<br>enchentes / temporais"]
    kb --> kb_emer["EMERGENCIAS<br>199 · 192 · 193"]

    f_conf --> mont[Montagem da resposta]
    f_rank --> mont
    f_serie --> mont
    f_meta --> mont
    kb_impactos --> mont
    kb_calor --> mont
    kb_seca --> mont
    kb_chuva --> mont
    kb_emer --> mont
    mont --> out([Resposta final em Markdown])
```

### Fontes de verdade

| Fonte | Tipo | Conteúdo |
|---|---|---|
| `saida/facts.json` | Calculado por `analise_el_nino.py` | Confirmação, ranking estadual, série nacional, metadados |
| `KB_IMPACTOS` | Curada (código) | Impacto esperado por região (S, N, NE, CO, SE) |
| `KB_SAUDE_CALOR` | Curada (código) | Orientações para ondas de calor |
| `KB_SECA` | Curada (código) | Orientações para seca/queimadas |
| `KB_CHUVA` | Curada (código) | Orientações para chuvas intensas |
| `EMERGENCIAS` | Curada (código) | Telefones: Defesa Civil 199, SAMU 192, Bombeiros 193 |
| `FONTE_OFICIAL` | Curada (código) | Link para o portal Gov.br/El Niño |

---

## 4. Fluxo de execução e observabilidade

Como o agente roda **localmente e sem serviços externos**, a "observabilidade" se reduz ao ciclo de vida do Streamlit e aos logs do processo. Cada pergunta é processada dentro da própria requisição do navegador.

```mermaid
flowchart TD
    req([Pergunta no chat_input]) --> sessao[Streamlit session_state.chat]
    sessao --> responder[responder pergunta, facts]
    responder --> norm["_norm + detecção<br>UF · região · intenção"]
    norm --> sel[Seletor de fonte]
    sel --> facts_cache["carregar_fatos<br>@st.cache_data (memória)"]
    sel --> kb_code[KB em código]
    facts_cache --> mont[Montar Markdown]
    kb_code --> mont
    mont --> append[append na session_state.chat]
    append --> render[st.chat_message + st.markdown]
    render --> ui([Interface Streamlit])

    responder -.->|nenhuma chamada de rede| net((Sem saída de rede))
    facts_cache -.->|leitura de arquivo local| fs((disco local))
```

### Pontos de rastreabilidade

- **`@st.cache_data(show_spinner=False)`**: `carregar_fatos` lê `saida/facts.json` uma única vez e mantém em cache por sessão do Streamlit.
- **`session_state.chat`**: todo o histórico da conversa vive apenas na sessão do navegador; ao fechar a aba, a conversa é perdida.
- **Sem logs persistentes**: o agente não grava perguntas nem respostas em disco. O único log é o `stdout` do processo Streamlit (erros de execução).
- **Privacidade**: nenhuma pergunta é enviada para APIs externas.

---

## 5. Interface (3 abas)

| Aba | Conteúdo |
|---|---|
| **Pergunte ao agente** | Chat com sugestões clicáveis e `chat_input` |
| **Dados e estados** | DataFrame do ranking, gráfico da série nacional, fração de estações com calor |
| **Guia de proteção** | Orientações de calor/seca/chuva + fonte oficial + emergências |

---

## 6. Como executar

```bash
# 1. Gera os fatos (se ainda não existir saida/facts.json)
python analise_el_nino.py

# 2. Sobe o agente
streamlit run app_el_nino.py
```

O agente fica disponível em `http://localhost:8501`.
