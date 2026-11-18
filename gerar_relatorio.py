# -*- coding: utf-8 -*-
"""
Gera o relatorio HTML (com graficos) a partir de saida/facts.json.
Uso: python gerar_relatorio.py
Saida: relatorio_el_nino.html
"""
from __future__ import annotations

import base64
import io
import json
import os
from html import escape as escape_html
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

BASE = Path(__file__).resolve().parent
SAIDA = BASE / "saida"
FACTS = SAIDA / "facts.json"
DEST = BASE / "relatorio_el_nino.html"

# Paleta unica do projeto: off-white, grafite e verde musgo.
TINTA = "#23252a"
MUSGO = "#5f6b45"
SAGE = "#8d9a6b"
LINHA = "#e4e2da"

REGION_COLORS = {
    "S": "#2f3437",
    "SE": "#7f8c5c",
    "CO": "#5f6b45",
    "N": "#454d2e",
    "NE": "#a3ad86",
}

MESES_CURTOS = {
    "01": "Jan",
    "02": "Fev",
    "03": "Mar",
    "04": "Abr",
    "05": "Mai",
    "06": "Jun",
    "07": "Jul",
    "08": "Ago",
    "09": "Set",
    "10": "Out",
    "11": "Nov",
    "12": "Dez",
}


def rotulo_mes(mes: str) -> str:
    ano, numero = mes.split("-", 1)
    return f"{ano}/{MESES_CURTOS.get(numero, numero)}"


def _estilo(ax) -> None:
    ax.set_facecolor("#ffffff")
    for lado in ("top", "right", "left"):
        ax.spines[lado].set_visible(False)
    ax.spines["bottom"].set_color(LINHA)
    ax.tick_params(colors="#737780", labelsize=8, length=0)
    ax.grid(axis="y", color="#eceae4", lw=0.9)
    ax.set_axisbelow(True)


def fig_to_b64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight", facecolor="#ffffff")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def grafico_serie(serie: list[dict]) -> str:
    meses = [s["mes_str"] for s in serie]
    temp_z = [s["temp_z"] for s in serie]
    prec_z = [s["precip_z"] for s in serie]
    frac = [s["frac_quente"] * 100 for s in serie]

    fig, ax1 = plt.subplots(figsize=(11, 4.6), facecolor="#ffffff")
    _estilo(ax1)
    ax1.axhline(0, color="#cfd2c7", lw=0.9)
    ax1.axhspan(1.5, 3, color="#eef0e6", zorder=0)
    ax1.axhspan(-3, -1.5, color="#f3f3ef", zorder=0)
    ax1.plot(meses, temp_z, "-o", ms=3.5, lw=1.9, color="#3f4a2e", label="Anomalia temp. (z)", zorder=3)
    ax1.plot(meses, prec_z, "-s", ms=3, lw=1.5, color=SAGE, label="Anomalia chuva (z)", zorder=3)
    ax1.set_ylabel("Z-score interno", color="#737780", fontsize=9)
    ax1.set_ylim(-3, 3)
    ax1.tick_params(axis="x", rotation=90, labelsize=7)
    ax2 = ax1.twinx()
    ax2.bar(meses, frac, color="#d7dcc6", width=0.62, zorder=1)
    ax2.set_ylabel("% estacoes quentes (z>=1.5)", color=MUSGO, fontsize=9)
    ax2.set_ylim(0, 100)
    ax2.tick_params(colors=MUSGO, labelsize=8, length=0)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    ax1.legend(loc="upper left", fontsize=8, frameon=False)
    ax1.set_title("Evolucao mensal das anomalias (2024-2026)", fontsize=11, color=TINTA, loc="left", pad=12)
    return fig_to_b64(fig)


def grafico_ranking(ranking: list[dict], periodo: str, top: int = 15) -> str:
    top_r = ranking[:top][::-1]
    nomes = [f"{r['uf']} ({r['regiao_nome'][:3]})" for r in top_r]
    vals = [r["indice_impacto"] for r in top_r]
    cores = [REGION_COLORS[r["regiao"]] for r in top_r]

    fig, ax = plt.subplots(figsize=(9, 5), facecolor="#ffffff")
    _estilo(ax)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color="#eceae4", lw=0.9)
    ax.barh(nomes, vals, color=cores, height=0.58)
    ax.set_xlabel("Indice de impacto (regiao-aware)", color="#737780", fontsize=9)
    ax.set_title(f"Top {top} estados mais impactados pelo El Nino ({periodo})", fontsize=11, color=TINTA, loc="left", pad=12)
    for i, v in enumerate(vals):
        ax.text(v, i, f" {v:.2f}", va="center", fontsize=7, color=TINTA)
    return fig_to_b64(fig)


def grafico_regioes(resumo: list[dict]) -> str:
    nomes = [r["regiao_nome"] for r in resumo]
    vals = [r["indice_medio"] for r in resumo]
    cores = [REGION_COLORS[r["regiao"]] for r in resumo]

    fig, ax = plt.subplots(figsize=(6.4, 3.8), facecolor="#ffffff")
    _estilo(ax)
    ax.bar(nomes, vals, color=cores, width=0.56)
    ax.set_ylabel("Indice medio", color="#737780", fontsize=9)
    ax.set_title("Impacto medio por regiao", fontsize=11, color=TINTA, loc="left", pad=12)
    for i, v in enumerate(vals):
        ax.text(i, v, f"{v:.2f}", ha="center", va="bottom", fontsize=8, color=TINTA)
    return fig_to_b64(fig)


