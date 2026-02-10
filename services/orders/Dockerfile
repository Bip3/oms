FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY shared /app/shared
COPY services/orders /app/services/orders

ENV PYTHONPATH=/app

WORKDIR /app/services/orders

EXPOSE 8003

CMD ["uvicorn", "services.orders.main:app", "--host", "0.0.0.0", "--port", "8003"]
