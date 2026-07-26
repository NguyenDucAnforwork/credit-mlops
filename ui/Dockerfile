FROM python:3.12-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# UI runtime deps are pinned to match the remediated project dependency set.
RUN uv pip install --system --no-cache streamlit==1.54.0 requests==2.34.2 matplotlib

COPY ui/streamlit_app.py ui/property_workflow.py ./

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"

CMD ["streamlit", "run", "streamlit_app.py", \
     "--server.port=8501", \
     "--server.headless=true", \
     "--server.address=0.0.0.0"]
