# -*- coding: utf-8 -*-
"""
Publica o site do El Nino na internet via tuneis Cloudflare (trycloudflare).

Deixe ESTA janela aberta: enquanto ela estiver ativa, os links publicos
funcionam. Ctrl+C encerra os tuneis e os servicos locais.

O que este script faz:
  1) Libera as portas 8765/8501 e reinicia o agente Streamlit com flags que
     permitem abrir dentro de um iframe (CORS/XSRF desativados).
  2) Sobe um servidor local que expoe APENAS o relatorio (nao expoe CSV/scripts).
  3) Abre um tunel publico para o site e outro para o agente.
  4) Regenera o HTML apontando o iframe para a URL publica do agente.
  5) Mostra os links publicos para voce compartilhar.

Uso:  python publicar.py
"""
from __future__ import annotations

import glob
import http.server
import os
import re
import shutil
import signal
import socketserver
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
REPORT = BASE / "relatorio_el_nino.html"
APP = BASE / "app_el_nino.py"
GERAR = BASE / "gerar_relatorio.py"

SITE_PORT = 8765
AGENT_PORT = 8501
PY = sys.executable


def cloudflared_path() -> str:
    achado = shutil.which("cloudflared")
    if achado:
        return achado
    for candidato in (
        r"C:\Program Files (x86)\cloudflared\cloudflared.exe",
        r"C:\Program Files\cloudflared\cloudflared.exe",
    ):
        if Path(candidato).exists():
            return candidato
    raise SystemExit(
        "cloudflared nao encontrado. Instale com: winget install --id Cloudflare.cloudflared"
    )


def escolher_python() -> str:
    """Retorna um interpretador que tenha streamlit instalado.

    O script pode ser chamado por um 'python' do PATH sem as dependencias;
    nesse caso procura uma instalacao local que tenha o streamlit.
    """
    candidatos = [sys.executable]
    candidatos += glob.glob(os.path.expanduser(r"~\AppData\Local\Programs\Python\Python3*\python.exe"))
    candidatos += glob.glob(r"C:\Program Files\Python3*\python.exe")
    vistos: set[str] = set()
    for caminho in candidatos:
        if caminho in vistos or not Path(caminho).exists():
            continue
        vistos.add(caminho)
        try:
            teste = subprocess.run([caminho, "-c", "import streamlit"], capture_output=True, timeout=60)
        except Exception:
            continue
        if teste.returncode == 0:
            return caminho
    print("  ! Nao encontrei um Python com 'streamlit' instalado; tentando o atual.")
    return sys.executable


def pid_na_porta(port: int) -> int | None:
    try:
        bruto = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True).stdout or b""
        saida = bruto.decode("oem", errors="ignore")
    except Exception:
        return None
    alvo = f":{port}"
    for linha in saida.splitlines():
        partes = linha.split()
        if len(partes) >= 5 and partes[3].upper() == "LISTENING" and partes[1].endswith(alvo):
            try:
                return int(partes[4])
            except ValueError:
                pass
    return None


def liberar_porta(port: int) -> None:
    pid = pid_na_porta(port)
    if pid:
        subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
        print(f"  - porta {port}: processo {pid} encerrado")


class _RelatorioHandler(http.server.BaseHTTPRequestHandler):
    """Serve apenas o relatorio, em '/' — nada de listagem de diretorio."""

    def do_GET(self) -> None:  # noqa: N802
        caminho = self.path.split("?", 1)[0]
        if caminho in ("/", "/index.html", "/relatorio_el_nino.html"):
            try:
                dados = REPORT.read_bytes()
            except FileNotFoundError:
                self.send_error(404, "Relatorio ainda nao gerado")
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(dados)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(dados)
        else:
            self.send_error(404)

    def log_message(self, *args) -> None:
        pass


