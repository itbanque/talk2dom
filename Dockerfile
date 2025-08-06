FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        gcc \
        libxml2-dev \
        libxslt1-dev \
        libffi-dev \
        libssl-dev \
        build-essential \
        && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium

COPY . .

EXPOSE 8000

CMD ["uvicorn", "talk2dom.api.main:app", "--host", "0.0.0.0", "--port", "8000"]