def html(facts: dict) -> str:
    conf = facts["confirmacao"]
    periodo = facts.get("periodo_impacto_label", "2026")
    periodo_observado = (
        f"{rotulo_mes(facts['periodo_dados']['min'])} até "
        f"{rotulo_mes(facts['periodo_dados']['max'])}"
    )
    agent_url = escape_html(
        os.environ.get("ELNINO_AGENT_URL", "http://localhost:8501/").strip()
        or "http://localhost:8501/",
        quote=True,
    )
    favicon = base64.b64encode((BASE / "favicon.svg").read_bytes()).decode("ascii")
    crit_frac = f"{facts['z_calor_conf']:.1f}"

    if conf.get("confirmado"):
        resumo_hero = (
            f"Anomalia confirmada em {conf['mes_confirmacao']}: z médio de temperatura "
            f"{conf['temp_z']:+.2f}σ; {conf['frac_quente']*100:.1f}% das "
            f"{conf['n_estacoes']} estações com z ≥ {crit_frac}σ."
        )
        dossie = (
            '<aside class="dossier">'
            '<p class="dossier-label">Sinal confirmado</p>'
            f'<p class="dossier-month">{conf["mes_confirmacao"]}</p>'
            '<dl class="dossier-list">'
            f'<div><dt>Z médio de temperatura</dt><dd>{conf["temp_z"]:+.2f}σ</dd></div>'
            f'<div><dt>Estações com z ≥ {crit_frac}σ</dt><dd>{conf["frac_quente"]*100:.1f}%</dd></div>'
            f'<div><dt>Estações no mês</dt><dd>{conf["n_estacoes"]}</dd></div>'
            f'<div><dt>Região líder</dt><dd>{facts["resumo_regioes"][0]["regiao_nome"]}</dd></div>'
            '</dl>'
            '</aside>'
        )
        ficha = (
            '<div class="spec-panel">'
            '<p class="spec-title">Ficha da confirmação</p>'
            '<dl class="spec-list">'
            f'<div><dt>Mês confirmado</dt><dd>{conf["mes_confirmacao"]}</dd></div>'
            f'<div><dt>Início do aquecimento</dt><dd>{conf.get("mes_inicio_sustentado", "-")}</dd></div>'
            f'<div><dt>Z médio de temperatura</dt><dd>{conf["temp_z"]:+.2f}σ</dd></div>'
            f'<div><dt>Estações com z ≥ {crit_frac}σ</dt><dd>{conf["frac_quente"]*100:.1f}%</dd></div>'
            f'<div><dt>Estações avaliadas</dt><dd>{conf["n_estacoes"]}</dd></div>'
            '</dl></div>'
        )
    else:
        resumo_hero = (
            f"Até {facts['periodo_dados']['max']}, os dados não atenderam simultaneamente "
            "aos critérios de confirmação. Explore os sinais mensais e os impactos regionais."
        )
        dossie = (
            '<aside class="dossier">'
            '<p class="dossier-label">Sem confirmação no período</p>'
            f'<p class="dossier-month">{facts["periodo_dados"]["max"]}</p>'
            '<dl class="dossier-list">'
            f'<div><dt>Z médio de temperatura</dt><dd>{conf.get("temp_z", 0):+.2f}σ</dd></div>'
            f'<div><dt>Estações analisadas</dt><dd>{facts["n_estacoes"]}</dd></div>'
            f'<div><dt>Unidades federativas</dt><dd>{facts["n_ufs"]}</dd></div>'
            '</dl>'
            '</aside>'
        )
        ficha = (
            '<div class="spec-panel">'
            '<p class="spec-title">Ficha da análise</p>'
            '<dl class="spec-list">'
            f'<div><dt>Último mês com dados</dt><dd>{facts["periodo_dados"]["max"]}</dd></div>'
            f'<div><dt>Estações analisadas</dt><dd>{facts["n_estacoes"]}</dd></div>'
            f'<div><dt>Unidades federativas</dt><dd>{facts["n_ufs"]}</dd></div>'
            '</dl></div>'
        )

    if conf.get("confirmado"):
        det = conf.get("detalhe_regional", {})
        ordem = ["CO", "S", "SE", "N", "NE"]
        nomes_reg = {"CO": "Centro-Oeste", "S": "Sul", "SE": "Sudeste", "N": "Norte", "NE": "Nordeste"}
        linhas_det = "".join(
            f"<li><b>{nomes_reg.get(r, r)}</b> — temperatura {det[r]['temp_z']:+.2f}&sigma;, "
            f"chuva {det[r]['precip_z']:+.2f}&sigma;</li>"
            for r in ordem if r in det
        )
        bloco_conf = (
            f"<p class=\"lead-text\">A anomalia foi confirmada em <span class='mark'>{conf['mes_confirmacao']}</span>, "
            f"com in&iacute;cio do aquecimento em {conf.get('mes_inicio_sustentado','-')}. "
            f"Nesse m&ecirc;s, <b>{conf['frac_quente']*100:.0f}%</b> das {conf['n_estacoes']} esta&ccedil;&otilde;es "
            f"apresentaram anomalia de temperatura z&nbsp;&ge;&nbsp;{facts['z_calor_conf']} "
            f"(z m&eacute;dio nacional = {conf['temp_z']:+.2f}&sigma;).</p>"
            f"<p>Crit&eacute;rio de confirma&ccedil;&atilde;o: <code>{conf.get('criterio','')}</code>. "
            f"Meses que atenderam ao crit&eacute;rio: {', '.join(conf.get('todos_meses_criterio', [])) or '-'}.</p>"
            f"<p class=\"sub-head\">Assinatura regional na janela ({', '.join(conf.get('meses_janela', []))})</p>"
            f"<ul class=\"tight-list\">{linhas_det}</ul>"
        )
    else:
        bloco_conf = f"<p class=\"lead-text\">Sinal n&atilde;o sustentado no per&iacute;odo. {conf.get('motivo','')}</p>"

    linhas = []
    for r in facts["ranking_estados"]:
        linhas.append(
            "<tr>"
            f"<td>{r['ranking']}</td><td><b>{r['uf']}</b></td><td>{r['regiao_nome']}</td>"
            f"<td>{r['indice_impacto']:.2f}</td><td>{r['calor_z']:.2f}</td>"
            f"<td>{r['seca_z']:.2f}</td><td>{r['chuva_z']:.2f}</td>"
            f"<td>{r['perc_meses_quentes']:.0f}%</td><td>{r['dias_calor_extremo']}</td>"
            f"<td>{r['n_estacoes']}</td></tr>"
        )
    tabela = "\n".join(linhas)

    g_serie = grafico_serie(facts["serie_nacional"])
    g_rank = grafico_ranking(facts["ranking_estados"], periodo)
    g_reg = grafico_regioes(facts["resumo_regioes"])

    return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="Entenda os sinais do El Niño no Brasil, os impactos regionais e os dados de estações do INMET.">
  <meta name="theme-color" content="#23252a">
  <title>El Niño 2026 · O sinal, o mapa e o que fazer</title>
  <link rel="icon" type="image/svg+xml" href="data:image/svg+xml;base64,{favicon}">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,600;0,9..144,700;1,9..144,400;1,9..144,600&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/css/bootstrap.min.css" rel="stylesheet" integrity="sha384-sRIl4kxILFvY47J16cr9ZwB07vP4J8+LH7qKQnuqkuIAvNWLzeN8tE5YBujZqJLB" crossorigin="anonymous">
  <style>
    :root {{
      color-scheme: light;
      --paper: #f6f5f1;
      --surface: #ffffff;
      --ink: #23252a;
      --ink-soft: #3a3d43;
      --muted: #737780;
      --line: #e4e2da;
      --line-strong: #d3d1c7;
      --moss: #5f6b45;
      --moss-deep: #47512f;
      --moss-soft: #eef0e6;
      --serif: "Fraunces", Georgia, "Times New Roman", serif;
      --sans: "Inter", "Segoe UI", system-ui, -apple-system, sans-serif;
    }}
    html {{ scroll-behavior: smooth; scroll-padding-top: 6rem; }}
    body {{ margin: 0; background: var(--paper); color: var(--ink); font-family: var(--sans); font-size: 1rem; line-height: 1.7; -webkit-font-smoothing: antialiased; }}
    h1, h2, h3 {{ font-family: var(--serif); font-weight: 600; letter-spacing: -.012em; }}
    p {{ margin: 0 0 1.1rem; }}
    a {{ color: var(--moss-deep); text-decoration: none; }}
    code {{ padding: .1em .4em; border-radius: 4px; background: var(--moss-soft); color: var(--moss-deep); font-family: ui-monospace, "SFMono-Regular", Consolas, monospace; font-size: .85em; }}
    .skip-link {{ position: absolute; left: 1rem; top: -5rem; z-index: 2000; padding: .7rem 1.1rem; border-radius: 6px; background: var(--ink); color: var(--paper); }}
    .skip-link:focus {{ top: 1rem; }}
    .mark {{ box-shadow: inset 0 -0.55em 0 var(--moss-soft); padding: 0 .12em; font-weight: 600; }}

    /* Micro-interação: sublinhado animado */
    .link-u {{ position: relative; font-weight: 500; }}
    .link-u::after {{ position: absolute; left: 0; bottom: -2px; width: 100%; height: 1px; background: currentColor; transform: scaleX(0); transform-origin: left; transition: transform .3s ease; content: ""; }}
    .link-u:hover::after, .link-u:focus-visible::after {{ transform: scaleX(1); }}

    /* Botões */
    .btn {{ display: inline-flex; align-items: center; gap: .5rem; padding: .78rem 1.45rem; border: 1px solid transparent; border-radius: 6px; font-family: var(--sans); font-size: .94rem; font-weight: 600; line-height: 1.4; transition: background-color .2s ease, color .2s ease, border-color .2s ease, transform .2s ease; }}
    .btn:focus-visible {{ outline: 2px solid var(--moss); outline-offset: 3px; }}
    .btn .arrow {{ transition: transform .25s ease; }}
    .btn:hover .arrow {{ transform: translateX(4px); }}
    .btn-ink {{ color: var(--paper); background: var(--ink); }}
    .btn-ink:hover {{ color: var(--paper); background: var(--moss-deep); }}
    .btn-ghost-ink {{ color: var(--ink); background: transparent; border-color: var(--line-strong); }}
    .btn-ghost-ink:hover {{ color: var(--moss-deep); border-color: var(--moss); }}
    .btn-moss {{ color: #fff; background: var(--moss); }}
    .btn-moss:hover {{ color: #fff; background: var(--moss-deep); }}
    .btn-light {{ color: var(--ink); background: var(--paper); }}
    .btn-light:hover {{ color: var(--moss-deep); background: #fff; }}
    .btn-sm {{ padding: .5rem 1rem; font-size: .85rem; }}

    .scroll-progress {{ position: fixed; inset: 0 0 auto; z-index: 1100; height: 2px; }}
    .scroll-progress span {{ display: block; width: 0; height: 100%; background: var(--moss); transition: width .1s linear; }}

    /* Navegação */
    .site-nav {{ position: sticky; top: 0; z-index: 1030; background: rgba(246, 245, 241, .92); backdrop-filter: saturate(160%) blur(12px); border-bottom: 1px solid transparent; transition: border-color .2s ease, background-color .2s ease; }}
    .site-nav.is-scrolled {{ border-bottom-color: var(--line); background: rgba(246, 245, 241, .98); }}
    .nav-inner {{ display: flex; align-items: center; gap: 1.25rem; min-height: 4.5rem; }}
    .brand {{ display: inline-flex; align-items: center; gap: .7rem; color: var(--ink); }}
    .brand-mark {{ display: grid; width: 2.1rem; height: 2.1rem; place-items: center; border-radius: 4px; background: var(--moss); color: #fff; font-family: var(--serif); font-size: 1.05rem; font-weight: 600; }}
    .brand-text {{ display: flex; flex-direction: column; line-height: 1.15; }}
    .brand-text strong {{ font-family: var(--serif); font-size: 1.02rem; font-weight: 600; }}
    .brand-text small {{ color: var(--muted); font-size: .7rem; letter-spacing: .04em; text-transform: uppercase; }}
    .nav-links {{ display: flex; gap: .35rem; margin-left: auto; }}
    .nav-link {{ padding: .45rem .8rem; color: var(--muted); font-size: .88rem; font-weight: 500; letter-spacing: .01em; }}
    .nav-link:hover, .nav-link:focus-visible {{ color: var(--ink); }}
    .nav-cta {{ flex: none; }}

    /* Hero */
    .hero {{ padding: clamp(3.25rem, 6.5vw, 6rem) 0 clamp(2.5rem, 5vw, 4rem); background: var(--paper); }}
    .hero-grid {{ display: grid; gap: clamp(2.25rem, 5vw, 4.5rem); grid-template-columns: 1.18fr .82fr; align-items: center; }}
    .eyebrow {{ display: block; margin: 0 0 1.1rem; color: var(--moss); font-size: .72rem; font-weight: 600; letter-spacing: .18em; text-transform: uppercase; }}
    .hero h1 {{ margin: 0; font-size: clamp(2.6rem, 6vw, 5.1rem); font-weight: 600; line-height: 1.03; letter-spacing: -.03em; text-wrap: balance; }}
    .hero h1 em {{ font-style: italic; font-weight: 400; }}
    .hero-lede {{ max-width: 33rem; margin: 1.5rem 0 0; color: var(--ink-soft); font-size: clamp(1rem, 1.5vw, 1.13rem); }}
    .hero-actions {{ display: flex; flex-wrap: wrap; gap: .7rem; margin-top: 2.25rem; }}
    .hero-trust {{ display: flex; flex-wrap: wrap; gap: .4rem 1.6rem; margin: 2rem 0 0; padding: 0; list-style: none; color: var(--muted); font-size: .84rem; }}
    .hero-trust li {{ display: flex; align-items: center; gap: .5rem; }}
    .hero-trust li::before {{ width: .3rem; height: .3rem; background: var(--moss); content: ""; }}

    /* Dossiê (bloco grafite) */
    .dossier {{ padding: clamp(1.5rem, 3vw, 2.25rem); border-radius: 8px; background: var(--ink); color: var(--paper); }}
    .dossier-label {{ margin: 0; color: #b9c39b; font-size: .7rem; font-weight: 600; letter-spacing: .18em; text-transform: uppercase; }}
    .dossier-month {{ margin: .5rem 0 1.5rem; font-family: var(--serif); font-size: clamp(2rem, 4vw, 2.9rem); font-weight: 600; line-height: 1; }}
    .dossier-list {{ display: grid; gap: 0; margin: 0; }}
    .dossier-list > div {{ display: flex; align-items: baseline; justify-content: space-between; gap: 1rem; padding: .75rem 0; border-top: 1px solid rgba(246, 245, 241, .16); }}
    .dossier-list dt {{ color: rgba(246, 245, 241, .68); font-size: .82rem; font-weight: 400; }}
    .dossier-list dd {{ margin: 0; font-family: var(--serif); font-size: 1.15rem; font-weight: 600; }}

    /* Faixa de números */
    .stats-band {{ border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); background: var(--surface); }}
    .stats-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); }}
    .stat-cell {{ min-width: 0; padding: 1.5rem 1.25rem; border-right: 1px solid var(--line); }}
    .stat-cell:first-child {{ padding-left: 0; }}
    .stat-cell:last-child {{ border-right: 0; }}
    .stat-cell strong {{ display: block; font-family: var(--serif); font-size: clamp(1.35rem, 2.4vw, 1.85rem); font-weight: 600; letter-spacing: -.02em; }}
    .stat-period {{ font-size: clamp(1rem, 1.35vw, 1.45rem) !important; letter-spacing: -.03em !important; white-space: nowrap; }}
    .stat-cell span {{ color: var(--muted); font-size: .8rem; letter-spacing: .02em; }}
    .stats-source {{ padding: .85rem 0; border-top: 1px solid var(--line); color: var(--muted); font-size: .78rem; }}

    /* Seções */
    .section {{ padding: clamp(3rem, 6vw, 5rem) 0; }}
    .section-head h2 {{ margin: 0 0 .7rem; font-size: clamp(1.7rem, 3.2vw, 2.4rem); }}
    .section-head p {{ max-width: 40rem; margin: 0; color: var(--muted); }}
    .section-roadmap {{ border-bottom: 1px solid var(--line); background: var(--surface); }}

    /* Roteiro: lista editorial, sem cartões idênticos */
    .roadmap-list {{ margin: 0; padding: 0; list-style: none; border-top: 1px solid var(--line); }}
    .roadmap-item {{ border-bottom: 1px solid var(--line); }}
    .roadmap-item a {{ display: grid; grid-template-columns: 3.5rem 1fr auto; align-items: baseline; gap: 1.25rem; padding: 1.35rem .25rem; color: inherit; transition: padding-left .25s ease, color .2s ease; }}
    .roadmap-item a:hover, .roadmap-item a:focus-visible {{ padding-left: .85rem; color: var(--moss-deep); }}
    .roadmap-num {{ font-family: var(--serif); font-size: 1.5rem; font-weight: 600; color: var(--line-strong); transition: color .25s ease; }}
    .roadmap-item a:hover .roadmap-num, .roadmap-item a:focus-visible .roadmap-num {{ color: var(--moss); }}
    .roadmap-body h3 {{ margin: 0 0 .25rem; font-size: 1.1rem; font-weight: 600; }}
    .roadmap-body p {{ margin: 0; color: var(--muted); font-size: .92rem; }}
    .roadmap-go {{ color: var(--line-strong); transition: transform .25s ease, color .25s ease; }}
    .roadmap-item a:hover .roadmap-go, .roadmap-item a:focus-visible .roadmap-go {{ transform: translateX(5px); color: var(--moss); }}
    .progress-panel {{ padding: 1.35rem 1.5rem; border: 1px solid var(--line); border-radius: 8px; }}
    .progress {{ height: .45rem; border-radius: 0; background: #ebe9e2; overflow: hidden; }}
    .progress-bar {{ border-radius: 0; background: var(--moss); transition: width .3s ease; }}

    /* Índice lateral */
    .toc {{ position: sticky; top: 6.25rem; }}
    .toc-nav {{ display: flex; flex-direction: column; border-left: 1px solid var(--line); }}
    .toc-link {{ position: relative; padding: .55rem 0 .55rem 1rem; color: var(--muted); font-size: .88rem; transition: color .2s ease; }}
    .toc-link::before {{ position: absolute; left: -1px; top: 0; width: 2px; height: 100%; background: var(--moss); transform: scaleY(0); transform-origin: top; transition: transform .25s ease; content: ""; }}
    .toc-link:hover {{ color: var(--ink); }}
    .toc-link.active {{ color: var(--ink); font-weight: 600; }}
    .toc-link.active::before {{ transform: scaleY(1); }}
    .resume-card {{ margin-top: 1.75rem; padding: 1.35rem 1.5rem; border: 1px solid var(--line); border-radius: 8px; background: var(--moss-soft); }}
    .resume-card p {{ color: var(--ink-soft); font-size: .87rem; }}

    /* Documento */
    .doc-section {{ padding: clamp(2.5rem, 4.5vw, 3.5rem) 0; border-top: 1px solid var(--line); scroll-margin-top: 6.25rem; }}
    .doc-section:first-of-type {{ border-top: 0; padding-top: 0; }}
    .kicker {{ display: block; margin: 0 0 .85rem; color: var(--moss); font-size: .72rem; font-weight: 600; letter-spacing: .18em; text-transform: uppercase; }}
    .doc-section h2 {{ margin: 0 0 1.4rem; font-size: clamp(1.55rem, 2.9vw, 2.15rem); max-width: 34ch; }}
    .lead-text {{ font-size: 1.1rem; color: var(--ink-soft); }}
    .sub-head {{ margin: 1.75rem 0 .6rem; font-size: .78rem; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; color: var(--muted); }}
    .tight-list {{ margin: 0 0 1.25rem; padding-left: 1.1rem; }}
    .tight-list li {{ margin-bottom: .35rem; }}
    .footnote {{ color: var(--muted); font-size: .84rem; }}
    .figure-block {{ margin: 0 0 1.5rem; }}
    .figure-block img {{ display: block; width: 100%; height: auto; border-radius: 6px; background: #fff; }}
    .figure-block figcaption {{ margin-top: .7rem; color: var(--muted); font-size: .8rem; }}

    .spec-panel {{ padding: 1.4rem 1.5rem; border: 1px solid var(--line); border-radius: 8px; }}
    .spec-title {{ margin: 0 0 .5rem; font-family: var(--serif); font-size: 1.02rem; font-weight: 600; }}
    .spec-list {{ margin: 0; }}
    .spec-list > div {{ display: flex; align-items: baseline; justify-content: space-between; gap: 1rem; padding: .65rem 0; border-top: 1px solid var(--line); }}
    .spec-list dt {{ color: var(--muted); font-size: .83rem; }}
    .spec-list dd {{ margin: 0; font-weight: 600; }}

    .region-list {{ margin: 0 0 1.25rem; padding: 0; list-style: none; }}
    .region-list li {{ position: relative; padding: .6rem 0 .6rem 1.4rem; border-top: 1px solid var(--line); }}
    .region-list li::before {{ position: absolute; left: 0; top: 1.15rem; width: .5rem; height: .5rem; background: var(--moss); content: ""; }}

    .note-panel {{ padding: 1.5rem; border-left: 2px solid var(--moss); background: var(--moss-soft); }}
    .note-title {{ margin: 0 0 .5rem; font-family: var(--serif); font-size: 1.02rem; font-weight: 600; }}
    .note-panel p:last-child {{ margin-bottom: 0; }}

    .meta-panel {{ padding: 1.6rem; border-radius: 8px; background: var(--ink); color: var(--paper); }}
    .meta-title {{ margin: 0 0 .9rem; font-family: var(--serif); font-size: 1.05rem; font-weight: 600; }}
    .meta-list {{ margin: 0; padding: 0; list-style: none; }}
    .meta-list li {{ display: flex; align-items: baseline; gap: .9rem; padding: .6rem 0; border-top: 1px solid rgba(246, 245, 241, .16); color: rgba(246, 245, 241, .82); font-size: .9rem; }}
    .meta-list b {{ min-width: 2.6rem; font-family: var(--serif); font-size: 1.05rem; font-weight: 600; color: #fff; }}

    .table-wrap {{ overflow-x: auto; border: 1px solid var(--line); border-radius: 6px; }}
    .table {{ min-width: 780px; margin: 0; font-size: .86rem; vertical-align: middle; }}
    .table thead th {{ color: var(--paper); background: var(--ink); white-space: nowrap; font-weight: 600; }}
    .table tbody tr:hover {{ background: var(--moss-soft); }}
    summary {{ cursor: pointer; }}
    summary::marker {{ color: var(--moss); }}

    .completion-btn {{ color: var(--moss-deep); background: var(--moss-soft); border: 1px solid transparent; }}
    .completion-btn:hover {{ color: #fff; background: var(--moss); }}
    .completion-btn[aria-pressed="true"] {{ color: #fff; background: var(--moss); }}

    /* Faixa final */
    .cta-band {{ padding: clamp(2.5rem, 5vw, 4rem) 0; background: var(--ink); color: var(--paper); }}
    .cta-inner {{ display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 1.75rem; }}
    .cta-inner .eyebrow {{ color: #b9c39b; }}
    .cta-inner h2 {{ margin: 0 0 .6rem; font-size: clamp(1.5rem, 3vw, 2.15rem); }}
    .cta-inner p {{ max-width: 38rem; margin: 0; color: rgba(246, 245, 241, .72); }}
    .cta-actions {{ display: flex; flex-wrap: wrap; gap: .7rem; }}

    /* Rodapé */
    .site-footer {{ padding: 2.5rem 0; border-top: 1px solid var(--line); color: var(--muted); font-size: .85rem; }}
    .privacy-note {{ margin: 1rem 0 0; max-width: 52rem; font-size: .8rem; }}

    /* Agente */
    .agent-launcher {{ position: fixed; right: 1.25rem; bottom: 1.25rem; z-index: 1040; display: inline-flex; align-items: center; justify-content: center; gap: .6rem; min-height: 3.4rem; padding: .7rem 1.2rem; border: 0; border-radius: 999px; color: var(--paper); background: var(--ink); box-shadow: 0 10px 26px rgba(35, 37, 42, .22); font-family: var(--sans); font-size: .9rem; font-weight: 600; transition: background-color .2s ease, transform .2s ease; }}
    .agent-launcher:hover {{ transform: translateY(-2px); background: var(--moss-deep); }}
    .agent-launcher:focus-visible, .agent-close:focus-visible {{ outline: 2px solid var(--moss); outline-offset: 3px; }}
    .agent-launcher svg {{ width: 1.2rem; height: 1.2rem; flex: none; }}
    .agent-panel[hidden] {{ display: none !important; }}
    .agent-panel:not([hidden]) {{ position: fixed; right: 1.25rem; bottom: 5.5rem; z-index: 1040; display: flex; width: min(420px, calc(100vw - 2rem)); height: min(680px, calc(100dvh - 7rem)); flex-direction: column; overflow: hidden; border: 1px solid var(--line); border-radius: 8px; background: #fff; box-shadow: 0 24px 60px rgba(35, 37, 42, .22); }}
    .agent-panel-head {{ display: flex; align-items: center; justify-content: space-between; gap: 1rem; padding: .95rem 1.05rem; background: var(--ink); color: var(--paper); }}
    .agent-panel-head strong {{ display: block; font-family: var(--serif); font-size: .98rem; font-weight: 600; }}
    .agent-panel-head span {{ display: block; color: rgba(246, 245, 241, .7); font-size: .76rem; }}
    .agent-panel-actions {{ display: flex; align-items: center; gap: .8rem; }}
    .agent-panel-actions a {{ color: #b9c39b; font-size: .78rem; font-weight: 600; white-space: nowrap; }}
    .agent-close {{ display: grid; width: 2.1rem; height: 2.1rem; flex: none; place-items: center; border: 0; border-radius: 4px; color: var(--paper); background: rgba(246, 245, 241, .12); font-size: 1.2rem; }}
    .agent-frame {{ width: 100%; height: 100%; flex: 1; border: 0; background: var(--paper); }}

    /* Revelação suave ao rolar */
    .reveal {{ opacity: 0; transform: translateY(14px); transition: opacity .6s ease, transform .6s ease; }}
    .reveal.is-visible {{ opacity: 1; transform: none; }}

    @media (max-width: 991.98px) {{
      .hero-grid {{ grid-template-columns: 1fr; }}
      .toc {{ position: static; margin-bottom: 2rem; }}
      .stats-grid {{ grid-template-columns: repeat(2, 1fr); }}
      .stat-cell:nth-child(2) {{ border-right: 0; }}
      .stat-cell:nth-child(-n+2) {{ border-bottom: 1px solid var(--line); }}
    }}
    @media (max-width: 767.98px) {{
      .nav-links {{ display: none; }}
      .nav-cta {{ margin-left: auto; }}
      .brand-text small {{ display: none; }}
      .roadmap-item a {{ grid-template-columns: 2.6rem 1fr auto; gap: .9rem; }}
    }}
    @media (max-width: 575.98px) {{
      .hero-trust {{ display: none; }}
      .agent-launcher {{ right: 1rem; bottom: 1rem; width: 3.4rem; height: 3.4rem; min-height: 0; padding: 0; }}
      .agent-launcher-label {{ position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; }}
      .agent-panel:not([hidden]) {{ right: .5rem; bottom: 4.75rem; width: calc(100vw - 1rem); height: calc(100dvh - 5.25rem); }}
      .agent-panel-actions a {{ font-size: .7rem; }}
    }}
    @media (prefers-reduced-motion: reduce) {{
      .reveal {{ opacity: 1; transform: none; }}
      *, *::before, *::after {{ scroll-behavior: auto !important; transition-duration: .01ms !important; animation-duration: .01ms !important; }}
    }}
    @media print {{ .site-nav, .toc, .resume-card, .completion-btn, .hero-actions, .scroll-progress, .agent-launcher, .agent-panel, .cta-band {{ display: none !important; }} body {{ background: #fff; }} .doc-section {{ break-inside: avoid; }} }}
  </style>
</head>
<body>
  <a class="skip-link" href="#conteudo">Pular para o conteúdo</a>
  <div class="scroll-progress" aria-hidden="true"><span id="scroll-bar"></span></div>

  <nav class="site-nav" aria-label="Navegação principal">
    <div class="container nav-inner">
      <a class="brand" href="#inicio">
        <span class="brand-mark" aria-hidden="true">E</span>
        <span class="brand-text"><strong>Clima em foco</strong><small>El Niño · INMET 2024–2026</small></span>
      </a>
      <div class="nav-links">
        <a class="nav-link" href="#roteiro">Roteiro</a>
        <a class="nav-link" href="#a-confirmacao">Análise</a>
        <a class="nav-link" href="#estados">Dados</a>
        <a class="nav-link" href="#fontes">Fontes</a>
      </div>
      <button class="btn btn-ink nav-cta" type="button" data-open-agent>Agente</button>
    </div>
  </nav>

  <header class="hero" id="inicio">
    <div class="container hero-grid">
      <div class="hero-copy">
        <p class="eyebrow">Monitoramento climático · dados do INMET</p>
        <h1>El Niño 2026,<br>em <em>contexto</em>.</h1>
        <p class="hero-lede">{resumo_hero}</p>
        <div class="hero-actions">
          <a class="btn btn-ink" href="#roteiro">Explorar a análise <span class="arrow" aria-hidden="true">→</span></a>
          <button class="btn btn-ghost-ink" type="button" data-open-agent>Falar com o agente</button>
        </div>
        <ul class="hero-trust">
          <li>{facts['n_estacoes']} estações automáticas</li>
          <li>{facts['n_ufs']} unidades federativas</li>
          <li>Série {facts['periodo_dados']['min']}–{facts['periodo_dados']['max']}</li>
        </ul>
      </div>
      {dossie}
    </div>
  </header>

  <div class="stats-band">
    <div class="container">
      <div class="stats-grid">
        <div class="stat-cell"><strong>{facts['n_estacoes']}</strong><span>estações analisadas</span></div>
        <div class="stat-cell"><strong>{facts['n_ufs']}</strong><span>unidades federativas</span></div>
        <div class="stat-cell"><strong class="stat-period">{periodo_observado}</strong><span>período observado</span></div>
        <div class="stat-cell"><strong>{facts['gerado_em'][:10]}</strong><span>data desta análise</span></div>
      </div>
      <p class="stats-source mb-0">Fonte: estações automáticas do INMET · {facts['n_observacoes_mensais']:,} observações mensais · nenhuma pergunta é enviada a serviços externos.</p>
    </div>
  </div>

  <section class="section section-roadmap" id="roteiro" aria-labelledby="roteiro-titulo">
    <div class="container">
      <div class="row g-5">
        <div class="col-lg-5">
          <div class="section-head reveal">
            <p class="eyebrow">Seu roteiro</p>
            <h2 id="roteiro-titulo">Ao final, você vai saber</h2>
            <p>Siga as etapas na ordem ou vá direto à pergunta que quer responder.</p>
          </div>
          <div class="progress-panel reveal">
            <div class="d-flex justify-content-between gap-2 small fw-semibold mb-2">
              <span>Progresso da leitura</span><span id="progress-count">0 de 5 etapas</span>
            </div>
            <div class="progress" role="progressbar" aria-label="Progresso das etapas" aria-valuemin="0" aria-valuemax="5" aria-valuenow="0">
              <div class="progress-bar" id="progress-bar" style="width: 0%"></div>
            </div>
          </div>
        </div>
        <div class="col-lg-7">
          <ol class="roadmap-list">
            <li class="roadmap-item reveal"><a href="#a-confirmacao"><span class="roadmap-num">01</span><span class="roadmap-body"><h3>Identificar a confirmação</h3><p>Veja o mês e o critério usados para reconhecer a anomalia.</p></span><span class="roadmap-go" aria-hidden="true">→</span></a></li>
            <li class="roadmap-item reveal"><a href="#impacto-regional"><span class="roadmap-num">02</span><span class="roadmap-body"><h3>Comparar os impactos</h3><p>Entenda por que cada região apresenta sinais diferentes.</p></span><span class="roadmap-go" aria-hidden="true">→</span></a></li>
            <li class="roadmap-item reveal"><a href="#estados"><span class="roadmap-num">03</span><span class="roadmap-body"><h3>Explorar os dados</h3><p>Leia o ranking, a evolução mensal e as fontes consultadas.</p></span><span class="roadmap-go" aria-hidden="true">→</span></a></li>
          </ol>
        </div>
      </div>
    </div>
  </section>

  <main class="section" id="conteudo">
    <div class="container">
      <div class="row g-5">
        <aside class="col-lg-3" aria-label="Etapas desta leitura">
          <div class="toc">
            <p class="eyebrow mb-3">Nesta leitura</p>
            <nav class="toc-nav mb-4" aria-label="Índice do relatório">
              <a class="toc-link" href="#a-confirmacao">Quando foi confirmada</a>
              <a class="toc-link" href="#impacto-regional">Impacto por região</a>
              <a class="toc-link" href="#estados">Estados em destaque</a>
              <a class="toc-link" href="#evolucao">Evolução no tempo</a>
              <a class="toc-link" href="#fontes">Orientações e fontes</a>
            </nav>
            <div class="resume-card">
              <p class="eyebrow mb-2">Retome quando quiser</p>
              <p class="mb-3" id="resume-message">Seu progresso fica salvo neste navegador.</p>
              <button class="btn btn-moss btn-sm" type="button" data-resume>Retomar leitura</button>
            </div>
          </div>
        </aside>

        <div class="col-lg-9">
          <section class="doc-section reveal" id="a-confirmacao" data-lesson tabindex="-1" aria-labelledby="confirmacao-titulo">
            <p class="kicker">Etapa 01 — O sinal</p>
            <h2 id="confirmacao-titulo">Quando o El Niño foi identificado?</h2>
            <div class="row g-4 g-lg-5">
              <div class="col-lg-7">
                {bloco_conf}
                <p>Para cada estação, a anomalia mensal é comparada à climatologia do mesmo mês. O <i>z-score interno</i> divide essa diferença pelo desvio-padrão das anomalias da estação, calculado dentro do período analisado ({facts['periodo_dados']['min']} a {facts['periodo_dados']['max']}).</p>
                <p>Para confirmar, o z médio de temperatura deve ser &ge; {facts['z_calor_conf']:.1f}&sigma; e pelo menos {facts['frac_conf']*100:.0f}% das estações precisam registrar z &ge; {facts['z_calor_conf']:.1f}. Um valor isolado não basta: a leitura combina a intensidade média do sinal com a proporção de estações que o observaram.</p>
              </div>
              <div class="col-lg-5">
                {ficha}
                <p class="footnote mt-3 mb-0">O limiar |z| &ge; {facts['z_limiar']} é usado nos indicadores gerais; a confirmação do aquecimento usa um critério próprio.</p>
              </div>
            </div>
            <button class="btn completion-btn mt-4" type="button" data-complete aria-pressed="false">Marcar etapa como concluída</button>
          </section>

          <section class="doc-section reveal" id="impacto-regional" data-lesson tabindex="-1" aria-labelledby="regiao-titulo">
            <p class="kicker">Etapa 02 — O lugar</p>
            <h2 id="regiao-titulo">O impacto muda de região para região</h2>
            <div class="row g-4 g-lg-5 align-items-center">
              <div class="col-lg-6">
                <figure class="figure-block mb-0">
                  <img src="data:image/png;base64,{g_reg}" alt="Gráfico de barras comparando o índice médio de impacto nas cinco regiões do Brasil">
                  <figcaption>Índice médio de impacto por região na janela analisada.</figcaption>
                </figure>
              </div>
              <div class="col-lg-6">
                <ul class="region-list">
                  <li><b>Norte</b> e <b>Nordeste</b> — tendência de condições mais secas.</li>
                  <li><b>Centro-Oeste</b> e <b>Sudeste</b> — calor acima do padrão e chuva irregular.</li>
                  <li><b>Sul</b> — precipitação acima do padrão.</li>
                </ul>
                <p class="footnote mb-0">O índice é comparativo e resume os sinais observados na janela analisada; não representa uma previsão isolada para cada município.</p>
              </div>
            </div>
            <button class="btn completion-btn mt-4" type="button" data-complete aria-pressed="false">Marcar etapa como concluída</button>
          </section>

          <section class="doc-section reveal" id="estados" data-lesson tabindex="-1" aria-labelledby="estados-titulo">
            <p class="kicker">Etapa 03 — Os estados</p>
            <h2 id="estados-titulo">Onde os sinais mais se destacam?</h2>
            <p class="lead-text">Este ranking combina indicadores alinhados ao perfil climático de cada região no período {periodo}. Use-o para comparar sinais, não como previsão determinística.</p>
            <figure class="figure-block">
              <img src="data:image/png;base64,{g_rank}" alt="Ranking dos 15 estados com maior índice comparativo de impacto pelo El Niño no período {periodo}">
              <figcaption>Janela analisada: {periodo} — da confirmação/início da anomalia até o último mês com dados.</figcaption>
            </figure>
            <details class="mb-3">
              <summary class="fw-semibold py-2">Abrir tabela completa dos estados</summary>
              <div class="table-wrap mt-3">
                <table class="table table-striped">
                  <caption class="caption-top px-3">Indicadores comparativos por unidade federativa, {periodo}.</caption>
                  <thead><tr><th scope="col">#</th><th scope="col">UF</th><th scope="col">Região</th><th scope="col">Índice</th><th scope="col">Calor (z)</th><th scope="col">Seca (z)</th><th scope="col">Chuva (z)</th><th scope="col">% meses quentes</th><th scope="col">Dias Tmax&ge;35</th><th scope="col">Estações</th></tr></thead>
                  <tbody>{tabela}</tbody>
                </table>
              </div>
            </details>
            <button class="btn completion-btn mt-2" type="button" data-complete aria-pressed="false">Marcar etapa como concluída</button>
          </section>

          <section class="doc-section reveal" id="evolucao" data-lesson tabindex="-1" aria-labelledby="evolucao-titulo">
            <p class="kicker">Etapa 04 — Ao longo do tempo</p>
            <h2 id="evolucao-titulo">Acompanhe a evolução mensal</h2>
            <div class="row g-4 g-lg-5">
              <div class="col-lg-8">
                <figure class="figure-block mb-0">
                  <img src="data:image/png;base64,{g_serie}" alt="Série temporal mensal de anomalias de temperatura e precipitação e percentual de estações com sinal de calor">
                  <figcaption>Anomalias mensais de temperatura e chuva e fração de estações com sinal de calor.</figcaption>
                </figure>
              </div>
              <div class="col-lg-4">
                <div class="note-panel">
                  <p class="note-title">Leia com atenção</p>
                  <p class="mb-0">A série descreve os dados disponíveis até {facts['periodo_dados']['max']}; novos meses podem alterar a leitura do cenário.</p>
                </div>
              </div>
            </div>
            <button class="btn completion-btn mt-4" type="button" data-complete aria-pressed="false">Marcar etapa como concluída</button>
          </section>

          <section class="doc-section reveal" id="fontes" data-lesson tabindex="-1" aria-labelledby="fontes-titulo">
            <p class="kicker">Etapa 05 — Próximos passos</p>
            <h2 id="fontes-titulo">Orientações confiáveis e limites da análise</h2>
            <div class="row g-4 g-lg-5">
              <div class="col-lg-7">
                <p>Para orientações oficiais de saúde e avisos de calor extremo, consulte o <b>Portal Gov.br — El Niño</b>.</p>
                <p><a class="link-u" href="https://www.gov.br/saude/pt-br/assuntos/saude-de-a-a-z/e/el-nino" target="_blank" rel="noopener noreferrer">Abrir orientações do Ministério da Saúde <span aria-hidden="true">→</span></a></p>
                <p class="footnote">Análise gerada a partir de dados horários do INMET. O índice de impacto é um indicador comparativo derivado dos dados e não substitui boletins oficiais de monitoramento do INMET, ANA, CPTEC/INPE ou da Defesa Civil.</p>
              </div>
              <div class="col-lg-5">
                <div class="meta-panel">
                  <p class="meta-title">Em emergências</p>
                  <ul class="meta-list">
                    <li><b>199</b> Defesa Civil</li>
                    <li><b>192</b> SAMU</li>
                    <li><b>193</b> Bombeiros</li>
                  </ul>
                </div>
              </div>
            </div>
            <button class="btn completion-btn mt-4" type="button" data-complete aria-pressed="false">Marcar etapa como concluída</button>
          </section>
        </div>
      </div>
    </div>
  </main>

  <section class="cta-band" aria-labelledby="cta-titulo">
    <div class="container cta-inner">
      <div>
        <p class="eyebrow">Dúvidas sobre o fenômeno?</p>
        <h2 id="cta-titulo">Tire dúvidas com o agente offline</h2>
        <p>Respostas baseadas nesta análise, por região e por estado. Nenhuma pergunta sai do seu navegador.</p>
      </div>
      <div class="cta-actions">
        <button class="btn btn-light" type="button" data-open-agent>Abrir o agente</button>
        <a class="btn btn-moss" href="{agent_url}" target="_blank" rel="noopener noreferrer">Nova aba <span aria-hidden="true">↗</span></a>
      </div>
    </div>
  </section>

  <footer class="site-footer">
    <div class="container">
      <div class="d-flex flex-column flex-sm-row justify-content-between gap-2">
        <span>Fonte dos dados: estações automáticas do INMET · {facts['periodo_dados']['min']}–{facts['periodo_dados']['max']}</span>
        <span>Relatório gerado em {facts['gerado_em']}</span>
      </div>
      <p class="privacy-note">O agente de dúvidas responde com base nesta análise, sem enviar suas perguntas para serviços externos.</p>
    </div>
  </footer>

  <button class="agent-launcher" type="button" id="agent-launcher" aria-expanded="false" aria-controls="agent-panel">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 11.5a8.4 8.4 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7a8.4 8.4 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.4 8.4 0 0 1 3.8-.9h.5a8.5 8.5 0 0 1 8 8v.5z"/></svg>
    <span class="agent-launcher-label">Pergunte ao agente</span>
  </button>

  <section class="agent-panel" id="agent-panel" hidden aria-label="Agente de dúvidas sobre o El Niño">
    <header class="agent-panel-head">
      <div>
        <strong>Agente do El Niño</strong>
        <span>Respostas com base nesta análise</span>
      </div>
      <div class="agent-panel-actions">
        <a href="{agent_url}" target="_blank" rel="noopener noreferrer">Abrir em nova aba ↗</a>
        <button class="agent-close" type="button" id="agent-close" aria-label="Fechar o agente">&times;</button>
      </div>
    </header>
    <iframe class="agent-frame" id="agent-frame" src="about:blank" data-src="{agent_url}" title="Agente de dúvidas sobre o El Niño" loading="lazy"></iframe>
  </section>
  <script>
    (() => {{
      const lessons = [...document.querySelectorAll("[data-lesson]")];
      const links = [...document.querySelectorAll(".toc-link")];
      const completeKey = "elnino-report-completed-v1";
      const lastKey = "elnino-report-last-section-v1";
      const progress = document.querySelector(".progress");
      const progressBar = document.getElementById("progress-bar");
      const progressCount = document.getElementById("progress-count");
      const resumeMessage = document.getElementById("resume-message");
      const scrollBar = document.getElementById("scroll-bar");
      const siteNav = document.querySelector(".site-nav");
      const readStorage = (key, fallback = "") => {{
        try {{ return localStorage.getItem(key) || fallback; }} catch {{ return fallback; }}
      }};
      const writeStorage = (key, value) => {{
        try {{ localStorage.setItem(key, value); }} catch {{ /* Progresso segue ativo durante esta visita. */ }}
      }};
      let completed = new Set();
      try {{ completed = new Set(JSON.parse(readStorage(completeKey, "[]"))); }} catch {{ completed = new Set(); }}

      const renderProgress = () => {{
        const count = lessons.filter((lesson) => completed.has(lesson.id)).length;
        progressCount.textContent = count + " de " + lessons.length + " etapas";
        progress.setAttribute("aria-valuenow", String(count));
        progressBar.style.width = (count / lessons.length) * 100 + "%";
        resumeMessage.textContent = count === lessons.length
          ? "Leitura concluída. Você pode revisar qualquer etapa."
          : count + " de " + lessons.length + " etapas concluídas. Seu progresso fica salvo neste navegador.";
        document.querySelectorAll("[data-complete]").forEach((button) => {{
          const done = completed.has(button.closest("[data-lesson]").id);
          button.setAttribute("aria-pressed", String(done));
          button.textContent = done ? "Etapa concluída ✓" : "Marcar etapa como concluída";
        }});
      }};

      document.querySelectorAll("[data-complete]").forEach((button) => {{
        button.addEventListener("click", () => {{
          const lessonId = button.closest("[data-lesson]").id;
          if (completed.has(lessonId)) completed.delete(lessonId);
          else completed.add(lessonId);
          writeStorage(completeKey, JSON.stringify([...completed]));
          renderProgress();
        }});
      }});

      document.querySelectorAll("[data-resume]").forEach((button) => {{
        button.addEventListener("click", () => {{
          const savedId = readStorage(lastKey);
          const savedLesson = lessons.find((lesson) => lesson.id === savedId && !completed.has(lesson.id));
          const nextLesson = lessons.find((lesson) => !completed.has(lesson.id));
          const target = savedLesson || nextLesson || lessons[0];
          target.scrollIntoView({{ behavior: "smooth", block: "start" }});
          target.focus({{ preventScroll: true }});
        }});
      }});

      const observer = new IntersectionObserver((entries) => {{
        entries.forEach((entry) => {{
          if (!entry.isIntersecting) return;
          writeStorage(lastKey, entry.target.id);
          links.forEach((link) => link.classList.toggle("active", link.hash === "#" + entry.target.id));
        }});
      }}, {{ rootMargin: "-20% 0px -65% 0px" }});
      lessons.forEach((lesson) => observer.observe(lesson));

      // Revelação suave dos blocos ao entrar na viewport.
      const revelar = new IntersectionObserver((entries, obs) => {{
        entries.forEach((entry) => {{
          if (!entry.isIntersecting) return;
          entry.target.classList.add("is-visible");
          obs.unobserve(entry.target);
        }});
      }}, {{ rootMargin: "0px 0px -8% 0px", threshold: 0.08 }});
      document.querySelectorAll(".reveal").forEach((el) => revelar.observe(el));

      const launcher = document.getElementById("agent-launcher");
      const panel = document.getElementById("agent-panel");
      const panelClose = document.getElementById("agent-close");
      const frame = document.getElementById("agent-frame");
      const setPanel = (open) => {{
        panel.hidden = !open;
        launcher.setAttribute("aria-expanded", String(open));
        if (open) {{
          if (frame && frame.src !== frame.dataset.src) frame.src = frame.dataset.src;
          (panelClose || launcher).focus();
        }} else {{
          launcher.focus();
        }}
      }};
      document.querySelectorAll("[data-open-agent]").forEach((el) => el.addEventListener("click", () => setPanel(true)));
      launcher.addEventListener("click", () => setPanel(panel.hidden));
      panelClose.addEventListener("click", () => setPanel(false));
      document.addEventListener("keydown", (event) => {{
        if (event.key === "Escape" && !panel.hidden) setPanel(false);
      }});

      const onScroll = () => {{
        const root = document.documentElement;
        const max = root.scrollHeight - root.clientHeight;
        scrollBar.style.width = (max > 0 ? (root.scrollTop / max) * 100 : 0) + "%";
        siteNav.classList.toggle("is-scrolled", window.scrollY > 24);
      }};
      document.addEventListener("scroll", onScroll, {{ passive: true }});
      onScroll();

      renderProgress();
    }})();
  </script>
</body>
</html>"""


def main() -> None:
    if not FACTS.exists():
        raise SystemExit("facts.json nao encontrado. Rode analise_el_nino.py primeiro.")
    facts = json.loads(FACTS.read_text(encoding="utf-8"))
    DEST.write_text(html(facts), encoding="utf-8")
    print(f"Relatorio gerado: {DEST}")


if __name__ == "__main__":
    main()
