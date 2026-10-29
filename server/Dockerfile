FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app/server

COPY server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server/ .

# .models is pre-created so the named volume mounted there (see compose.yml) inherits
# this ownership instead of root's, letting the retrieval models download at runtime.
RUN mkdir -p .models \
    && useradd --create-home --uid 1000 server \
    && chown -R server:server /app
USER server

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
