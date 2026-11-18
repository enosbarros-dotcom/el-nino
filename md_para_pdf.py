# -*- coding: utf-8 -*-
"""
Converte arquivos Markdown do projeto em PDF.

Renderiza o Markdown para HTML (markdown-it), desenha os blocos ```mermaid
e usa o Chrome/Edge em modo headless para gerar o PDF.

Uso:
    python md_para_pdf.py                 # converte todos os *.md da raiz
    python md_para_pdf.py docs_agente_el_nino.md
Saida:
    <nome>.pdf ao lado do .md
"""
from __future__ import annotations

import html
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from markdown_it import MarkdownIt
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.util import ClassNotFound

BASE = Path(__file__).resolve().parent

CSS = """
@page { size: A4; margin: 18mm 16mm 20mm; }
:root { --paper:#fbfaf7; --ink:#23252a; --moss:#5f6b45; --line:#e4e2da; --muted:#737780; }
* { box-sizing: border-box; }
body { margin:0; background:var(--paper); color:var(--ink);
  font-family:"Inter","Segoe UI",Arial,sans-serif; font-size:10.5pt; line-height:1.62; }
main { max-width: 172mm; margin: 0 auto; padding: 6mm 0 0; }
h1,h2,h3,h4 { font-family:"Fraunces","Georgia",serif; color:var(--ink); line-height:1.22;
  margin: 1.6em 0 .55em; font-weight:600; }
h1 { font-size:26pt; letter-spacing:-.02em; margin-top:0; }
h2 { font-size:17pt; padding-bottom:.28em; border-bottom:2px solid var(--moss); }
h3 { font-size:13pt; }
h4 { font-size:11pt; }
p { margin:.6em 0; }
a { color:var(--moss); text-decoration:none; border-bottom:1px solid rgba(95,107,69,.35); }
strong { font-weight:600; }
hr { border:0; border-top:1px solid var(--line); margin:2em 0; }
ul,ol { margin:.5em 0; padding-left:1.35em; }
li { margin:.24em 0; }
blockquote { margin:1em 0; padding:.7em 1.1em; border-left:3px solid var(--moss);
  background:#f3f2ec; color:#41443f; }
code { font-family:"Cascadia Mono","Consolas",monospace; font-size:9.3pt;
  background:#efeee8; padding:.12em .38em; border-radius:4px; }
pre { background:#f2f1eb; border:1px solid var(--line); border-radius:8px;
  padding:.85em 1em; overflow:auto; page-break-inside:avoid; }
pre code { background:none; padding:0; font-size:8.8pt; line-height:1.5; }
table { width:100%; border-collapse:collapse; margin:1em 0; font-size:9.6pt;
  page-break-inside:avoid; }
th,td { text-align:left; padding:.5em .7em; border-bottom:1px solid var(--line); vertical-align:top; }
th { background:#f3f2ec; font-weight:600; }
.mermaid { margin:1.1em 0; text-align:center; page-break-inside:avoid; }
.mermaid svg { max-width:100%; height:auto; }
.highlight .k{color:#5f6b45} .highlight .s,.highlight .s1,.highlight .s2{color:#7a4b2a}
.highlight .c,.highlight .c1{color:#8a8f85;font-style:italic} .highlight .nf{color:#2f3437}
.highlight .nn{color:#454d2e} .highlight .mi,.highlight .mf{color:#9a5b2c}
"""

MERMAID_INIT = """
<script type="module">
  import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';
  mermaid.initialize({ startOnLoad: false, theme: 'neutral',
    themeVariables: { fontFamily: 'Inter, Segoe UI, Arial, sans-serif', fontSize: '13px' } });
  window.addEventListener('load', async () => {
    await mermaid.run({ querySelector: '.mermaid' });
    document.title = 'pronto';
  });
</script>
"""


def _highlight(code: str, lang: str, _attrs) -> str:
    try:
        lexer = get_lexer_by_name(lang) if lang else guess_lexer(code)
    except ClassNotFound:
        return ""
    return highlight(code, lexer, HtmlFormatter(nowrap=True))


def _md() -> MarkdownIt:
    try:
        md = MarkdownIt("gfm-like", {"highlight": _highlight, "linkify": False})
    except Exception:
        md = MarkdownIt("commonmark", {"highlight": _highlight})
        md.enable(["table", "strikethrough"])
    padrao = md.renderer.rules.get("fence")

    def fence(tokens, idx, options, env):
        info = (tokens[idx].info or "").strip()
        if info.split(" ")[0] == "mermaid":
            return '<div class="mermaid">' + html.escape(tokens[idx].content) + "</div>"
        return padrao(tokens, idx, options, env)

    md.renderer.rules["fence"] = fence
    return md


def _navegador() -> str:
    candidatos = [
        shutil.which("chrome"),
        shutil.which("msedge"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for caminho in candidatos:
        if caminho and Path(caminho).exists():
            return caminho
    raise SystemExit("Chrome/Edge nao encontrado para gerar o PDF.")


def converter(md_path: Path, navegador: str) -> Path:
    corpo = _md().render(md_path.read_text(encoding="utf-8"))
    pagina = (
        "<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>"
        f"<title>{html.escape(md_path.stem)}</title>"
        "<link rel='preconnect' href='https://fonts.googleapis.com'>"
        "<link href='https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600"
        "&family=Inter:wght@400;500;600&display=swap' rel='stylesheet'>"
        f"<style>{CSS}</style>{MERMAID_INIT}</head>"
        f"<body><main>{corpo}</main></body></html>"
    )

    destino = md_path.with_suffix(".pdf")
    with tempfile.TemporaryDirectory() as tmp:
        html_tmp = Path(tmp) / "doc.html"
        html_tmp.write_text(pagina, encoding="utf-8")
        subprocess.run(
            [
                navegador, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                "--virtual-time-budget=20000", "--run-all-compositor-stages-before-draw",
                f"--print-to-pdf={destino}", html_tmp.as_uri(),
            ],
            capture_output=True,
            timeout=180,
        )
    return destino


def main() -> None:
    args = sys.argv[1:]
    arquivos = [BASE / a for a in args] if args else sorted(BASE.glob("*.md"))
    if not arquivos:
        raise SystemExit("Nenhum arquivo .md encontrado.")

    navegador = _navegador()
    for md_path in arquivos:
        if not md_path.exists():
            print(f"! nao encontrado: {md_path.name}")
            continue
        pdf = converter(md_path, navegador)
        tamanho = pdf.stat().st_size if pdf.exists() else 0
        print(f"PDF gerado: {pdf}  ({tamanho/1024:.0f} KB)")


if __name__ == "__main__":
    main()