def servir_relatorio(port: int) -> socketserver.TCPServer:
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(("127.0.0.1", port), _RelatorioHandler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def abrir_tunel(cf: str, alvo: str) -> tuple[subprocess.Popen, dict]:
    """Abre um quick tunnel e captura a URL publica do log do cloudflared."""
    proc = subprocess.Popen(
        [cf, "tunnel", "--url", alvo, "--no-autoupdate"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="ignore",
        bufsize=1,
    )
    estado: dict = {"url": None}

    def drenar() -> None:
        if proc.stdout is None:
            return
        for linha in proc.stdout:
            if estado["url"] is None:
                casado = re.search(r"https://[-\w.]+\.trycloudflare\.com", linha)
                if casado:
                    estado["url"] = casado.group(0)

    threading.Thread(target=drenar, daemon=True).start()

    inicio = time.time()
    while estado["url"] is None and proc.poll() is None and time.time() - inicio < 45:
        time.sleep(0.3)
    return proc, estado


def aguardar_http(port: int, timeout: float = 45) -> bool:
    inicio = time.time()
    while time.time() - inicio < timeout:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2) as resposta:
                if resposta.status < 500:
                    return True
        except Exception:
            time.sleep(0.5)
    return False


def main() -> None:
    global PY
    cf = cloudflared_path()
    filhos: list[subprocess.Popen] = []

    print("== Publicando o site do El Nino ==")
    PY = escolher_python()
    print("[1/5] Liberando portas e reiniciando servicos locais...")
    liberar_porta(SITE_PORT)
    liberar_porta(AGENT_PORT)
    # Remove tuneis orfaos de execucoes anteriores para permitir reexecucao limpa.
    subprocess.run(["taskkill", "/F", "/IM", "cloudflared.exe"], capture_output=True)

    httpd = servir_relatorio(SITE_PORT)
    print(f"  - relatorio local servido em http://127.0.0.1:{SITE_PORT}")

    streamlit = subprocess.Popen(
        [
            PY, "-m", "streamlit", "run", str(APP),
            "--server.port", str(AGENT_PORT),
            "--server.address", "127.0.0.1",
            "--server.headless", "true",
            "--server.enableCORS", "false",
            "--server.enableXsrfProtection", "false",
            "--browser.gatherUsageStats", "false",
        ],
        cwd=str(BASE),
    )
    filhos.append(streamlit)

    print("[2/5] Aguardando o agente Streamlit iniciar...")
    if aguardar_http(AGENT_PORT):
        print(f"  - agente local pronto em http://127.0.0.1:{AGENT_PORT}")
    else:
        print("  ! o agente ainda nao respondeu; os tuneis seguem sendo criados")

    print("[3/5] Abrindo tuneis Cloudflare (site e agente)...")
    proc_site, url_site = abrir_tunel(cf, f"http://127.0.0.1:{SITE_PORT}")
    proc_agente, url_agente = abrir_tunel(cf, f"http://127.0.0.1:{AGENT_PORT}")
    filhos.extend([proc_site, proc_agente])

    if not url_site["url"] or not url_agente["url"]:
        print("  ! Nao foi possivel obter uma das URLs publicas. Verifique a conexao.")

    print("[4/5] Regenerando o relatorio com a URL publica do agente...")
    ambiente = dict(os.environ)
    if url_agente["url"]:
        ambiente["ELNINO_AGENT_URL"] = url_agente["url"] + "/"
    subprocess.run([PY, str(GERAR)], cwd=str(BASE), env=ambiente, check=False)

    print("[5/5] Pronto.\n")
    print("=" * 66)
    print(f"  SITE   ->  {url_site['url'] or '(indisponivel)'}")
    print(f"  AGENTE ->  {url_agente['url'] or '(indisponivel)'}")
    print("=" * 66)
    print("Compartilhe o link do SITE. O agente abre pelo botao/painel do proprio site.")
    print("Mantenha esta janela aberta para o site seguir no ar. Ctrl+C encerra.\n")

    def encerrar(*_args) -> None:
        print("\nEncerrando tuneis e servicos locais...")
        for proc in filhos:
            if proc.poll() is None:
                proc.terminate()
        try:
            httpd.shutdown()
        except Exception:
            pass
        sys.exit(0)

    signal.signal(signal.SIGINT, encerrar)
    try:
        while True:
            time.sleep(1)
            if streamlit.poll() is not None:
                print("! O agente Streamlit parou inesperadamente. Encerrando.")
                encerrar()
    except KeyboardInterrupt:
        encerrar()


if __name__ == "__main__":
    main()
