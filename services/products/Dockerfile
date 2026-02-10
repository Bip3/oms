FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY shared /app/shared
COPY services/products /app/services/products

ENV PYTHONPATH=/app

WORKDIR /app/services/products

EXPOSE 8002

CMD ["uvicorn", "services.products.main:app", "--host", "0.0.0.0", "--port", "8002"]
