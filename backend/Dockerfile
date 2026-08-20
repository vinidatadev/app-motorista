FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Roda como usuário não-root
RUN adduser --disabled-password --no-create-home appuser
USER appuser

EXPOSE 8000

# Temporariamente usando main-simple para troubleshooting
CMD ["uvicorn", "main-simple:app", "--host", "0.0.0.0", "--port", "8000"]
