# -*- coding: utf-8 -*-
"""
Agente El Nino - Streamlit (100% offline, sem API key)
======================================================
Consome saida/facts.json (gerado por analise_el_nino.py) e responde
duvidas sobre: quando a anomalia foi confirmada, estados mais impactados,
impactos por regiao e orientacoes de saude/protecao.

Rodar:  streamlit run app_el_nino.py
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import pandas as pd
import streamlit as st

BASE = Path(__file__).resolve().parent
FACTS = BASE / "saida" / "facts.json"

# --------------------------------------------------------------------------- #
# Base de conhecimento (curada) - orientacoes e contexto
# --------------------------------------------------------------------------- #
FONTE_OFICIAL = "https://www.gov.br/saude/pt-br/assuntos/saude-de-a-a-z/e/el-nino"

KB_IMPACTOS = {
    "S": "Chuvas muito acima da media, temporais frequentes e risco elevado de enchentes e alagamentos.",
    "N": "Aumento da seca e estiagem severa, com elevacao do risco de queimadas na Amazonia.",
    "NE": "Seca e estiagem severa, com reducao das chuvas e aumento do risco de queimadas e crise hidrica.",
    "CO": "Ocorrencia de ondas de calor e maior variabilidade nos volumes de chuva.",
    "SE": "Ondas de calor e maior variabilidade nos volumes de chuva.",
}

KB_REGIAO_NOME = {
    "N": "Norte", "NE": "Nordeste", "CO": "Centro-Oeste", "SE": "Sudeste", "S": "Sul",
}

KB_SAUDE_CALOR = (
    "**Ondas de calor / estresse termico**\n"
    "- Beba agua com frequencia, mesmo sem sede; evite bebidas alcoolicas e muito acucaradas.\n"
    "- Evite exposicao ao sol entre 10h e 16h; use roupas leves e protetor solar.\n"
    "- Atencao redobrada com idosos, criancas, gestantes e pessoas com doencas cronicas.\n"
    "- Sinais de alerta de insolacao/desidratacao: tontura, nausea, dor de cabeca intensa, "
    "pele quente e seca, confusao mental, desmaio. Procure atendimento imediatamente."
)

KB_SECA = (
    "**Seca / estiagem e queimadas**\n"
    "- Economize agua e evite desperdicio; priorize o consumo humano.\n"
    "- Nao faca queimadas; mantenha terrenos limpos e evite fogueiras perto de vegetacao.\n"
    "- Cuide da qualidade do ar: em dias com fumaca, feche janelas, use mascara se necessario "
    "e hidrate as vias respiratorias; procure atendimento se houver falta de ar.\n"
    "- Atencao a sinais de desidratacao e ao consumo de agua de fontes seguras."
)

KB_CHUVA = (
    "**Chuvas intensas / enchentes**\n"
    "- Nao atravesse areas alagadas a pe ou de carro; a agua pode esconder buracos e correnteza.\n"
    "- Afaste-se de encostas e margens de rios em caso de chuva forte e continua.\n"
    "- Prepare um kit de emergencia (agua, alimentos, documentos, lanternas, medicamentos).\n"
    "- Siga os alertas da Defesa Civil do seu municipio e evacue quando orientado."
)

EMERGENCIAS = "Emergencias: **Defesa Civil 199** | **SAMU 192** | **Bombeiros 193**."

UF_NOME = {
    "AC": "Acre", "AL": "Alagoas", "AP": "Amapa", "AM": "Amazonas", "BA": "Bahia",
    "CE": "Ceara", "DF": "Distrito Federal", "ES": "Espirito Santo", "GO": "Goias",
    "MA": "Maranhao", "MT": "Mato Grosso", "MS": "Mato Grosso do Sul", "MG": "Minas Gerais",
    "PA": "Para", "PB": "Paraiba", "PR": "Parana", "PE": "Pernambuco", "PI": "Piaui",
    "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte", "RS": "Rio Grande do Sul",
    "RO": "Rondonia", "RR": "Roraima", "SC": "Santa Catarina", "SP": "Sao Paulo",
    "SE": "Sergipe", "TO": "Tocantins",
}
NOME_TO_UF = {v.lower(): k for k, v in UF_NOME.items()}
NOME_TO_UF.update({"paraiba": "PB", "piaui": "PI", "ceara": "CE", "goias": "GO",
                   "espirito santo": "ES", "rio grande do sul": "RS", "rio de janeiro": "RJ",
                   "sao paulo": "SP", "minas gerais": "MG", "mato grosso": "MT",
                   "mato grosso do sul": "MS", "distrito federal": "DF"})
# "para" (preposicao) colide com o estado Para; so casa se vier em MAIUSCULO via UFS_RE
NOME_TO_UF.pop("para", None)

# Codigos de UF em MAIUSCULO (ex.: "RS", "SP") para evitar colisoes com palavras comuns ("se", "to")
UFS_RE = re.compile(r"\b(" + "|".join(UF_NOME.keys()) + r")\b")


def _norm(txt: str) -> str:
    txt = unicodedata.normalize("NFKD", txt.lower())
    return "".join(c for c in txt if not unicodedata.combining(c))


def _palavras(txt: str) -> set[str]:
    return set(re.findall(r"[a-z]+", _norm(txt)))


# --------------------------------------------------------------------------- #
# Carregamento dos fatos
# --------------------------------------------------------------------------- #
@st.cache_data(show_spinner=False)
def carregar_fatos(path_str: str):
    return json.loads(Path(path_str).read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# Motor do agente (regras + recuperacao sobre os fatos calculados)
# --------------------------------------------------------------------------- #
def responder(pergunta: str, f: dict) -> str:
    q = _norm(pergunta)
    ranking = f["ranking_estados"]
    conf = f["confirmacao"]

    # localizar UF citada (codigo em MAIUSCULO, ex.: "RS"; ou nome completo, com limite de palavra)
    uf_citada = None
    m_uf = UFS_RE.search(pergunta)
    if m_uf:
        uf_citada = m_uf.group(1)
    if not uf_citada:
        for nome, cod in NOME_TO_UF.items():
            if re.search(r"(?<![a-z])" + re.escape(nome) + r"(?![a-z])", q):
                uf_citada = cod
                break

    # localizar regiao citada
    regiao_citada = None
    for key, tokens in {
        "S": ["sul", "parana", "santa catarina", "rio grande do sul"],
        "NE": ["nordeste", "nordestino"],
        "N": ["norte", "amazonia", "amazonas"],
        "CO": ["centro-oeste", "centro oeste"],
        "SE": ["sudeste"],
    }.items():
        if any(t in q for t in tokens):
            regiao_citada = key
            break

    # saudações / ajuda (comparacao por palavra, para nao casar com "foi", "coisa", etc.)
    palavras = _palavras(pergunta)
    if palavra_greeting := (palavras & {"oi", "ola", "help", "ajuda"}):
        return (
            "Ola! Sou o agente do El Nino. Posso responder sobre:\n"
            "- **Quando** a anomalia foi confirmada;\n"
            "- **Quais estados** serao mais impactados (e por que);\n"
            "- **Impactos por regiao** (chuva, seca, calor);\n"
            "- **Orientacoes** de saude e protecao (calor, seca, enchentes).\n\n"
            "Experimente: *\"Quando a anomalia foi confirmada?\"* ou *\"Quais estados mais impactados?\"*"
        )
    if any(t in q for t in ["bom dia", "boa tarde", "boa noite"]):
        return (
            "Ola! Sou o agente do El Nino. Posso responder sobre:\n"
            "- **Quando** a anomalia foi confirmada;\n"
            "- **Quais estados** serao mais impactados (e por que);\n"
            "- **Impactos por regiao** (chuva, seca, calor);\n"
            "- **Orientacoes** de saude e protecao (calor, seca, enchentes).\n\n"
            "Experimente: *\"Quando a anomalia foi confirmada?\"* ou *\"Quais estados mais impactados?\"*"
        )

    if "o que e" in q or "explica" in q and "nino" in q or ("el nino" in q and "que" in q and "?" in pergunta):
        return (
            "**El Nino** e um fenomeno climatico natural caracterizado pelo aquecimento anormal das "
            "aguas superficiais do Oceano Pacifico Equatorial. Ele enfraquece os ventos alisios e "
            "altera a circulacao atmosferica global, modificando os padroes de chuva e temperatura.\n\n"
            "No Brasil: chuvas acima da media no **Sul**, seca no **Norte/Nordeste** e ondas de calor "
            "com chuva irregular no **Sudeste/Centro-Oeste**."
        )

    # pergunta sobre um estado especifico
    if uf_citada:
        item = next((r for r in ranking if r["uf"] == uf_citada), None)
        if item:
            return _ficha_estado(item, f)

    # quando confirmada
    if any(t in q for t in ["quando", "confirmad", "data", "inicio", "comecou", "detectad"]):
        if conf.get("confirmado"):
            det = conf.get("detalhe_regional", {})
            nomes = {"CO": "Centro-Oeste", "S": "Sul", "SE": "Sudeste", "N": "Norte", "NE": "Nordeste"}
            linhas = "\n".join(
                f"- {nomes[r]}: temp {det[r]['temp_z']:+.2f}\u03c3, chuva {det[r]['precip_z']:+.2f}\u03c3"
                for r in ["CO", "S", "SE", "N", "NE"] if r in det
            )
            return (
                f"A anomalia foi **confirmada em {conf['mes_confirmacao']}**, com in\u00edcio do "
                f"aquecimento em {conf.get('mes_inicio_sustentado','-')}.\n\n"
                f"Nesse m\u00eas, **{conf['frac_quente']*100:.0f}%** das {conf['n_estacoes']} esta\u00e7\u00f5es "
                f"apresentaram anomalia de temperatura z \u2265 {f['z_calor_conf']} "
                f"(z m\u00e9dio nacional = {conf['temp_z']:+.2f}\u03c3).\n\n"
                f"Crit\u00e9rio: `{conf.get('criterio','')}` (amplo e forte).\n\n"
                f"**Assinatura regional na janela** ({', '.join(conf.get('meses_janela', []))}):\n{linhas}"
            )
        return f"Ainda nao houve sinal sustentado no periodo analisado. {conf.get('motivo','')}"

    # regiao especifica (antes do ranking generico, p/ "quais impactos no Nordeste?" etc.)
    if regiao_citada:
        return _ficha_regiao(regiao_citada, ranking, f)

    # estados mais impactados
    if any(t in q for t in ["estado", "uf", "impactad", "afetad", "ranking", "onde", "quais"]):
        top = ranking[:8]
        linhas = "\n".join(
            f"{r['ranking']}. **{r['uf']}** ({r['regiao_nome']}) - indice {r['indice_impacto']:.2f} "
            f"| calor z={r['calor_z']:.2f}, seca z={r['seca_z']:.2f}, chuva z={r['chuva_z']:.2f}"
            for r in top
        )
        return f"Estados mais impactados (2026), pelo indice region-aware:\n\n{linhas}\n\n{EMERGENCIAS}"

    # temas de orientacao (temas especificos antes dos genericos)
    if any(t in q for t in ["calor", "temperatura alta", "insolacao", "estresse termico",
                            "quente", "abafado", "desidrat", "hipertermia"]):
        return KB_SAUDE_CALOR + "\n\n" + EMERGENCIAS
    if any(t in q for t in ["seca", "estiagem", "queimada", "fumaca", "ar seco",
                            "seco", "incendio", "crise hidrica", "falta de chuva"]):
        return KB_SECA + "\n\n" + EMERGENCIAS
    if any(t in q for t in ["chuva", "enchente", "alagamento", "temporal", "inundac",
                            "tempestade", "vendaval", "deslizamento", "cheia"]):
        return KB_CHUVA + "\n\n" + EMERGENCIAS
    if any(t in q for t in ["saude", "cuidado", "prevenc", "orientac", "hidrat", "protecao",
                            "medic", "hospital"]):
        return KB_SAUDE_CALOR + "\n\n" + KB_SECA + "\n\n" + KB_CHUVA
    if any(t in q for t in ["oficial", "gov", "portal", "ministerio", "link", "fonte",
                            "governo", "defesa civil", "inmet", "cptec"]):
        return f"Orientacoes oficiais de saude e avisos de calor extremo: **Portal Gov.br - El Nino**\n{FONTE_OFICIAL}"
    if any(t in q for t in ["dado", "estatistic", "metodolog", "z-score", "amostra", "quantas estac",
                            "metodo", "serie", "anomalia", "periodo analisado"]):
        return (
            f"Foram analisadas **{f['n_estacoes']} estacoes** automaticas do INMET em **{f['n_ufs']} UFs**, "
            f"no periodo de {f['periodo_dados']['min']} a {f['periodo_dados']['max']} "
            f"({f['n_observacoes_mensais']:,} observacoes mensais).\n\n"
            f"Metodo: z-score interno (anomalia em relacao a climatologia do mes-do-ano, dividida "
            f"pelo desvio-padrao da propria estacao). Limiar de anomalia: |z| >= {f['z_limiar']}."
        )

    # fallback inteligente: resumo geral
    top3 = ", ".join(r["uf"] for r in ranking[:3])
    return (
        "Nao entendi exatamente a pergunta, mas aqui vai um resumo:\n\n"
        f"- Anomalia confirmada em **{conf.get('mes_confirmacao','-')}** "
        f"({conf.get('frac_quente',0)*100:.0f}% das estacoes com calor anomalo).\n"
        f"- Estados mais impactados: **{top3}**.\n"
        f"- Padrao: chuva no Sul, seca no Norte/Nordeste, calor no Sudeste/Centro-Oeste.\n\n"
        "Pergunte, por exemplo: *\"E no Rio Grande do Sul?\"*, *\"orientacoes para onda de calor\"* "
        f"ou *\"quando foi confirmada?\"*. {EMERGENCIAS}"
    )


def _ficha_estado(item: dict, f: dict) -> str:
    reg = item["regiao"]
    return (
        f"**{item['uf']} - {UF_NOME.get(item['uf'], '')} ({item['regiao_nome']})**\n\n"
        f"- Indice de impacto (2026): **{item['indice_impacto']:.2f}** (ranking #{item['ranking']}).\n"
        f"- Anomalia de calor (z medio): {item['calor_z']:.2f} | seca: {item['seca_z']:.2f} "
        f"| chuva: {item['chuva_z']:.2f}.\n"
        f"- Meses com calor anomalo: {item['perc_meses_quentes']:.0f}% | "
        f"dias com Tmax >= 35C: {item['dias_calor_extremo']}.\n"
        f"- Estacoes analisadas: {item['n_estacoes']}.\n\n"
        f"**Impacto esperado:** {KB_IMPACTOS[reg]}\n\n"
        f"**Orientacoes:** veja a aba *Orientacoes* ou pergunte sobre calor, seca ou chuva.\n\n{EMERGENCIAS}"
    )


def _ficha_regiao(reg: str, ranking: list[dict], f: dict) -> str:
    estados = [r for r in ranking if r["regiao"] == reg]
    lista = ", ".join(f"{r['uf']} ({r['indice_impacto']:.2f})" for r in estados[:8])
    return (
        f"**Regiao {KB_REGIAO_NOME[reg]}**\n\n"
        f"- Impacto esperado: {KB_IMPACTOS[reg]}\n"
        f"- Estados da regiao no ranking: {lista}.\n\n"
        f"**Orientacoes:** "
        + (KB_CHUVA if reg == "S" else KB_SECA if reg in ("N", "NE") else KB_SAUDE_CALOR)
        + f"\n\n{EMERGENCIAS}"
    )


# --------------------------------------------------------------------------- #
# Interface
# --------------------------------------------------------------------------- #
ESTILO_UI = """
<style>
:root { --navy:#062b62; --blue:#0755a0; --gold:#ffb51b; --ink:#10243d; --muted:#667992; --paper:#f3f7fc; --surface:#fff; --line:#dce6f2; }
.stApp { background:var(--paper); color:var(--ink); font-family:Inter,'Segoe UI',sans-serif; }
.block-container { max-width:1440px; padding:2rem clamp(1rem,4vw,3.5rem) 3rem; }
h1,h2,h3,[data-testid="stMetricValue"] { font-family:'Segoe UI',Arial,sans-serif; }
.elnino-hero { position:relative; overflow:hidden; min-height:300px; padding:clamp(1.6rem,4vw,3.2rem); border-radius:28px; color:white; background:radial-gradient(ellipse at 93% 105%,rgba(12,106,190,.72),transparent 43%),linear-gradient(118deg,#075ba6 0%,#064887 44%,#062b62 100%); box-shadow:0 22px 48px rgba(6,43,98,.16); }
.elnino-hero:before { content:""; position:absolute; width:390px; height:390px; right:-35px; top:-180px; border:1px solid rgba(255,255,255,.13); border-radius:50%; box-shadow:0 0 0 25px rgba(255,255,255,.025),0 0 0 58px rgba(255,255,255,.025); }
.hero-copy { position:relative; z-index:1; max-width:690px; }
.hero-kicker { display:inline-flex; align-items:center; gap:9px; margin-bottom:1rem; color:#d7eaff; font-size:.78rem; font-weight:700; letter-spacing:.12em; text-transform:uppercase; }
.hero-kicker:before { content:""; width:8px; height:8px; border-radius:50%; background:var(--gold); box-shadow:0 0 12px rgba(255,181,27,.75); }
.elnino-hero h1.hero-title { margin:0; color:#fff !important; font-family:'Segoe UI',Arial,sans-serif !important; font-size:clamp(3.5rem,8vw,6.5rem) !important; font-weight:800 !important; line-height:.96 !important; letter-spacing:-.065em; text-wrap:balance; }
.hero-title .title-word { display:block; width:fit-content; animation:title-reveal .42s cubic-bezier(.2,.7,.25,1) both; animation-delay:calc(var(--word-index,0) * 75ms); }
.hero-title .hero-season { margin-top:.38em; color:var(--gold); font-size:.54em; letter-spacing:-.035em; }
@keyframes title-reveal { from { opacity:0; transform:translateY(9px); filter:blur(2px); } to { opacity:1; transform:translateY(0); filter:blur(0); } }
.hero-subtitle { max-width:540px; margin:1.15rem 0 0; color:#d8e9fb; font-size:1rem; line-height:1.65; }
.hero-orbit { position:absolute; right:clamp(1.5rem,8vw,7.5rem); bottom:1.4rem; display:grid; place-items:center; width:clamp(150px,23vw,250px); aspect-ratio:1; border-radius:50%; background:radial-gradient(circle at 38% 32%,rgba(29,132,206,.82),rgba(2,43,99,.2) 67%); box-shadow:inset 0 0 42px rgba(117,191,246,.12),0 0 50px rgba(0,20,58,.18); }
.hero-orbit:before,.hero-orbit:after { content:""; position:absolute; inset:12%; border-radius:50%; background:radial-gradient(circle,transparent 69%,rgba(202,229,255,.16) 70% 70.5%,transparent 71%); }
.hero-orbit:after { inset:27% -7%; transform:rotate(-24deg); background:radial-gradient(ellipse,transparent 68%,rgba(202,229,255,.14) 69% 69.5%,transparent 70%); }
.ocean-label { position:relative; z-index:1; max-width:130px; color:#e8f5ff; font-size:.8rem; font-weight:700; line-height:1.4; text-align:center; text-transform:uppercase; letter-spacing:.08em; }
.warm-band { position:absolute; left:14%; top:47%; width:72%; height:15px; border-radius:100%; transform:rotate(-13deg); background:linear-gradient(90deg,#ffb54a,#ff7f2a 56%,#e73532); filter:drop-shadow(0 0 9px rgba(255,111,46,.75)); }
.hero-meta { display:flex; flex-wrap:wrap; gap:9px; margin-top:1.5rem; }
.hero-chip { padding:.4rem .78rem; border-radius:8px; color:white; font-size:.8rem; font-weight:700; background:rgba(255,255,255,.12); }
.hero-chip--gold { color:var(--gold); background:rgba(255,181,27,.1); }
.section-eyebrow { margin:1.65rem 0 .8rem; color:var(--muted); font-size:.76rem; font-weight:700; letter-spacing:.13em; text-transform:uppercase; }
[data-testid="stMetric"] { min-height:112px; padding:1.05rem 1.2rem; border:0; border-radius:14px; background:var(--surface); box-shadow:0 8px 24px rgba(22,57,97,.055); }
[data-testid="stMetricLabel"] { color:var(--muted); font-size:.82rem; font-weight:600; }
[data-testid="stMetricValue"] { color:var(--navy); font-size:1.8rem; font-weight:800; }
[data-testid="stTabs"] { margin-top:1.5rem; }
[data-testid="stTabs"] [role="tablist"] { gap:8px; border:0; }
[data-testid="stTabs"] button[role="tab"] { padding:.72rem 1.05rem; border:0; border-radius:8px; color:var(--muted); font-weight:700; background:transparent; transition:background-color .15s ease,color .15s ease; }
[data-testid="stTabs"] button[role="tab"][aria-selected="true"] { color:var(--blue); background:#e5f1fd; }
[data-testid="stChatMessage"] { border:0; border-radius:12px; background:var(--surface); box-shadow:0 5px 18px rgba(22,57,97,.045); }
[data-testid="stChatInput"] { border:0; border-radius:10px; background:var(--surface); box-shadow:0 5px 18px rgba(22,57,97,.07); }
.stButton > button { min-height:44px; border:0; border-radius:8px; color:white; font-weight:700; background:var(--blue); transition:background-color .15s ease,transform .15s ease; }
.stButton > button:hover { color:white; background:var(--navy); transform:translateY(-1px); }
.stButton > button:focus-visible,[data-testid="stTabs"] button:focus-visible { outline:3px solid #ffb51b; outline-offset:3px; }
[data-testid="stDataFrame"] { overflow:hidden; border:0; border-radius:12px; box-shadow:0 6px 22px rgba(22,57,97,.05); }
.privacy-note { margin-top:2rem; padding-top:1rem; color:var(--muted); font-size:.82rem; }
@media (prefers-reduced-motion:reduce) {
  *,*::before,*::after { scroll-behavior:auto !important; animation-duration:.01ms !important; transition-duration:.01ms !important; }
}
@media (max-width:720px) {
  .block-container { padding-top:1rem; }
  .elnino-hero { min-height:0; padding-bottom:1.5rem; }
  .hero-orbit { right:-35px; bottom:-38px; opacity:.35; }
  .hero-copy { max-width:100%; }
  .hero-subtitle { max-width:90%; }
  [data-testid="stMetric"] { min-height:95px; padding:.8rem; }
  [data-testid="stMetricValue"] { font-size:1.35rem; }
}
</style>
"""


def main() -> None:
    st.set_page_config(page_title="Agente El Niño", page_icon=BASE / "favicon.svg", layout="wide")
    st.markdown(ESTILO_UI, unsafe_allow_html=True)

    if not FACTS.exists():
        st.error("Arquivo saida/facts.json nao encontrado. Rode `python analise_el_nino.py` primeiro.")
        st.stop()

    f = carregar_fatos(str(FACTS))
    conf = f["confirmacao"]
    periodo = f["periodo_dados"]
    status = (
        f"Anomalia confirmada em {conf['mes_confirmacao']}"
        if conf.get("confirmado")
        else "Monitoramento em andamento"
    )
    if conf.get("confirmado"):
        resumo = (
            f"Confirmada em {conf['mes_confirmacao']}: z médio da temperatura "
            f"{conf['temp_z']:+.2f}σ; {conf['frac_quente']*100:.1f}% das "
            f"{conf['n_estacoes']} estações com z ≥ {f['z_calor_conf']:.1f}σ. "
            "Explore o ranking estadual, a evolução mensal e orientações oficiais."
        )
    else:
        resumo = (
            f"Até {periodo['max']}, os dados ainda não atenderam simultaneamente "
            "aos critérios de confirmação. Explore a série mensal, os impactos regionais "
            "e as orientações oficiais."
        )

    st.markdown(
        f"""
        <section class="elnino-hero">
          <div class="hero-copy">
            <div class="hero-kicker">Dados do INMET · série até {periodo['max']}</div>
            <h1 class="hero-title"><span class="title-word" style="--word-index:0">El Niño</span><span class="title-word hero-season" style="--word-index:1">Brasil · 2026–2027</span></h1>
            <p class="hero-subtitle">
              {resumo}
            </p>
            <div class="hero-meta">
              <span class="hero-chip">Dados {periodo['min']} a {periodo['max']}</span>
              <span class="hero-chip hero-chip--gold">{status}</span>
            </div>
          </div>
          <div class="hero-orbit" aria-hidden="true">
            <div class="warm-band"></div>
            <div class="ocean-label">Pacífico<br>Equatorial</div>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="section-eyebrow">Resumo da análise</div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Estações automáticas", f"{f['n_estacoes']:,}".replace(",", "."))
    c2.metric("Unidades federativas", f"{f['n_ufs']}")
    c3.metric("Confirmação", conf.get("mes_confirmacao", "Em análise") if conf.get("confirmado") else "Em análise")
    c4.metric("Limiar de confirmação", f"z ≥ {f['z_calor_conf']:.1f}")

    aba_agente, aba_painel, aba_orient = st.tabs(
        ["Pergunte ao agente", "Dados e estados", "Guia de proteção"]
    )

    with aba_agente:
        st.subheader("Como podemos ajudar?")
        st.caption("Pergunte sobre a confirmação, impactos por local ou como se proteger.")
        if "chat" not in st.session_state:
            st.session_state.chat = [
                {"role": "assistant", "content": (
                    "Olá! Sou o agente do El Niño. Pergunte quando a anomalia foi confirmada, "
                    "quais estados serão mais impactados ou peça orientações sobre calor, seca e enchentes."
                )}
            ]

        sugestoes = [
            "Quando a anomalia foi confirmada?",
            "Quais estados serao mais impactados?",
            "Quais os impactos no Nordeste?",
            "Orientacoes para onda de calor",
        ]
        for inicio in range(0, len(sugestoes), 2):
            for col, s in zip(st.columns(2), sugestoes[inicio:inicio + 2]):
                if col.button(s, width="stretch"):
                    st.session_state.chat.append({"role": "user", "content": s})
                    st.session_state.chat.append({"role": "assistant", "content": responder(s, f)})

        for msg in st.session_state.chat:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        if pergunta := st.chat_input("Digite sua duvida sobre o El Nino..."):
            st.session_state.chat.append({"role": "user", "content": pergunta})
            with st.chat_message("user"):
                st.markdown(pergunta)
            with st.chat_message("assistant"):
                st.markdown(responder(pergunta, f))

    with aba_painel:
        st.subheader("Estados em destaque")
        st.caption(
            f"Índice regional de impacto no período {f.get('periodo_impacto_label', 'mais recente')}. "
            "É uma leitura dos dados observados, não uma previsão meteorológica."
        )
        df = pd.DataFrame(f["ranking_estados"])
        st.dataframe(
            df[["ranking", "uf", "regiao_nome", "indice_impacto", "calor_z", "seca_z",
                "chuva_z", "perc_meses_quentes", "dias_calor_extremo", "n_estacoes"]],
            width="stretch", hide_index=True,
        )
        st.subheader("Evolução mensal")
        st.caption("Z-score de temperatura e precipitação em relação ao padrão interno do período.")
        serie = pd.DataFrame(f["serie_nacional"]).set_index("mes_str")
        st.line_chart(serie[["temp_z", "precip_z"]])
        st.subheader("Estações com sinal de calor")
        st.bar_chart(serie[["frac_calor_1"]].rename(columns={"frac_calor_1": "Fração das estações (z ≥ 1)"}))

    with aba_orient:
        st.subheader("Orientações para se proteger")
        st.caption("Recomendações gerais. Em risco imediato, siga os alertas das autoridades locais.")
        col_calor, col_seca = st.columns(2)
        with col_calor:
            st.markdown(KB_SAUDE_CALOR)
            st.markdown(KB_SECA)
        with col_seca:
            st.markdown(KB_CHUVA)
            st.markdown(f"**Fonte oficial**  \n[Portal Gov.br — El Niño]({FONTE_OFICIAL})")
            st.info(
                "Este painel não substitui boletins oficiais do INMET, ANA, CPTEC/INPE ou Defesa Civil."
            )
        st.markdown(EMERGENCIAS)

    st.markdown(
        '<p class="privacy-note">Privacidade: as perguntas são processadas pelo motor local do app, '
        'sem envio a APIs de IA; a conversa dura apenas nesta sessão. Conteúdo informativo, '
        'não substitui orientações das autoridades.</p>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
