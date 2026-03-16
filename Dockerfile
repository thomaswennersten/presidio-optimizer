FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt requirements.txt
RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ && \
    pip install --no-cache-dir -r requirements.txt && \
    python -m spacy download sv_core_news_sm && \
    python -m spacy download en_core_web_sm && \
    apt-get purge -y gcc g++ && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

COPY backend/ .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
