# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    PORT=8501

WORKDIR /app

# Camada de dependencias primeiro (melhor cache de build no CI)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Codigo + dados. O caminho relativo saida/ e o esperado por app_el_nino.py,
# e favicon.svg e usado como page_icon no st.set_page_config.
COPY app_el_nino.py   ./app_el_nino.py
COPY favicon.svg      ./favicon.svg
COPY saida/facts.json ./saida/facts.json

EXPOSE 8501

# CORS/XSRF desligados: obrigatorio para o agente abrir dentro do <iframe> do relatorio.
CMD ["sh", "-c", "streamlit run app_el_nino.py \
  --server.port=${PORT} \
  --server.address=0.0.0.0 \
  --server.headless=true \
  --server.enableCORS=false \
  --server.enableXsrfProtection=false"]
