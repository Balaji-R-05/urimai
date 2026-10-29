FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app/bot

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot/ .

RUN useradd --create-home --uid 1000 bot && chown -R bot:bot /app
USER bot

CMD ["python", "main.py"]
